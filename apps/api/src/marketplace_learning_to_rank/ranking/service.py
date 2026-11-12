import time,math
from marketplace_learning_to_rank.core.models import MarketplaceQuery, SearchResponse, SearchResult
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES,features,vector
from marketplace_learning_to_rank.retrieval.search import MODEL_ID,SearchEngine

class RankingService:
    def __init__(self,engine:SearchEngine,model=None):self.engine,self.model=engine,model;self.model_uses_semantic=True
    def search(self,q:MarketplaceQuery,strategy="rules",limit=20):
        started=time.perf_counter();eligible,constraints=self.engine.eligible(q);eligibility_done=time.perf_counter()
        candidates,counts=self.engine.retrieve(q,eligible);retrieval_done=time.perf_counter()
        return self.rank_candidates(q,strategy,candidates,counts,len(eligible),constraints,limit,started,eligibility_done,retrieval_done)
    def rank_candidates(self,q:MarketplaceQuery,strategy:str,candidates:list,counts:dict,eligible_count:int,constraints:list[str],limit:int=20,started:float|None=None,eligibility_done:float|None=None,retrieval_done:float|None=None):
        if strategy not in {"rules","semantic","lambdamart"}:raise ValueError("strategy must be rules, semantic, or lambdamart")
        if strategy=="semantic" and self.engine.model_id!=MODEL_ID:raise ValueError("Semantic ranking requires the local all-MiniLM-L6-v2 model. Run `marketplace_learning_to_rank embeddings build`.")
        if strategy=="lambdamart" and self.model is None:raise ValueError("LambdaMART model is not trained; run `marketplace_learning_to_rank train`.")
        started=started or time.perf_counter();eligibility_done=eligibility_done or started;retrieval_done=retrieval_done or eligibility_done
        prepared=[]
        for p,lex,sem in candidates:
            if strategy=="lambdamart" and not self.model_uses_semantic:sem=0.0
            prepared.append((p,features(q,p,lex,sem)))
        feature_done=time.perf_counter();matrix=[vector(f) for _,f in prepared];contributions=[{} for _ in prepared]
        if strategy=="lambdamart" and matrix:
            scores=self.model.predict(matrix)
            try:
                raw=self.model.predict(matrix,pred_contrib=True)
                for i,row in enumerate(raw):contributions[i]={name:float(row[j]) for j,name in enumerate(FEATURE_NAMES) if abs(float(row[j]))>=.001}
            except (TypeError,ValueError):pass
        elif strategy=="rules":scores=[self.engine.rule_score(f) for _,f in prepared]
        else:scores=[f.semantic_score for _,f in prepared]
        rows=[]
        for i,((p,f),score) in enumerate(zip(prepared,scores)):
            explanation=[]
            if strategy=="lambdamart" and contributions[i]:
                positive=sorted(((n,v) for n,v in contributions[i].items() if v>0),key=lambda x:-x[1])[:3]
                negative=sorted(((n,v) for n,v in contributions[i].items() if v<0),key=lambda x:x[1])[:2]
                explanation += [f"supports score: {n.replace('_',' ')} ({v:+.3f})" for n,v in positive]
                explanation += [f"reduces score: {n.replace('_',' ')} ({v:+.3f})" for n,v in negative]
            else:
                for key,label in [("specialty_overlap","specialty match"),("skill_overlap","skill overlap"),("budget_fit","budget fit"),("experience_fit","experience fit"),("availability_fit","availability"),("reliability","reliability")]:
                    value=getattr(f,key)
                    if value>=.55:explanation.append(f"{label}: {value:.2f}")
            if f.cold_start:explanation.append("new provider: no review history")
            if not math.isfinite(float(score)):raise RuntimeError("Ranker produced a non-finite score")
            rows.append((float(score),p,f,explanation,contributions[i]))
        ranking_done=time.perf_counter();rows.sort(key=lambda x:(-x[0],x[1].provider_id))
        results=[SearchResult(provider=p,score=round(score,6),rank=i+1,features=f,explanation=why,feature_contributions=contrib)
                 for i,(score,p,f,why,contrib) in enumerate(rows[:limit])]
        return SearchResponse(strategy=strategy,results=results,eligible_count=eligible_count,candidate_counts=counts,
          constraints_applied=constraints,timings_ms={"eligibility":(eligibility_done-started)*1000,"retrieval":(retrieval_done-eligibility_done)*1000,
          "features":(feature_done-retrieval_done)*1000,"ranking":(ranking_done-feature_done)*1000,"total_server":(ranking_done-started)*1000},
          message="No providers meet these constraints. Relax a filter explicitly and try again." if not eligible_count else None)
