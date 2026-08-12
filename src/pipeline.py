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
PROJECT_ROOT=Path(__file__).parent.parent.resolve()
def run_translation_pipeline(params:dict,log_fn=None,progress_fn=None,cancel_fn=None)->dict:
 log=log_fn or print; progress=progress_fn or (lambda f,m:log(m)); cancel=cancel_fn or (lambda:False); started=time.time(); cfg=params['config']; book=Path(params['book']); errors=[]; cfg.setdefault('_cost',{}); cfg['_cost'].setdefault('prompt_tokens',0); cfg['_cost'].setdefault('completion_tokens',0)
 if not book.exists(): raise FileNotFoundError(str(book))
 progress(.02,'Phase 0: 提取 + 预读'); text=extract_book(str(book),use_vision=not params.get('no_vision',False)); log(f'提取: {len(text)} 字符'); text,ph=protect(text); chapters=parse_structure(text); log(f'章节: {len(chapters)} 章'); kg={}; glossary={}
 if not params.get('no_preread',False) and cfg.get('enable_agentic_preread',True):
  def kg_call(sp,up): return call_api(api_key=cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=4096,provider=cfg.get('provider','deepseek'),tier='fast',llm_tiers=cfg.get('llm_tiers') if cfg.get('use_tiered_models') else None)
  kg=build_knowledge_graph(text,kg_call,sample_ratio=cfg.get('preread_sample_ratio',.1),max_sample_tokens=cfg.get('preread_max_sample_tokens',30000)); glossary=kg_to_glossary(kg); (PROJECT_ROOT/'reports').mkdir(parents=True,exist_ok=True); json.dump(kg,open(PROJECT_ROOT/'reports'/'knowledge_graph.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 else: log('跳过 Pre-Read')
 if cfg.get('genre')=='auto': cfg['genre']=kg.get('book_metadata',{}).get('genre','natural_science')
 progress(.1,'Phase 1: 语义分块'); overlap=params.get('overlap') if params.get('overlap') is not None else cfg['overlap_by_genre'].get(cfg.get('genre','auto'),3); groups=[]
 for ch in chapters:
  if cancel(): return _result(None,chapters,groups,[],errors,started,cfg)
  t='\n\n'.join(ch.get('paragraphs',[]))
  if t.strip(): groups.append((ch['title'],chunk_text(t,target_tokens=params.get('target_tokens',1500),max_tokens=cfg.get('chunk_max_tokens',3000),overlap_sentences=overlap)))
 total=sum(len(x) for _,x in groups); progress(.15,f'Phase 2: 翻译 ({total} 块)'); shared=ConsistencyModel(); results=[]; vs=None
 if not params.get('no_rat',False): vs=TranslationVectorStore(persist_dir=cfg['vector_store_dir']); vs.initialize() if params.get('clear_cache',False) else None; vs.clear() if params.get('clear_cache',False) else None
 def llm(sp,up,tier=None): return call_api(api_key=cfg.get('api_key',''),api_base=cfg.get('api_base','https://api.deepseek.com/v1'),model=cfg.get('model','deepseek-v4-pro'),system_prompt=sp,user_prompt=up,max_tokens=cfg.get('max_tokens_per_chunk',4096),provider=provider,tier=tier,llm_tiers=cfg.get('llm_tiers') if cfg.get('use_tiered_models') else None)
 provider=cfg.get('provider','deepseek')
 for title,chunks in groups:
  if cancel(): break
  trans,errs=translate_chapter(chapter_title=title,chunks=chunks,vector_store=vs if not params.get('no_rat',False) else None,consistency_model=shared,glossary=glossary,kg=kg,llm_call=llm,config=cfg,checkpoint_path=str(PROJECT_ROOT/'cache'/f'checkpoint_{title}.json')); results.append((title,chunks,trans)); errors.extend(errs); progress(.15+.55*sum(len(x[1]) for x in results)/max(total,1),title)
 progress(.75,'Phase 3: 质量审计'); issues=shared.audit_all(min_occurrences=3); rd=PROJECT_ROOT/'reports'/'consistency'; rd.mkdir(parents=True,exist_ok=True); log(generate_consistency_report(issues,shared.get_glossary_snapshot(),output_path=str(rd/'consistency_report.txt'))); shared.save(str(PROJECT_ROOT/'reports'/'consistency_model.json')); json.dump(shared.get_glossary_snapshot(),open(rd/'glossary_final.json','w',encoding='utf8'),ensure_ascii=False,indent=2)
 progress(.9,'Phase 4: 组装'); name=book.stem; out=params.get('output') or str(PROJECT_ROOT/'output'/name/f'{name}.txt'); Path(out).parent.mkdir(parents=True,exist_ok=True); assemble_book([(t,restore(assemble_translations(c,tr,strategy=cfg.get('assembly_strategy','first_lock')),ph,verbose=False)) for t,c,tr in results],out,fmt=params.get('format','txt')); progress(1,'翻译完成'); value,_=calc_cost(cfg.get('model',''),cfg['_cost']['prompt_tokens'],cfg['_cost']['completion_tokens'],cfg.get('pricing')); return _result(out,chapters,groups,issues,errors,started,cfg,value)
def _result(out,chapters,groups,issues,errors,started,cfg,value=None):
 c=cfg.get('_cost',{}); return {'output_path':out,'num_chapters':len(chapters),'num_chunks':sum(len(x) for _,x in groups),'num_issues':len(issues),'num_errors':len(errors),'elapsed_sec':time.time()-started,'prompt_tokens':c.get('prompt_tokens',0),'completion_tokens':c.get('completion_tokens',0),'cost_dollars':value,'errors':errors}
