from __future__ import annotations
import hashlib, json, platform, re
from datetime import datetime, timezone
from pathlib import Path
import lightgbm as lgb
import numpy as np
from marketplace_learning_to_rank import __version__
from marketplace_learning_to_rank.core.models import MarketplaceQuery, Provider
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES, FEATURE_VERSION, features, vector
from marketplace_learning_to_rank.retrieval.search import SearchEngine
from marketplace_learning_to_rank.data.splits import intent_key

PARAMETERS={"objective":"lambdarank","metric":"ndcg","n_estimators":300,"learning_rate":0.04,
 "num_leaves":15,"max_depth":5,"min_child_samples":25,"random_state":42,"deterministic":True,
 "force_col_wise":True,"n_jobs":1,"label_gain":[0,1,3,7,15]}

def _read(data_dir:Path):
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((data_dir/'queries.json').read_text())]
    judgments=json.loads((data_dir/'judgments.json').read_text()); splits=json.loads((data_dir/'splits.json').read_text())
    if len({p.provider_id for p in providers})!=len(providers): raise ValueError("Duplicate provider_id values")
    qids={q.query_id for q in queries}
    if None in qids or len(qids)!=len(queries): raise ValueError("Missing or duplicate query_id values")
    if set(splits)!=qids or set(splits.values())!={"train","validation","test"}: raise ValueError("Split map must cover every query exactly once")
    texts=[re.sub(r"\W+"," ",q.text.casefold()).strip() for q in queries]
    if len(set(texts))!=len(texts):raise ValueError("Duplicate normalized query text across split groups")
    intents={}
    for query in queries:
        part=splits[query.query_id]
        if intent_key(query) in intents and intents[intent_key(query)]!=part:raise ValueError("Structured query intent leakage across split groups")
        intents[intent_key(query)]=part
    seen=set();provider_ids={p.provider_id for p in providers}
    for row in judgments:
        key=(row["query_id"],row["provider_id"])
        if key in seen: raise ValueError(f"Duplicate judgment: {key}")
        if row["query_id"] not in qids or row["provider_id"] not in provider_ids: raise ValueError(f"Unknown judgment reference: {key}")
        if int(row["label"]) not in range(5): raise ValueError(f"Invalid relevance label: {row['label']}")
        seen.add(key)
    return providers,queries,judgments,splits

def train(data_dir:Path, model_path:Path, engine=None):
    providers,queries,labels,split=_read(data_dir)
    byq={q.query_id:[] for q in queries}; byp={p.provider_id:p for p in providers}
    for row in labels: byq[row['query_id']].append(row)
    heldout_path=data_dir/'provider_holdout.json';heldout=set(json.loads(heldout_path.read_text())) if heldout_path.exists() else set()
    settings=json.loads((data_dir/"manifest.json").read_text()).get("settings",{})
    engine=engine or SearchEngine(providers,candidate_k=int(settings.get("candidate_count",60)))
    if engine.model_id is None:raise RuntimeError("Training requires a real or explicitly injected encoder; run embeddings build")
    if not engine.semantic_model:
        raise RuntimeError("Training requires the local dense embedding model. Run `marketplace_learning_to_rank embeddings build` first.")
    matrices={}; groups={}; query_counts={}
    for part in ('train','validation'):
        X=[]; y=[]; sizes=[]; query_counts[part]=0
        for q in queries:
            if split[q.query_id]!=part: continue
            rows=[row for row in byq[q.query_id] if row["provider_id"] not in heldout]
            if not rows: continue
            query_counts[part]+=1; sizes.append(len(rows))
            qproviders=[byp[row["provider_id"]] for row in rows]
            lexical=engine.lexical_scores(q,qproviders)
            semantic=engine.semantic_scores(q,qproviders)
            for row in rows:
                p=byp[row['provider_id']]
                # Dense similarity is computed via the same online index used by serving.
                X.append(vector(features(q,p,lexical[p.provider_id],semantic[p.provider_id]))); y.append(int(row['label']))
        if not sizes or sum(sizes)!=len(y): raise ValueError(f"Invalid {part} query groups")
        matrices[part]=(np.asarray(X,dtype=float),np.asarray(y,dtype=int)); groups[part]=sizes
    X,y=matrices['train']; VX,VY=matrices['validation']
    model=lgb.LGBMRanker(**PARAMETERS,verbosity=-1)
    model.fit(X,y,group=groups['train'],eval_set=[(VX,VY)],eval_group=[groups['validation']],eval_at=[5,10],feature_name=FEATURE_NAMES,callbacks=[lgb.early_stopping(25,verbose=False)])
    model_path.parent.mkdir(parents=True,exist_ok=True)
    model_file=model_path.parent/'ranker.txt'; model.booster_.save_model(str(model_file))
    artifact_hash=hashlib.sha256(model_file.read_bytes()).hexdigest()
    feature_schema={"schema_version":FEATURE_VERSION,"feature_names":FEATURE_NAMES,"dtype":"float64","label":"synthetic relevance 0-4"}
    (model_path.parent/'feature_schema.json').write_text(json.dumps(feature_schema,indent=2))
    manifest={"model_id":"marketplace_learning_to_rank-lambdamart","model_version":__version__,"trained_at":datetime.now(timezone.utc).isoformat(),
      "training_seed":42,"dataset_version":json.loads((data_dir/'manifest.json').read_text()).get('generator_version','unknown'),
      "feature_schema_version":FEATURE_VERSION,"embedding_model_id":engine.model_id,"embedding_model_revision":engine.model_revision,
      "lightgbm_version":lgb.__version__,"python_version":platform.python_version(),"training_row_count":len(y),
      "training_query_count":query_counts['train'],"validation_query_count":query_counts['validation'],"feature_names":FEATURE_NAMES,
      "hyperparameters":PARAMETERS,"best_iteration":model.best_iteration_,"artifact_hash_sha256":artifact_hash,
      "evaluation_summary":None,"synthetic_demo_data":True}
    (model_path.parent/'model_manifest.json').write_text(json.dumps(manifest,indent=2))
    (model_path.parent/'training_metrics.json').write_text(json.dumps({"training_rows":len(y),"validation_rows":len(VY),"train_groups":len(groups['train']),"validation_groups":len(groups['validation']),"best_iteration":model.best_iteration_,"validation_history":model.evals_result_},indent=2))
    return manifest
