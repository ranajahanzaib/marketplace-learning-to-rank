from __future__ import annotations
from contextlib import asynccontextmanager
import hashlib, json, os, time, uuid
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import lightgbm as lgb
from marketplace_learning_to_rank.core.models import MarketplaceQuery, Provider
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES, FEATURE_VERSION, features, vector
from marketplace_learning_to_rank.ranking.service import RankingService
from marketplace_learning_to_rank.retrieval.search import MODEL_ID,MODEL_REVISION,SearchEngine
from marketplace_learning_to_rank.experiments.harness import Event,ExperimentConfig,ExperimentStore,report as experiment_report,simulate as simulate_experiment

ROOT=Path(__file__).resolve().parents[5]; DATA=ROOT/'data/generated'; ARTIFACTS=ROOT/'artifacts'
state={"service":None,"manifest":None,"model_error":None,"dataset_meta":None}

def _load_service():
    state["service"]=None;state["manifest"]=None;state["model_error"]=None
    validation=ARTIFACTS/"data/validation.json"
    state["dataset_meta"]=json.loads(validation.read_text()) if validation.exists() else None
    path=DATA/'providers.json'
    if not path.exists():return
    providers=[Provider.model_validate(row) for row in json.loads(path.read_text())]
    model=None; manifest=None; model_file=ARTIFACTS/'models/ranker.txt'
    try:
        if model_file.exists():
            manifest=json.loads((ARTIFACTS/'models/model_manifest.json').read_text())
            schema=json.loads((ARTIFACTS/'models/feature_schema.json').read_text())
            digest=hashlib.sha256(model_file.read_bytes()).hexdigest()
            if digest!=manifest['artifact_hash_sha256']: raise ValueError("Model artifact hash does not match its manifest")
            if schema['feature_names']!=FEATURE_NAMES or manifest.get('feature_names')!=FEATURE_NAMES or schema['schema_version']!=FEATURE_VERSION or manifest.get('feature_schema_version')!=FEATURE_VERSION: raise ValueError("Model feature schema is incompatible with this server")
            model=lgb.Booster(model_file=str(model_file))
            if model.num_feature()!=len(FEATURE_NAMES) or model.feature_name()!=FEATURE_NAMES: raise ValueError("Model feature order does not match serving feature schema")
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as error:
        state['model_error']=str(error);model=None;manifest=None
    settings=json.loads((DATA/"manifest.json").read_text()).get("settings",{})
    if os.environ.get("RANKLIFT_CI_SMOKE")=="1":
        from marketplace_learning_to_rank.retrieval.smoke_encoder import SmokeEncoder
        engine=SearchEngine(providers,encoder=SmokeEncoder(),candidate_k=int(settings.get("candidate_count",60)))
    else:engine=SearchEngine(providers,candidate_k=int(settings.get("candidate_count",60)))
    service=RankingService(engine,model)
    if model and manifest and manifest.get('embedding_model_id') and (engine.model_id!=manifest.get('embedding_model_id') or engine.model_revision!=manifest.get('embedding_model_revision')):
        state['model_error']="Trained model embedding provenance does not match the loaded local encoder"
        model=None;manifest=None;service=RankingService(engine,None)
    if model and manifest and manifest.get('embedding_model_id') is None:
        service.model_uses_semantic=False
    else:service.model_uses_semantic=True
    state.update(service=service,manifest=manifest)

@asynccontextmanager
async def lifespan(app:FastAPI):
    _load_service();yield;state.update(service=None)
app=FastAPI(title="Marketplace Learning to Rank API",version="0.2.0",description="Local marketplace ranking lab. Demo records and labels are synthetic.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["GET","POST","DELETE"],allow_headers=["content-type"])

def _service():
    if state['service'] is None:raise HTTPException(503,"Marketplace data is not prepared. Run `marketplace_learning_to_rank pipeline run`.")
    return state['service']

def _evaluate_file():
    path=ARTIFACTS/'evaluations/evaluation_metrics.json'
    if not path.exists():raise HTTPException(503,"Evaluation report is unavailable. Run `marketplace_learning_to_rank evaluate`.")
    return json.loads(path.read_text())

@app.get('/api/health')
@app.get('/api/v1/health')
def health():return {"status":"ok","data_loaded":state['service'] is not None,"synthetic_demo_data":True,"model_error":state['model_error']}
@app.get('/api/v1/ready')
def ready():
    service=state['service']
    if service is None:raise HTTPException(503,"Provider catalog is not loaded")
    return {"ready":True,"semantic_available":service.engine.model_id==MODEL_ID,"lambdamart_available":service.model is not None}
@app.post('/api/search')
@app.post('/api/v1/search')
def search(q:MarketplaceQuery,strategy:str='rules',limit:int=Query(20,ge=1,le=100)):
    service=_service();request_id=str(uuid.uuid4());start=time.perf_counter()
    try:result=service.search(q,strategy,limit)
    except ValueError as e:raise HTTPException(400,str(e))
    result.request_id=request_id;result.model_version=(state['manifest'] or {}).get('model_version') if strategy=='lambdamart' else None
    result.timings_ms["request_processing"]=round((time.perf_counter()-start)*1000,3)
    if strategy=='semantic' and service.engine.semantic_model is None: result.warnings.append("Dense semantic model is unavailable")
    return result
@app.post('/api/v1/search/compare')
def compare(q:MarketplaceQuery,strategies:str="rules,semantic,lambdamart",limit:int=Query(10,ge=1,le=100)):
    service=_service();requested=list(dict.fromkeys(strategies.split(',')))
    if len(requested)>3 or any(s not in {'rules','semantic','lambdamart'} for s in requested):raise HTTPException(422,"Strategies must be rules, semantic, or lambdamart")
    eligible,constraints=service.engine.eligible(q);candidates,candidate_counts=service.engine.retrieve(q,eligible);output={}
    for strategy in requested:
        try:output[strategy]=service.rank_candidates(q,strategy,candidates,candidate_counts,len(eligible),constraints,limit)
        except ValueError as e:output[strategy]={"available":False,"reason":str(e)}
    return {"request_id":str(uuid.uuid4()),"same_candidate_pool":True,"candidate_counts":candidate_counts,"eligible_count":len(eligible),"strategies":output}
@app.post('/api/v1/providers/compare')
def compare_providers(q:MarketplaceQuery,provider_a:str,provider_b:str):
    service=_service();eligible,constraints=service.engine.eligible(q);candidates,counts=service.engine.retrieve(q,eligible)
    candidate_lookup={p.provider_id:(p,lex,sem) for p,lex,sem in candidates}
    if provider_a not in candidate_lookup or provider_b not in candidate_lookup:raise HTTPException(404,"Both providers must be eligible and retrieved for this query")
    pa,la,sa=candidate_lookup[provider_a];pb,lb,sb=candidate_lookup[provider_b]
    fa=features(q,pa,la,sa);fb=features(q,pb,lb,sb)
    contributions={}
    if service.model is not None:
        rows=service.model.predict([vector(fa),vector(fb)],pred_contrib=True)
        contributions={provider_a:{n:float(rows[0][i]) for i,n in enumerate(FEATURE_NAMES)},provider_b:{n:float(rows[1][i]) for i,n in enumerate(FEATURE_NAMES)}}
    ranks={}
    for strategy in ('rules','semantic','lambdamart'):
        try:
            result=service.rank_candidates(q,strategy,candidates,counts,len(eligible),constraints,max(100,len(candidates)))
            ranks[strategy]={r.provider.provider_id:r.rank for r in result.results}
        except ValueError:continue
    return {"relative_to_current_candidate_pool":True,"provider_a":provider_a,"provider_b":provider_b,
      "observed_feature_differences":{name:{"a":getattr(fa,name),"b":getattr(fb,name),"delta_b_minus_a":getattr(fb,name)-getattr(fa,name)} for name in FEATURE_NAMES},
      "model_contributions":contributions,"strategy_ranks":{s:{"a":r.get(provider_a),"b":r.get(provider_b)} for s,r in ranks.items()}}
@app.get('/api/v1/providers/{provider_id}')
def provider(provider_id:str):
    service=_service()
    for p in service.engine.providers:
        if p.provider_id==provider_id:return p
    raise HTTPException(404,"Provider not found")
@app.get('/api/v1/demo-queries')
def demo_queries():
    path=DATA/'queries.json'
    if not path.exists():raise HTTPException(503,"Demo queries are not generated")
    return json.loads(path.read_text())[:20]
@app.get('/api/meta')
@app.get('/api/v1/models/current')
def metadata():
    service=state['service']
    return {"synthetic_demo_data":True,"provider_count":len(service.engine.providers) if service else 0,
      "semantic_available":bool(service and service.engine.model_id==MODEL_ID),"lambdamart_available":bool(service and service.model),
      "model_error":state['model_error'],"model":state['manifest'],"dataset":state['dataset_meta']}
@app.get('/api/v1/models/features')
def feature_schema():return {"schema_version":FEATURE_VERSION,"feature_names":FEATURE_NAMES}
@app.get('/api/v1/models/importance')
def feature_importance():
    service=_service()
    if service.model is None:raise HTTPException(503,"Trained model unavailable")
    values=service.model.feature_importance(importance_type='gain')
    return {"importance_type":"split gain","causal_interpretation":False,"features":[{"name":name,"gain":float(value)} for name,value in sorted(zip(FEATURE_NAMES,values),key=lambda pair:-pair[1])] }
@app.get('/api/v1/evaluation/benchmark')
def evaluation_benchmark():
    path=ARTIFACTS/'evaluations/benchmark.json'
    if not path.exists():raise HTTPException(503,"Benchmark report is unavailable")
    return json.loads(path.read_text())
@app.get('/api/v1/evaluation/summary')
def evaluation_summary():
    data=_evaluate_file();return {k:v for k,v in data.items() if k not in {'per_query','query_details','retrieval_failures'}}
@app.get('/api/v1/evaluation/queries')
def evaluation_queries(limit:int=Query(100,ge=1,le=1000)):
    data=_evaluate_file();rules={r['query_id']:r for r in data['per_query'].get('rules',[])};learned={r['query_id']:r for r in data['per_query'].get('lambdamart',[])}
    rows=[]
    for query_id,query in data.get('query_details',{}).items():
        row={"query_id":query_id,"text":query['text']}
        if query_id in rules:row['rules_ndcg@10']=rules[query_id]['ndcg@10']
        if query_id in learned:row['lambdamart_ndcg@10']=learned[query_id]['ndcg@10']
        if query_id in rules and query_id in learned:row['delta']=learned[query_id]['ndcg@10']-rules[query_id]['ndcg@10']
        rows.append(row)
    return {"split":"test","label_origin":data['label_origin'],"query_count":len(rows),"queries":sorted(rows,key=lambda row:(row.get('delta',0),row['query_id']))[:limit]}
@app.get('/api/v1/evaluation/queries/{query_id}')
def evaluation_query(query_id:str):
    data=_evaluate_file();results={}
    for strategy,rows in data['per_query'].items():
        row=next((item for item in rows if item['query_id']==query_id),None)
        if row:results[strategy]=row
    if not results:raise HTTPException(404,"Held-out evaluation query not found")
    base={pid:index+1 for index,pid in enumerate(results.get('rules',{}).get('ranked_provider_ids',[]))}
    rank_changes={}
    for strategy,row in results.items():
        current={pid:index+1 for index,pid in enumerate(row['ranked_provider_ids'])}
        rank_changes[strategy]={pid:{"rules_rank":base.get(pid),"strategy_rank":current.get(pid),"delta":base.get(pid)-current.get(pid) if pid in base and pid in current else None} for pid in sorted(set(base)|set(current))}
    return {"query_id":query_id,"query":data.get('query_details',{}).get(query_id),"strategies":results,"rank_changes":rank_changes,
      "relevant_provider_ids":results.get('rules',{}).get('relevant_provider_ids',[]),"label_origin":data['label_origin']}
@app.get('/api/v1/evaluation/failures')
def failures(limit:int=Query(20,ge=1,le=100)):
    data=_evaluate_file();rows=data['per_query'].get('lambdamart',[]);rules={r['query_id']:r for r in data['per_query'].get('rules',[])}
    ordered=sorted((r for r in rows if r['query_id'] in rules),key=lambda r:r['ndcg@10']-rules[r['query_id']]['ndcg@10'])
    return {"worst_regressions":[{**r,"ndcg_delta_vs_rules":r['ndcg@10']-rules[r['query_id']]['ndcg@10']} for r in ordered[:limit]],"largest_improvements":[{**r,"ndcg_delta_vs_rules":r['ndcg@10']-rules[r['query_id']]['ndcg@10']} for r in ordered[-limit:][::-1]],"semantic_retrieval_misses":data.get("retrieval_failures",[])[:limit]}
@app.get('/api/v1/evaluation/deltas')
def evaluation_deltas(limit:int=Query(500,ge=1,le=2000)):
    data=_evaluate_file();rules={r['query_id']:r for r in data['per_query'].get('rules',[])};learned={r['query_id']:r for r in data['per_query'].get('lambdamart',[])}
    rows=[{"query_id":qid,"rules_ndcg@10":rules[qid]['ndcg@10'],"lambdamart_ndcg@10":learned[qid]['ndcg@10'],"delta":learned[qid]['ndcg@10']-rules[qid]['ndcg@10']} for qid in rules.keys()&learned.keys()]
    return {"metric":"NDCG@10 delta (LambdaMART minus rules)","query_count":len(rows),"queries":sorted(rows,key=lambda row:(row['delta'],row['query_id']))[:limit]}
@app.get('/api/v1/evaluation/segments')
def evaluation_segments():
    data=_evaluate_file();return data.get('segments',{"available":False,"reason":"Segment evaluation has not been generated"})
@app.get('/api/v1/evaluation/cold-start')
def cold_start():
    data=_evaluate_file();return data.get('cold_start',{"available":False,"reason":"Dedicated held-out-provider analysis has not been generated"})
def _experiment_store():return ExperimentStore(ARTIFACTS/'experiments/marketplace_learning_to_rank.sqlite3')
@app.post('/api/v1/experiments')
def create_experiment(config:ExperimentConfig):
    if config.control_strategy not in {'rules','semantic','lambdamart'} or config.treatment_strategy not in {'rules','semantic','lambdamart'}:raise HTTPException(422,"Unsupported ranking strategy")
    try:return _experiment_store().create(config)
    except sqlite3.IntegrityError as e:raise HTTPException(409,"Experiment ID already exists") from e
@app.get('/api/v1/experiments/{experiment_id}')
def get_experiment(experiment_id:str):
    config=_experiment_store().get(experiment_id)
    if config is None:raise HTTPException(404,"Experiment not found")
    return config
@app.post('/api/v1/experiments/{experiment_id}/assignments')
def assignment(experiment_id:str,unit_id:str=Query(min_length=1,max_length=128)):
    store=_experiment_store();config=store.get(experiment_id)
    if config is None:raise HTTPException(404,"Experiment not found")
    return {"experiment_id":experiment_id,"unit_id":unit_id,"variant":store.assignment(config,unit_id)}
@app.post('/api/v1/experiments/{experiment_id}/events')
def ingest_event(experiment_id:str,event:Event):
    store=_experiment_store();config=store.get(experiment_id)
    if config is None:raise HTTPException(404,"Experiment not found")
    if event.experiment_id!=experiment_id:raise HTTPException(422,"Event experiment ID mismatch")
    assigned=store.assignment(config,event.visitor_id)
    if event.variant!=assigned:raise HTTPException(409,"Event variant does not match persistent visitor assignment")
    expected=config.treatment_strategy if assigned=="treatment" else config.control_strategy
    if event.strategy!=expected:raise HTTPException(409,"Event strategy does not match the assigned variant")
    if event.source not in {"real","simulated"}:raise HTTPException(422,"Event source must be real or simulated")
    return {"inserted":store.event(event),"idempotent":True}
@app.post('/api/v1/experiments/{experiment_id}/simulate')
def simulate(experiment_id:str,sessions:int=Query(500,ge=1,le=10000),seed:int=42):
    store=_experiment_store();config=store.get(experiment_id)
    if config is None:raise HTTPException(404,"Experiment not found")
    if config.status!="running":raise HTTPException(409,"Experiment is not running")
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((DATA/'queries.json').read_text())]
    judgments=json.loads((DATA/'judgments.json').read_text());byq={q.query_id:{} for q in queries}
    for row in judgments:byq[row['query_id']][row['provider_id']]=row['label']
    try:return simulate_experiment(store,config,_service(),queries,byq,sessions,seed)
    except (ValueError,RuntimeError) as e:raise HTTPException(400,str(e))
@app.delete('/api/v1/experiments/{experiment_id}/simulation')
def reset_simulation(experiment_id:str):
    store=_experiment_store()
    if store.get(experiment_id) is None:raise HTTPException(404,"Experiment not found")
    store.reset_simulation(experiment_id)
    return {"experiment_id":experiment_id,"simulated_events_reset":True}
@app.get('/api/v1/experiments/{experiment_id}/results')
def experiment_results(experiment_id:str):
    store=_experiment_store();config=store.get(experiment_id)
    if config is None:raise HTTPException(404,"Experiment not found")
    return experiment_report(store,config)
@app.get('/api/v1/pipeline/status')
def pipeline_status():
    return {"stages":{"dataset_generated":(DATA/'manifest.json').exists(),"embeddings_built":(ARTIFACTS/'embeddings/providers.npz').exists(),"model_trained":(ARTIFACTS/'models/ranker.txt').exists(),"evaluation_completed":(ARTIFACTS/'evaluations/evaluation_metrics.json').exists(),"validation_report_available":(ARTIFACTS/'data/validation.json').exists(),"feature_table_built":(ARTIFACTS/'features/features.jsonl').exists(),"benchmark_completed":(ARTIFACTS/'evaluations/benchmark.json').exists()},"model_error":state['model_error']}
