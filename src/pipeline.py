from __future__ import annotations
import json,time
from pathlib import Path
from extractor import extract_book
from format_protector import protect,restore
from chunker import chunk_text,parse_structure
from assembler import assemble_translations,assemble_book
from translator import translate_chapter
from consistency import ConsistencyModel,generate_consistency_report
from kg_builder import build_knowledge_graph,kg_to_glossary
from api_client import call_api
from vector_store import TranslationVectorStore
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
PROJECT_ROOT=Path(__file__).parent.parent.resolve()
def slugify(book_name: str) -> str:
    """把书名转为安全的 checkpoint 文件名片段（保留中英文与数字）。"""
    slug = re.sub(r'[^\w一-鿿-]+', '_', book_name, flags=re.UNICODE).strip('_')[:40]
    return slug or 'book'
def checkpoint_path_for(book_name: str, chapter_index: int, cfg: dict = None) -> str:
    """checkpoint 路径：按书名 slug + 章节索引命名，跨书不冲突。"""
    cache_dir = Path(cfg['cache_dir']) if cfg else PROJECT_ROOT/'cache'
    return str(cache_dir/f'checkpoint_{slugify(book_name)}__{chapter_index:03d}.json')
def run_translation_pipeline(params:dict,log_fn=None,progress_fn=None,cancel_fn=None)->dict:
 log=log_fn or print; progress=progress_fn or (lambda f,m:log(m)); cancel=cancel_fn or (lambda:False); started=time.time(); cfg=params['config']; book=Path(params['book']); errors=[]; cfg.setdefault('_cost',{}); cfg['_cost'].setdefault('prompt_tokens',0); cfg['_cost'].setdefault('completion_tokens',0)
 if not book.exists(): raise FileNotFoundError(str(book))
 _tiers=cfg.get('llm_tiers')
 if _tiers and cfg.get('reasoning_effort'):
  _tiers={k:{**v,'reasoning_effort':cfg['reasoning_effort']} for k,v in _tiers.items()}
 progress(.03,'Extracting text...'); text=extract_book(str(book),use_vision=not params.get('no_vision',False),max_mb=cfg.get('max_input_file_mb',100),max_mb_abort=cfg.get('max_input_file_mb_abort',500)); text,ph=protect(text); chapters=parse_structure(text); log(f'Extracted: {len(text)} chars, {len(chapters)} chapters'); kg={}; glossary={}
 if not params.get('no_preread',False) and cfg.get('enable_agentic_preread',True):
  def kg_call(sp,up): return call_api(api_key=cfg.get('litellm_api_key') or cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=4096,provider=cfg.get('provider','custom'),tier='fast',llm_tiers=_tiers if cfg.get('use_tiered_models') else None,temperature=cfg.get('temperature',0.3),max_retries=cfg.get('max_retries',3),retry_base_delay=cfg.get('retry_base_delay',2),retry_max_delay=cfg.get('retry_max_delay',30))
  kg=build_knowledge_graph(text,kg_call,sample_ratio=cfg.get('preread_sample_ratio',.1),max_sample_tokens=cfg.get('preread_max_sample_tokens',30000)); glossary=kg_to_glossary(kg); rd0=Path(cfg['reports_dir']); rd0.mkdir(parents=True,exist_ok=True); json.dump(kg,open(rd0/'knowledge_graph.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 else: log('Pre-read skipped')
 if cfg.get('genre')=='auto': cfg['genre']=kg.get('book_metadata',{}).get('genre','natural_science')
 progress(.07,'Chunking...'); overlap=params.get('overlap') if params.get('overlap') is not None else cfg['overlap_by_genre'].get(cfg.get('genre','auto'),3); groups=[]
 for ch in chapters:
  if cancel(): return _result(None,chapters,groups,[],errors,started,cfg)
  t='\n\n'.join(ch.get('paragraphs',[]))
  if t.strip(): groups.append((ch['title'],chunk_text(t,target_tokens=params.get('target_tokens') or cfg.get('chunk_target_tokens',1500),max_tokens=cfg.get('chunk_max_tokens',3000),overlap_sentences=overlap)))
 total=sum(len(x) for _,x in groups); chars=sum(len(c.text) for _,xs in groups for c in xs); progress(.07,f'Translating ({total} chunks)'); shared=ConsistencyModel(threshold=cfg.get('consistency_alert_threshold',0.8)); results=[]; vs=None
 if not params.get('no_rat',False):
  vs=TranslationVectorStore(persist_dir=cfg['vector_store_dir'],use_gpu=cfg.get('use_gpu',True))
  if params.get('clear_cache',False): vs.initialize(); vs.clear()
  else: vs.initialize()
  if not vs.ready:
   log('⚠️ RAT unavailable (missing deps or embedding model failed to load); translating without retrieval augmentation. Install: uv sync --extra rat')
   vs=None
  else:
   log('RAT retrieval augmentation ready')
 provider=cfg.get('provider','custom'); cost_lock=threading.Lock(); consistency_lock=threading.Lock()
 def llm(sp,up,tier=None): return call_api(api_key=cfg.get('litellm_api_key') or cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=cfg.get('max_tokens_per_chunk',4096),provider=provider,tier=tier,llm_tiers=_tiers if cfg.get('use_tiered_models') else None,temperature=cfg.get('temperature',0.3),max_retries=cfg.get('max_retries',3),retry_base_delay=cfg.get('retry_base_delay',2),retry_max_delay=cfg.get('retry_max_delay',30))
 done_lock=threading.Lock(); done_count=[0]
 import time as _time
 _ps={'done_chars':0,'inflight':{},'speed':None,'msg':'','display':0.0,'lock':threading.Lock()}
 def _tick():
  while True:
   _time.sleep(.4)
   with _ps['lock']:
    if _ps['display']>=.999: break
    speed=_ps['speed'] or 8.0
    partial=sum(min(cs,speed*(_time.time()-t0)) for cs,t0 in _ps['inflight'].values())
    target=.07+.88*min(_ps['done_chars']+partial,chars)/max(chars,1)
    if target>_ps['display']+.0005:
     _ps['display']=target
     progress(_ps['display'],_ps['msg'])
 threading.Thread(target=_tick,daemon=True).start()
 def one(title,chunks,idx=0):
  cm=ConsistencyModel(threshold=cfg.get('consistency_alert_threshold',0.8))
  _char_map={c.id:len(c.text) for c in chunks}
  def cb(i,n,cid,status):
   with _ps['lock']:
    if status=='start':
     _ps['inflight'][cid]=(_char_map.get(cid,0),_time.time())
     _ps['msg']=f'Translating: {title} {i}/{n}'
    else:
     if status!='fail':
      done_count[0]+=1
      cs=_char_map.get(cid,0)
      _ps['done_chars']+=cs
      t0=_ps['inflight'].pop(cid,(0,0))[1]
      if status=='ok' and t0:
       sp=cs/max(_time.time()-t0,.1)
       _ps['speed']=sp if _ps['speed'] is None else _ps['speed']*.5+sp*.5
     tag={'ok':'ok','fail':'fail','skip':'skipped (cached)'}.get(status,status)
     log(f'  [{i}/{n}] {tag} {cid}')
     _ps['display']=.07+.88*min(_ps['done_chars'],chars)/max(chars,1)
     progress(_ps['display'],f'Translating: {title} {i}/{n}')
  tr,er=translate_chapter(chapter_title=title,chunks=chunks,vector_store=vs,consistency_model=cm,glossary=glossary,kg=kg,llm_call=llm,config=cfg,checkpoint_path=checkpoint_path_for(book.stem,idx,cfg),cost_lock=cost_lock,chunk_cb=cb)
  with consistency_lock:
   for term,usages in cm.term_usage.items():
    target=shared.term_usage.setdefault(term,{})
    for zh,count in usages.items(): target[zh]=target.get(zh,0)+count
   for term,locs in cm.term_locations.items(): shared.term_locations.setdefault(term,[]).extend(locs)
   for term,src in cm.term_source.items(): shared.term_source.setdefault(term,src)
  return title,chunks,tr,er
 workers=params.get('parallel',0) or cfg.get('parallel_workers',0); workers=min(workers,len(groups),4) if workers==0 and len(groups)>1 else workers
 if workers>1 and len(groups)>1:
  with ThreadPoolExecutor(max_workers=workers) as pool:
   fs={pool.submit(one,t,c,i):i for i,(t,c) in enumerate(groups)}
   by_idx={}; done_chars=0
   for f in as_completed(fs):
    if cancel(): break
    t,c,tr,er=f.result(); by_idx[fs[f]]=(t,c,tr); errors.extend(er)
    done_chars+=sum(len(x.text) for x in c)
    progress(.07+.88*min(done_chars,chars)/max(chars,1),t)
   if cancel(): return _result(None,chapters,groups,[],errors,started,cfg)
   # 按章节索引排序组装 — as_completed 顺序与章节顺序无关，直接 append 会乱序
   results=[by_idx[i] for i in sorted(by_idx)]
 else:
  for idx,(t,c) in enumerate(groups):
   if cancel(): return _result(None,chapters,groups,[],errors,started,cfg)
   t,c,tr,er=one(t,c,idx); results.append((t,c,tr)); errors.extend(er); progress(.07+.88*min(sum(sum(len(c.text) for c in x[1]) for x in results),chars)/max(chars,1),t)
 if errors:
  log(f'Translation errors ({len(errors)} chunks):')
  for e in errors[:10]: log(f"  {e.get('chapter','?')}/{e.get('chunk_id','?')}: {e.get('error',e)}")
  if len(errors)>10: log(f'  ... {len(errors)-10} more errors')
 progress(.96,'Quality audit...'); issues=shared.audit_all(min_occurrences=3); rd=Path(cfg['reports_dir'])/'consistency'; rd.mkdir(parents=True,exist_ok=True); log(generate_consistency_report(issues,shared.get_glossary_snapshot(),output_path=str(rd/'consistency_report.txt'),threshold=cfg.get('consistency_alert_threshold',0.8))); shared.save(str(rd/'consistency_model.json')); json.dump(shared.get_glossary_snapshot(),open(rd/'glossary_final.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 progress(.99,'Assembling...'); name=book.stem; out=params.get('output') or str(PROJECT_ROOT/'output'/name/f"{name}.{params.get('format','txt')}"); Path(out).parent.mkdir(parents=True,exist_ok=True); assemble_book([(t,restore(assemble_translations(c,tr,strategy=cfg.get('assembly_strategy','first_lock')),ph,verbose=False)) for t,c,tr in results],out,fmt=params.get('format','txt')); progress(1,'Translation complete'); _ps['display']=1.0; c=cfg.get('_cost',{}); return _result(out,chapters,groups,issues,errors,started,cfg)
def _result(out,chapters,groups,issues,errors,started,cfg):
 c=cfg.get('_cost',{}); return {'output_path':out,'num_chapters':len(chapters),'num_chunks':sum(len(x) for _,x in groups),'num_issues':len(issues),'num_errors':len(errors),'elapsed_sec':time.time()-started,'prompt_tokens':c.get('prompt_tokens',0),'completion_tokens':c.get('completion_tokens',0),'errors':errors}
