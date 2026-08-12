from __future__ import annotations
import json,time
from pathlib import Path
from config import calc_cost
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
def checkpoint_path_for(book_name: str, chapter_index: int) -> str:
    """checkpoint 路径：按书名 slug + 章节索引命名，跨书不冲突。"""
    return str(PROJECT_ROOT/'cache'/f'checkpoint_{slugify(book_name)}__{chapter_index:03d}.json')
def run_translation_pipeline(params:dict,log_fn=None,progress_fn=None,cancel_fn=None)->dict:
 log=log_fn or print; progress=progress_fn or (lambda f,m:log(m)); cancel=cancel_fn or (lambda:False); started=time.time(); cfg=params['config']; book=Path(params['book']); errors=[]; cfg.setdefault('_cost',{}); cfg['_cost'].setdefault('prompt_tokens',0); cfg['_cost'].setdefault('completion_tokens',0)
 if not book.exists(): raise FileNotFoundError(str(book))
 progress(.02,'Phase 0: 提取 + 预读'); text=extract_book(str(book),use_vision=not params.get('no_vision',False)); log(f'提取: {len(text)} 字符'); text,ph=protect(text); chapters=parse_structure(text); log(f'章节: {len(chapters)} 章'); kg={}; glossary={}
 if not params.get('no_preread',False) and cfg.get('enable_agentic_preread',True):
  def kg_call(sp,up): return call_api(api_key=cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=4096,provider=cfg.get('provider','custom'),tier='fast',llm_tiers=cfg.get('llm_tiers') if cfg.get('use_tiered_models') else None)
  kg=build_knowledge_graph(text,kg_call,sample_ratio=cfg.get('preread_sample_ratio',.1),max_sample_tokens=cfg.get('preread_max_sample_tokens',30000)); glossary=kg_to_glossary(kg); (PROJECT_ROOT/'reports').mkdir(parents=True,exist_ok=True); json.dump(kg,open(PROJECT_ROOT/'reports'/'knowledge_graph.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 else: log('跳过 Pre-Read')
 if cfg.get('genre')=='auto': cfg['genre']=kg.get('book_metadata',{}).get('genre','natural_science')
 progress(.1,'Phase 1: 语义分块'); overlap=params.get('overlap') if params.get('overlap') is not None else cfg['overlap_by_genre'].get(cfg.get('genre','auto'),3); groups=[]
 for ch in chapters:
  if cancel(): return _result(None,chapters,groups,[],errors,started,cfg)
  t='\n\n'.join(ch.get('paragraphs',[]))
  if t.strip(): groups.append((ch['title'],chunk_text(t,target_tokens=params.get('target_tokens',1500),max_tokens=cfg.get('chunk_max_tokens',3000),overlap_sentences=overlap)))
 total=sum(len(x) for _,x in groups); chars=sum(len(c.text) for _,xs in groups for c in xs); est_tokens=int(chars*1.8); est_cost,_=calc_cost(cfg.get('model',''),est_tokens,est_tokens,cfg.get('pricing')); log(f'预检估算:\n  总字符: {chars:,}\n  总块数: {total}\n  预估 token: ~{est_tokens:,}\n  预估费用: ${est_cost:.4f}' if est_cost is not None else '预估费用: 未知'); progress(.15,f'Phase 2: 翻译 ({total} 块)'); shared=ConsistencyModel(); results=[]; vs=None
 if not params.get('no_rat',False):
  vs=TranslationVectorStore(persist_dir=cfg['vector_store_dir'])
  if params.get('clear_cache',False): vs.initialize(); vs.clear()
  else: vs.initialize()
  if not vs.ready:
   log('⚠️ RAT 不可用（依赖缺失或嵌入模型加载失败），本次翻译不含检索增强；主流程不受影响。安装: uv sync --extra rat')
   vs=None
  else:
   log('✅ RAT 检索增强已就绪')
 provider=cfg.get('provider','custom'); cost_lock=threading.Lock(); consistency_lock=threading.Lock()
 def llm(sp,up,tier=None): return call_api(api_key=cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=cfg.get('max_tokens_per_chunk',4096),provider=provider,tier=tier,llm_tiers=cfg.get('llm_tiers') if cfg.get('use_tiered_models') else None)
 done_lock=threading.Lock(); done_count=[0]
 def one(title,chunks,idx=0):
  cm=ConsistencyModel()
  def cb(i,n,cid,status):
   with done_lock:
    done_count[0]+=1; d=done_count[0]
   progress(.15+.55*d/max(total,1),f'Translating: {title} {i}/{n}')
  tr,er=translate_chapter(chapter_title=title,chunks=chunks,vector_store=vs,consistency_model=cm,glossary=glossary,kg=kg,llm_call=llm,config=cfg,checkpoint_path=checkpoint_path_for(book.stem,idx),cost_lock=cost_lock,chunk_cb=cb)
  with consistency_lock:
   for term,usages in cm.term_usage.items():
    target=shared.term_usage.setdefault(term,{})
    for zh,count in usages.items(): target[zh]=target.get(zh,0)+count
   for term,locs in cm.term_locations.items(): shared.term_locations.setdefault(term,[]).extend(locs)
  return title,chunks,tr,er
 workers=params.get('parallel',0) or cfg.get('parallel_workers',0)
 if workers>1 and len(groups)>1:
  with ThreadPoolExecutor(max_workers=workers) as pool:
   fs=[pool.submit(one,t,c,i) for i,(t,c) in enumerate(groups)]
   for f in as_completed(fs):
    if cancel(): break
    t,c,tr,er=f.result(); results.append((t,c,tr)); errors.extend(er); progress(.15+.55*sum(len(x[1]) for x in results)/max(total,1),t)
   if cancel(): return _result(None,chapters,groups,[],errors,started,cfg,est_tokens=est_tokens,est_cost=est_cost)
 else:
  for idx,(t,c) in enumerate(groups):
   if cancel(): return _result(None,chapters,groups,[],errors,started,cfg,est_tokens=est_tokens,est_cost=est_cost)
   t,c,tr,er=one(t,c,idx); results.append((t,c,tr)); errors.extend(er); progress(.15+.55*sum(len(x[1]) for x in results)/max(total,1),t)
 if errors:
  log(f'翻译错误 ({len(errors)} 个块):')
  for e in errors[:10]: log(f"  {e.get('chapter','?')}/{e.get('chunk_id','?')}: {e.get('error',e)}")
  if len(errors)>10: log(f'  ... 还有 {len(errors)-10} 个错误')
 from auditor import Auditor
 auditor=Auditor()
 for t,c,tr in results: auditor.scan_chapter(assemble_translations(c,tr,strategy=cfg.get('assembly_strategy','first_lock')),t)
 if auditor.total_issues>0:
  import io as _io
  from rich.console import Console as _Console
  _buf=_io.StringIO(); _Console(file=_buf,force_terminal=True,width=100).print(auditor.report()); log(_buf.getvalue().rstrip()); log(f'低 Token 审计共 {auditor.total_issues} 处候选')
 progress(.75,'Phase 3: 质量审计'); issues=shared.audit_all(min_occurrences=3); rd=PROJECT_ROOT/'reports'/'consistency'; rd.mkdir(parents=True,exist_ok=True); log(generate_consistency_report(issues,shared.get_glossary_snapshot(),output_path=str(rd/'consistency_report.txt'))); shared.save(str(PROJECT_ROOT/'reports'/'consistency_model.json')); json.dump(shared.get_glossary_snapshot(),open(rd/'glossary_final.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 progress(.9,'Phase 4: 组装'); name=book.stem; out=params.get('output') or str(PROJECT_ROOT/'output'/name/f"{name}.{params.get('format','txt')}"); Path(out).parent.mkdir(parents=True,exist_ok=True); assemble_book([(t,restore(assemble_translations(c,tr,strategy=cfg.get('assembly_strategy','first_lock')),ph,verbose=False)) for t,c,tr in results],out,fmt=params.get('format','txt')); progress(1,'翻译完成'); value,_=calc_cost(cfg.get('model',''),cfg['_cost']['prompt_tokens'],cfg['_cost']['completion_tokens'],cfg.get('pricing')); return _result(out,chapters,groups,issues,errors,started,cfg,value,est_tokens,est_cost)
def _result(out,chapters,groups,issues,errors,started,cfg,value=None,est_tokens=None,est_cost=None):
 c=cfg.get('_cost',{}); return {'output_path':out,'num_chapters':len(chapters),'num_chunks':sum(len(x) for _,x in groups),'num_issues':len(issues),'num_errors':len(errors),'elapsed_sec':time.time()-started,'prompt_tokens':c.get('prompt_tokens',0),'completion_tokens':c.get('completion_tokens',0),'cost_dollars':value,'errors':errors,'est_tokens':est_tokens,'est_cost_dollars':est_cost}
