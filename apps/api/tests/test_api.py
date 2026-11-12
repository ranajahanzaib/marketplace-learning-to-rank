from fastapi.testclient import TestClient
from marketplace_learning_to_rank.core.models import Provider
from marketplace_learning_to_rank.ranking.service import RankingService
from marketplace_learning_to_rank.retrieval.search import SearchEngine
import marketplace_learning_to_rank.api.app as api

def test_search_compare_validation_and_provider_routes(monkeypatch):
    provider=Provider(provider_id='p1',display_name='Avery North',headline='React specialist',description='React and TypeScript for SaaS',primary_category='Software development',specialties=['React'],skills=['TypeScript'],hourly_rate_usd=70,years_experience=8,city='Austin',country='United States',remote_available=True,onsite_available=True,availability_status='available',completed_projects=12,average_rating=4.7,review_count=16,response_rate=.9,response_time_hours=3,verified_status=True,portfolio_tags=['SaaS'],industry_expertise=['technology'])
    service=RankingService(SearchEngine([provider],with_semantic=False))
    monkeypatch.setattr(api,'_load_service',lambda:api.state.update(service=service,manifest=None,model_error=None))
    body={"text":"Need a React TypeScript specialist","category":"Software development","specialties":["React"],"skills":["TypeScript"],"max_rate_usd":80,"hard_budget":True}
    with TestClient(api.app) as client:
        response=client.post('/api/v1/search?strategy=rules',json=body)
        assert response.status_code==200 and response.json()['results'][0]['provider']['provider_id']=='p1'
        assert response.json()['timings_ms']['total_server']>=0
        over_budget={**body,'max_rate_usd':20}
        empty=client.post('/api/v1/search?strategy=rules',json=over_budget)
        assert empty.status_code==200 and empty.json()['results']==[] and empty.json()['eligible_count']==0
        invalid=client.post('/api/v1/search?strategy=unknown',json=body)
        assert invalid.status_code==400
        comparison=client.post('/api/v1/search/compare?strategies=rules,semantic,lambdamart',json=body)
        assert comparison.status_code==200 and comparison.json()['same_candidate_pool'] is True
        assert comparison.json()['strategies']['semantic']['available'] is False
        assert client.get('/api/v1/providers/p1').status_code==200
        preflight=client.options('/api/v1/experiments/test-abc/simulation',headers={'origin':'http://localhost:5173','access-control-request-method':'DELETE'})
        assert preflight.status_code==200 and 'DELETE' in preflight.headers['access-control-allow-methods']
        loopback=client.options('/api/v1/search',headers={'origin':'http://127.0.0.1:5173','access-control-request-method':'POST'})
        assert loopback.status_code==200 and loopback.headers['access-control-allow-origin']=='http://127.0.0.1:5173'
