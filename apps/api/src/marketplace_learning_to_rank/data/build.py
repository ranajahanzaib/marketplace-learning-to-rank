from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES,FEATURE_VERSION,features,vector
from marketplace_learning_to_rank.retrieval.search import MODEL_ID,MODEL_REVISION,SearchEngine,corpus_digest

def build_embeddings(data_dir:Path,artifact_dir:Path)->dict:
    from sentence_transformers import SentenceTransformer
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    artifact_dir.mkdir(parents=True,exist_ok=True); path=artifact_dir/'providers.npz';meta_path=path.with_suffix('.json')
    digest=corpus_digest(providers)
    if path.exists() and meta_path.exists():
        cached=json.loads(meta_path.read_text())
        if cached.get('model_id')==MODEL_ID and cached.get('model_revision')==MODEL_REVISION and cached.get('provider_digest')==digest:
            try:
                with np.load(path,allow_pickle=False) as archive:
                    ids=archive['provider_ids'];vectors=archive['vectors']
                    valid=(ids.shape==(len(providers),) and vectors.ndim==2 and
                        vectors.shape[0]==len(providers) and vectors.shape[1]==cached.get('dimension') and
                        np.array_equal(ids,np.asarray([p.provider_id for p in providers])) and
                        np.isfinite(vectors).all() and np.allclose(np.linalg.norm(vectors,axis=1),1.0,atol=1e-3))
                if valid:return {**cached,"cached":True}
            except (OSError,ValueError,KeyError):
                pass
    model=SentenceTransformer(MODEL_ID,revision=MODEL_REVISION)
    vectors=model.encode([p.searchable_text() for p in providers],normalize_embeddings=True,show_progress_bar=True)
    vectors=np.asarray(vectors,dtype=np.float32)
    if vectors.ndim!=2 or vectors.shape[0]!=len(providers) or not np.isfinite(vectors).all():raise ValueError("Embedding model returned invalid vectors")
    norms=np.linalg.norm(vectors,axis=1)
    if not np.allclose(norms,1.0,atol=1e-3):raise ValueError("Embedding vectors are not normalized")
    np.savez_compressed(path,provider_ids=np.asarray([p.provider_id for p in providers]),vectors=vectors)
    meta={"model_id":MODEL_ID,"model_revision":MODEL_REVISION,"provider_digest":digest,"provider_count":len(providers),"dimension":int(vectors.shape[1]),"normalized":True,"artifact":path.name,"cached":False}
    path.with_suffix('.json').write_text(json.dumps(meta,indent=2));return meta

def build_features(data_dir:Path,output:Path)->dict:
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((data_dir/'queries.json').read_text())]
    labels=json.loads((data_dir/'judgments.json').read_text());byq={q.query_id:[] for q in queries};byp={p.provider_id:p for p in providers}
    for row in labels:byq[row['query_id']].append(row)
    settings=json.loads((data_dir/"manifest.json").read_text()).get("settings",{})
    engine=SearchEngine(providers,candidate_k=int(settings.get("candidate_count",60)))
    if not engine.semantic_model:raise RuntimeError("Feature building requires local embeddings; run `marketplace_learning_to_rank embeddings build` after installing the semantic extra")
    output.parent.mkdir(parents=True,exist_ok=True);count=0
    with output.open('w') as f:
        for q in queries:
            rows=byq[q.query_id];ps=[byp[row['provider_id']] for row in rows]
            lex=engine.lexical_scores(q,ps);sem=engine.semantic_scores(q,ps)
            for row,p in zip(rows,ps):
                record={"query_id":q.query_id,"provider_id":p.provider_id,"label":row['label'],"features":vector(features(q,p,lex[p.provider_id],sem[p.provider_id]))}
                f.write(json.dumps(record,separators=(',',':'))+'\n');count+=1
    return {"feature_version":FEATURE_VERSION,"feature_names":FEATURE_NAMES,"row_count":count,"path":str(output)}
