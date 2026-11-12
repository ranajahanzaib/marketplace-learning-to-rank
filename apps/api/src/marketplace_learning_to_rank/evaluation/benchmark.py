from __future__ import annotations
import hashlib,json,platform,resource,statistics,time
from pathlib import Path
import lightgbm as lgb
from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES,FEATURE_VERSION
from marketplace_learning_to_rank.ranking.service import RankingService
from marketplace_learning_to_rank.retrieval.search import SearchEngine

def percentile(values,p):return sorted(values)[min(len(values)-1,int((len(values)-1)*p))]
def summarize(values):return {"count":len(values),"p50_ms":round(percentile(values,.5),3),"p95_ms":round(percentile(values,.95),3),"mean_ms":round(statistics.mean(values),3)}
def benchmark(data_dir:Path,model_path:Path,output:Path,iterations:int=100,engine:SearchEngine|None=None):
    if iterations<10 or iterations>10000:raise ValueError("iterations must be between 10 and 10000")
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((data_dir/'queries.json').read_text())]
    start=time.perf_counter();settings=json.loads((data_dir/"manifest.json").read_text()).get("settings",{})
    engine=engine or SearchEngine(providers,candidate_k=int(settings.get("candidate_count",60)));model=None
    if model_path.exists():
        manifest_path=model_path.parent/'model_manifest.json';schema_path=model_path.parent/'feature_schema.json'
        if not manifest_path.exists() or not schema_path.exists():raise ValueError("Model manifest and feature schema are required for benchmarking")
        manifest=json.loads(manifest_path.read_text());schema=json.loads(schema_path.read_text())
        if hashlib.sha256(model_path.read_bytes()).hexdigest()!=manifest.get('artifact_hash_sha256'):raise ValueError("Model artifact hash does not match its manifest")
        if manifest.get('embedding_model_id')!=engine.model_id or manifest.get('embedding_model_revision')!=engine.model_revision:raise ValueError("Benchmark encoder does not match the trained model embedding provenance")
        if schema.get('feature_names')!=FEATURE_NAMES or schema.get('schema_version')!=FEATURE_VERSION:raise ValueError("Model feature schema is incompatible with benchmarking")
        model=lgb.Booster(model_file=str(model_path))
        if model.num_feature()!=len(FEATURE_NAMES) or model.feature_name()!=FEATURE_NAMES:raise ValueError("Model feature order does not match benchmark feature schema")
    initialization_ms=(time.perf_counter()-start)*1000;service=RankingService(engine,model);strategy='lambdamart' if model else 'rules'
    categories={}
    for q in queries:categories.setdefault(q.category,[]).append(q)
    category_names=list(categories)
    if len(category_names)<3:raise ValueError("Benchmark dataset must cover at least three categories")
    pool_sizes=sorted({min(20,engine.candidate_k),min(60,engine.candidate_k),engine.candidate_k});limits=[5,10,20]
    results={};overall=[];stages={"eligibility":[],"retrieval":[],"features":[],"ranking":[]};combos=[(k,n) for k in pool_sizes for n in limits]
    for i in range(iterations):
        pool,limit=combos[i%len(combos)];category=category_names[i%len(category_names)]
        q=categories[category][(i//len(category_names))%len(categories[category])];engine.candidate_k=pool
        response=service.search(q,strategy,limit);overall.append(response.timings_ms['total_server'])
        for key in stages:stages[key].append(response.timings_ms[key])
        results.setdefault(f"candidate_k={pool},limit={limit}",[]).append(response.timings_ms['total_server'])
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes=int(rss) if platform.system()=="Darwin" else int(rss*1024)
    embedding=Path(__file__).resolve().parents[5]/'artifacts/embeddings/providers.npz'
    report={"synthetic_demo_data":True,"iterations":iterations,"strategy":strategy,"provider_count":len(providers),"category_count":len(category_names),
      "initialization_ms":round(initialization_ms,3),"warm_process":True,"overall":summarize(overall),"p99_ms":round(percentile(overall,.99),3) if iterations>=100 else None,
      "throughput_requests_per_second":round(1000/statistics.mean(overall),3),"by_candidate_pool_and_limit":{key:summarize(values) for key,values in results.items()},
      "stage_latency_ms":{name:summarize(values) for name,values in stages.items()},"process_peak_rss_bytes":rss_bytes,
      "model_artifact_bytes":model_path.stat().st_size if model_path.exists() else None,"embedding_index_bytes":embedding.stat().st_size if embedding.exists() else None,
      "measurement":"in-process server ranking time, no browser/network round trip"}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2));return report
