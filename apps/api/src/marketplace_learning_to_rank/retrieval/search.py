from __future__ import annotations
import hashlib, json
import zipfile
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from marketplace_learning_to_rank.core.models import MarketplaceQuery, Provider
from marketplace_learning_to_rank.ranking.features import features

ROOT=Path(__file__).resolve().parents[5]
MODEL_ID="sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

@lru_cache(maxsize=1)
def _load_local_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_ID,revision=MODEL_REVISION,local_files_only=True)

def corpus_digest(providers:list[Provider])->str:
    return hashlib.sha256("\n".join(p.searchable_text() for p in providers).encode()).hexdigest()

class SearchEngine:
    def __init__(self, providers: list[Provider], embedding_path:Path|None=None, encoder=None, with_semantic:bool=True, candidate_k:int=60):
        self.providers=providers
        if candidate_k<1 or candidate_k>500:raise ValueError("candidate_k must be between 1 and 500")
        self.candidate_k=candidate_k
        if len({p.provider_id for p in providers})!=len(providers): raise ValueError("Provider IDs must be unique")
        if not providers: raise ValueError("Provider catalog must not be empty")
        self.vectorizer=TfidfVectorizer(ngram_range=(1,2),stop_words="english")
        self.matrix=self.vectorizer.fit_transform([p.searchable_text() for p in providers])
        self.positions={p.provider_id:i for i,p in enumerate(providers)}
        self.semantic_model=encoder; self.model_id=getattr(encoder,"model_id",MODEL_ID) if encoder else None; self.model_revision=getattr(encoder,"model_revision",None) if encoder else None; self.provider_vectors=None; self._query_vectors=OrderedDict()
        if self.semantic_model is None and with_semantic:
            try:
                self.semantic_model=_load_local_model();self.model_id=MODEL_ID;self.model_revision=MODEL_REVISION
            except (ImportError, OSError, ValueError, TypeError):
                return
        if self.semantic_model is None:return
        artifact=embedding_path or ROOT/'artifacts/embeddings/providers.npz'
        meta_path=artifact.with_suffix('.json')
        if artifact.exists() and meta_path.exists():
            try:
                meta=json.loads(meta_path.read_text())
                expected_revision=self.model_revision
                if meta.get('model_id')==self.model_id and meta.get('model_revision')==expected_revision and meta.get('provider_digest')==corpus_digest(providers):
                    with np.load(artifact,allow_pickle=False) as archive:
                        vectors=archive['vectors']; ids=archive['provider_ids'].tolist()
                    if ids==[p.provider_id for p in providers] and vectors.ndim==2 and vectors.shape[0]==len(providers) and vectors.shape[1]==int(meta.get("dimension",0)) and np.isfinite(vectors).all() and np.allclose(np.linalg.norm(vectors,axis=1),1.0,atol=1e-3):
                        self.provider_vectors=vectors
            except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile,json.JSONDecodeError):
                self.provider_vectors=None
        if self.provider_vectors is None:
            vectors=np.asarray(self.semantic_model.encode([p.searchable_text() for p in providers],normalize_embeddings=True),dtype=np.float32)
            if vectors.ndim!=2 or vectors.shape[0]!=len(providers) or not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors,axis=1),1.0,atol=1e-3):
                raise ValueError("Embedding model returned invalid or unnormalized provider vectors")
            self.provider_vectors=vectors

    def lexical_scores(self,query:MarketplaceQuery,providers:list[Provider])->dict[str,float]:
        vector=self.vectorizer.transform([query.text+" "+" ".join(query.skills+query.specialties)])
        positions=[self.positions[p.provider_id] for p in providers]
        scores=cosine_similarity(vector,self.matrix[positions]).ravel()
        return {p.provider_id:float(scores[i]) for i,p in enumerate(providers)}

    def semantic_scores(self,query:MarketplaceQuery,providers:list[Provider])->dict[str,float]:
        if self.semantic_model is None or self.provider_vectors is None: raise RuntimeError("Local semantic model is not loaded")
        key=query.text
        if key not in self._query_vectors:
            encoded=np.asarray(self.semantic_model.encode([query.text],normalize_embeddings=True),dtype=np.float32)
            if encoded.ndim!=2 or encoded.shape[0]!=1 or encoded.shape[1]!=self.provider_vectors.shape[1] or not np.isfinite(encoded).all() or not np.isclose(np.linalg.norm(encoded[0]),1.0,atol=1e-3):
                raise ValueError("Embedding model returned an invalid query vector")
            self._query_vectors[key]=encoded[0]
            if len(self._query_vectors)>1024:self._query_vectors.popitem(last=False)
        else:self._query_vectors.move_to_end(key)
        vector=self._query_vectors[key]
        return {p.provider_id:float(self.provider_vectors[self.positions[p.provider_id]] @ vector) for p in providers}

    def eligible(self,q:MarketplaceQuery):
        reasons=["active provider",f"category: {q.category}"]
        if q.hard_budget and q.max_rate_usd is not None: reasons.append(f"hard budget ≤ ${q.max_rate_usd:g}/hr")
        if q.must_be_available: reasons.append("availability required")
        if q.location_required: reasons.append("location required")
        if q.experience_required and q.min_experience is not None: reasons.append(f"minimum experience: {q.min_experience} years")
        if q.remote_required: reasons.append("remote delivery required")
        if q.onsite_required: reasons.append("on-site delivery required")
        out=[]
        for p in self.providers:
            if not p.active or p.primary_category!=q.category: continue
            if q.hard_budget and q.max_rate_usd is not None and p.hourly_rate_usd>q.max_rate_usd: continue
            if q.must_be_available and p.availability_status=="unavailable": continue
            if q.onsite_required and not p.onsite_available: continue
            if q.remote_required and not p.remote_available: continue
            if q.location_required and (p.city.casefold()!=(q.city or "").casefold() or p.country.casefold()!=(q.country or "").casefold()): continue
            if q.experience_required and q.min_experience is not None and p.years_experience<q.min_experience: continue
            out.append(p)
        return out,reasons

    def _candidate_data(self,q:MarketplaceQuery,eligible:list[Provider],k:int|None):
        k=self.candidate_k if k is None else k
        if not eligible:return {"lexical":[],"semantic":[],"rules":[],"union":[]},{},{}
        lexical=self.lexical_scores(q,eligible)
        semantic=self.semantic_scores(q,eligible) if self.semantic_model and self.provider_vectors is not None else {}
        top=lambda scores:sorted(scores,key=lambda pid:(-scores[pid],pid))[:k]
        lexids=top(lexical);semids=top(semantic) if semantic else []
        rules={p.provider_id:self.rule_score(features(q,p,lexical[p.provider_id],semantic.get(p.provider_id,0))) for p in eligible}
        ruleids=top(rules);union=list(dict.fromkeys(lexids+semids+ruleids))
        return {"lexical":lexids,"semantic":semids,"rules":ruleids,"union":union},lexical,semantic

    def candidate_sets(self,q:MarketplaceQuery,eligible:list[Provider],k:int|None=None):
        return self._candidate_data(q,eligible,k)[0]

    def retrieve_with_sets(self,q:MarketplaceQuery,eligible:list[Provider],k:int|None=None):
        sets,lexical,semantic=self._candidate_data(q,eligible,k);lookup={p.provider_id:p for p in eligible}
        counts={name:len(ids) for name,ids in sets.items()}
        candidates=[(lookup[pid],lexical[pid],semantic.get(pid,0.0)) for pid in sets['union']]
        return candidates,counts,sets

    def retrieve(self,q:MarketplaceQuery,eligible:list[Provider],k:int|None=None):
        candidates,counts,_=self.retrieve_with_sets(q,eligible,k);return candidates,counts

    @staticmethod
    def rule_score(f):
        return (.22*f.specialty_overlap+.22*f.skill_overlap+.11*f.semantic_score+.12*f.budget_fit+
                .10*f.experience_fit+.07*f.availability_fit+.05*f.location_fit+.04*f.remote_preference_match+.07*f.reliability)
