from __future__ import annotations
import hashlib,json
from pathlib import Path
import lightgbm as lgb
from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.evaluation.metrics import bootstrap_mean,ndcg,paired_bootstrap_difference,precision_at_k,recall_at_k,mrr_at_k
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES,FEATURE_VERSION
from marketplace_learning_to_rank.ranking.service import RankingService
from marketplace_learning_to_rank.retrieval.search import MODEL_ID,SearchEngine

THRESHOLD=3;KS=(5,10,20)
def evaluate(data_dir:Path,model_path:Path,output_dir:Path|None=None,engine:SearchEngine|None=None):
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((data_dir/'queries.json').read_text())]
    judgments=json.loads((data_dir/'judgments.json').read_text());splits=json.loads((data_dir/'splits.json').read_text())
    labels={q.query_id:{} for q in queries}
    for row in judgments:labels[row['query_id']][row['provider_id']]=int(row['label'])
    provider_by_id={p.provider_id:p for p in providers}
    heldout=set(json.loads((data_dir/'provider_holdout.json').read_text())) if (data_dir/'provider_holdout.json').exists() else set()
    model=None
    if model_path.exists():
        manifest_path=model_path.parent/'model_manifest.json';schema_path=model_path.parent/'feature_schema.json'
        if not manifest_path.exists() or not schema_path.exists():raise ValueError("Model manifest and feature schema are required for evaluation")
        manifest=json.loads(manifest_path.read_text());schema=json.loads(schema_path.read_text())
        if hashlib.sha256(model_path.read_bytes()).hexdigest()!=manifest.get('artifact_hash_sha256'):raise ValueError("Model artifact hash does not match its manifest")
        if schema.get('feature_names')!=FEATURE_NAMES or schema.get('schema_version')!=FEATURE_VERSION or manifest.get('feature_names')!=FEATURE_NAMES or manifest.get('feature_schema_version')!=FEATURE_VERSION:raise ValueError("Model feature schema is incompatible with evaluation")
        if engine is not None and (manifest.get('embedding_model_id')!=engine.model_id or manifest.get('embedding_model_revision')!=engine.model_revision):raise ValueError("Evaluation encoder does not match the trained model embedding provenance")
        model=lgb.Booster(model_file=str(model_path))
        if model.num_feature()!=len(FEATURE_NAMES) or model.feature_name()!=FEATURE_NAMES:raise ValueError("Model feature order does not match evaluation feature schema")
    settings=json.loads((data_dir/"manifest.json").read_text()).get("settings",{})
    engine=engine or SearchEngine(providers,candidate_k=int(settings.get("candidate_count",60)))
    if model is not None:
        trained_manifest=json.loads((model_path.parent/'model_manifest.json').read_text())
        if trained_manifest.get('embedding_model_id')!=engine.model_id or trained_manifest.get('embedding_model_revision')!=engine.model_revision:raise ValueError("Evaluation encoder does not match the trained model embedding provenance")
    service=RankingService(engine,model)
    semantic_available=engine.model_id==MODEL_ID
    strategies=['rules']+(['semantic'] if semantic_available else [])+(['lambdamart'] if model else [])
    details={s:[] for s in strategies};query_details={};candidate_recall=[];eligible_coverage=[];zero=[];retriever_recall={"lexical":[],"semantic":[],"rules":[],"union":[]};retrieval_failures=[]
    cold_start={s:[] for s in strategies};unseen_provider={s:[] for s in strategies}
    for q in queries:
        if splits[q.query_id]!='test':continue
        eligible,constraints=engine.eligible(q);candidates,counts,candidate_sets=engine.retrieve_with_sets(q,eligible);candidate_ids=candidate_sets["union"];query_details[q.query_id]=q.model_dump(mode="json")
        judged=labels[q.query_id];relevant={pid for pid,label in judged.items() if label>=THRESHOLD}
        candidate_recall.append(len(set(candidate_ids)&relevant)/len(relevant) if relevant else 0.0)
        for stage,ids in candidate_sets.items():retriever_recall[stage].append(len(set(ids)&relevant)/len(relevant) if relevant else 0.0)
        missing_semantic=sorted(relevant-set(candidate_sets["semantic"])) if semantic_available else []
        if missing_semantic:retrieval_failures.append({"query_id":q.query_id,"retrieval_stage":"semantic","missed_relevant_provider_ids":missing_semantic})
        eligible_coverage.append(len(eligible)/max(1,len(providers)));zero.append(float(not eligible))
        unseen_relevant=relevant & heldout
        cold_relevant={pid for pid in relevant if provider_by_id[pid].review_count==0}
        for strategy in strategies:
            response=service.rank_candidates(q,strategy,candidates,counts,len(eligible),constraints,max(100,len(candidates)));ids=[r.provider.provider_id for r in response.results]
            y=[judged.get(pid,0) for pid in ids]
            row={"query_id":q.query_id,"eligible_count":len(eligible),"candidate_count":len(candidate_ids),"candidate_recall":candidate_recall[-1],"candidate_recall_by_retriever":{stage:retriever_recall[stage][-1] for stage in candidate_sets},"semantic_retrieval_misses":missing_semantic,"relevant_provider_ids":sorted(relevant),"zero_result":not bool(eligible),"ranked_provider_ids":ids}
            for k in KS:
                row[f"ndcg@{k}"]=ndcg(y,k);row[f"recall@{k}"]=recall_at_k(ids,relevant,k);row[f"precision@{k}"]=precision_at_k(y,k,THRESHOLD)
            row['mrr@10']=mrr_at_k(y,10,THRESHOLD);row['missed_relevant_provider_ids']=sorted(relevant-set(ids));details[strategy].append(row)
            if cold_relevant:
                cold_start[strategy].append({"query_id":q.query_id,"recall@10":recall_at_k(ids,cold_relevant,10),"candidate_recall":recall_at_k(candidate_ids,cold_relevant,len(candidate_ids)),"relevant_cold_provider_count":len(cold_relevant)})
            if unseen_relevant:
                unseen_provider[strategy].append({"query_id":q.query_id,"recall@10":recall_at_k(ids,unseen_relevant,10),"candidate_recall":recall_at_k(candidate_ids,unseen_relevant,len(candidate_ids)),"relevant_unseen_provider_count":len(unseen_relevant)})
    metric_keys=[f"{metric}@{k}" for metric in ('ndcg','recall','precision') for k in KS]+['mrr@10']
    summary={s:{"query_count":len(rows),**{key:bootstrap_mean([r[key] for r in rows],seed=42) for key in metric_keys}} for s,rows in details.items()}
    paired={}
    for strategy in strategies:
        if strategy=='rules':continue
        paired[strategy]={"ndcg@10":paired_bootstrap_difference([r['ndcg@10'] for r in details['rules']],[r['ndcg@10'] for r in details[strategy]],seed=41),"recall@10":paired_bootstrap_difference([r['recall@10'] for r in details['rules']],[r['recall@10'] for r in details[strategy]],seed=43)}
    freq={}
    for q in queries:
        for s in q.specialties:freq[s.casefold()]=freq.get(s.casefold(),0)+1
    segment_predicates={
      "low_budget":lambda q,r:q.max_rate_usd is not None and q.max_rate_usd<=65,
      "high_budget":lambda q,r:q.max_rate_usd is not None and q.max_rate_usd>=90,
      "remote_preferred":lambda q,r:q.remote_preferred is True,
      "local_or_onsite":lambda q,r:q.onsite_required or q.location_required,
      "sparse_specialty":lambda q,r:any(freq.get(s.casefold(),0)<=max(5,len(queries)//30) for s in q.specialties),
      "few_eligible":lambda q,r:r['eligible_count']<=10,
      "many_eligible":lambda q,r:r['eligible_count']>=30}
    qmap={q.query_id:q for q in queries};segments={}
    for segment,predicate in segment_predicates.items():
        segments[segment]={}
        for strategy,rows in details.items():
            part=[r for r in rows if predicate(qmap[r['query_id']],r)]
            segments[segment][strategy]={"query_count":len(part),"ndcg@10":bootstrap_mean([r['ndcg@10'] for r in part]),"recall@10":bootstrap_mean([r['recall@10'] for r in part])}
        if 'rules' in segments[segment]:
            for strategy in strategies:
                if strategy=='rules':continue
                a={r['query_id']:r for r in details['rules'] if predicate(qmap[r['query_id']],r)};b={r['query_id']:r for r in details[strategy] if predicate(qmap[r['query_id']],r)};ids=sorted(a.keys()&b.keys())
                segments[segment][strategy]['ndcg@10_delta_vs_rules']=paired_bootstrap_difference([a[i]['ndcg@10'] for i in ids],[b[i]['ndcg@10'] for i in ids]) if ids else None
    query_deltas={}
    for strategy in strategies:
        if strategy=="rules":continue
        baseline={r["query_id"]:r["ndcg@10"] for r in details["rules"]}
        deltas=[r["ndcg@10"]-baseline[r["query_id"]] for r in details[strategy]]
        query_deltas[strategy]={"mean_delta":sum(deltas)/max(1,len(deltas)),"improved_queries":sum(d>1e-12 for d in deltas),"regressed_queries":sum(d<-1e-12 for d in deltas),"unchanged_queries":sum(abs(d)<=1e-12 for d in deltas),"query_count":len(deltas),"delta_bootstrap_95_ci":paired_bootstrap_difference([baseline[r["query_id"]] for r in details[strategy]],[r["ndcg@10"] for r in details[strategy]])}
    result={"synthetic_demo_data":True,"split":"test","relevance_threshold":THRESHOLD,"query_count":len(next(iter(details.values()),[])),"query_level_gain_loss":query_deltas,
      "candidate_recall":bootstrap_mean(candidate_recall),"candidate_recall_by_retriever":{stage:({"available":False,"reason":"A production sentence-transformer model is not loaded."} if stage=="semantic" and not semantic_available else {"available":True,**bootstrap_mean(values)}) for stage,values in retriever_recall.items()},"retrieval_failures":retrieval_failures,"eligible_candidate_coverage_mean":sum(eligible_coverage)/max(1,len(eligible_coverage)),
      "zero_result_rate":sum(zero)/max(1,len(zero)),"strategies":summary,"paired_differences_vs_rules":paired,
      "per_query":details,"query_details":query_details,"segments":segments,
      "cold_start":{"definition":"no review history, complete profile","provider_level":{s:{"query_count":len(rows),"recall@10":bootstrap_mean([r['recall@10'] for r in rows]),"candidate_recall":bootstrap_mean([r['candidate_recall'] for r in rows])} for s,rows in cold_start.items()}},
      "unseen_provider_holdout":{"definition":"provider IDs excluded from all training/validation query groups","heldout_provider_count":len(heldout),"by_strategy":{s:{"query_count":len(rows),"recall@10":bootstrap_mean([r['recall@10'] for r in rows]),"candidate_recall":bootstrap_mean([r['candidate_recall'] for r in rows])} for s,rows in unseen_provider.items()}},
      "semantic_available":semantic_available,"label_origin":"simulated, not human relevance judgments",
      "candidate_pool":"same deterministic lexical + dense semantic (when available) + rules union for all rerankers"}
    dest=output_dir or Path(__file__).resolve().parents[5]/'artifacts/evaluations';dest.mkdir(parents=True,exist_ok=True)
    (dest/'evaluation_metrics.json').write_text(json.dumps(result,indent=2))
    manifest_path=model_path.parent/'model_manifest.json'
    if model is not None and manifest_path.exists():
        manifest=json.loads(manifest_path.read_text());manifest['evaluation_summary']={name:{'ndcg@10':metrics['ndcg@10'],'recall@10':metrics['recall@10']} for name,metrics in summary.items()}
        manifest_path.write_text(json.dumps(manifest,indent=2))
    return result
