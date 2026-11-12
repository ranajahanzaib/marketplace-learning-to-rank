import json
from pathlib import Path
import lightgbm as lgb
from fastapi.testclient import TestClient
from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.data.generate import generate
from marketplace_learning_to_rank.ranking.service import RankingService
from marketplace_learning_to_rank.retrieval.search import SearchEngine
from marketplace_learning_to_rank.retrieval.smoke_encoder import SmokeEncoder
from marketplace_learning_to_rank.training.train import train
from marketplace_learning_to_rank.evaluation.run import evaluate

def test_grouped_training_save_reload_and_unseen_provider(tmp_path:Path,monkeypatch):
    data=tmp_path/'data';providers,queries,_,_=generate(4,80,80,output=data)
    engine=SearchEngine(providers,encoder=SmokeEncoder())
    manifest=train(data,tmp_path/'models'/'ranker.txt',engine)
    assert manifest['training_query_count']>0 and manifest['validation_query_count']>0
    assert manifest['training_row_count']>manifest['training_query_count']
    assert len(json.loads((tmp_path/'models'/'feature_schema.json').read_text())['feature_names'])>20
    model=lgb.Booster(model_file=str(tmp_path/'models'/'ranker.txt'))
    service=RankingService(engine,model)
    q=next(q for q in queries if q.category=='Software development')
    result=service.search(q,'lambdamart',10)
    assert result.results and all(__import__('math').isfinite(r.score) for r in result.results)
    import marketplace_learning_to_rank.api.app as api
    monkeypatch.setattr(api,'_load_service',lambda:api.state.update(service=service,manifest=manifest,model_error=None))
    with TestClient(api.app) as client:
        response=client.post('/api/v1/search?strategy=lambdamart&limit=10',json=q.model_dump(mode='json'))
        assert response.status_code==200 and response.json()['results']
        assert response.json()['model_version']==manifest['model_version']
        comparison=client.post('/api/v1/search/compare?strategies=rules,lambdamart&limit=10',json=q.model_dump(mode='json'))
        assert comparison.status_code==200 and comparison.json()['same_candidate_pool'] is True
        assert comparison.json()['strategies']['lambdamart']['results']
    unseen=set(json.loads((data/'provider_holdout.json').read_text()))
    assert unseen and unseen.isdisjoint({row['provider_id'] for row in json.loads((data/'judgments.json').read_text()) if row['query_id'] in {q.query_id for q in queries[:56]}}) is False
