from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.data.generate import generate
from marketplace_learning_to_rank.evaluation.metrics import bootstrap_mean,ndcg,recall_at_k,mrr_at_k,precision_at_k
from marketplace_learning_to_rank.ranking.features import FEATURE_NAMES,features,vector
from marketplace_learning_to_rank.retrieval.search import SearchEngine
from marketplace_learning_to_rank.retrieval.smoke_encoder import SmokeEncoder
from marketplace_learning_to_rank.ranking.service import RankingService
import pytest

def make_provider(**overrides):
    data=dict(provider_id='p1',display_name='Avery North',headline='React specialist',description='React and TypeScript for SaaS',primary_category='Software development',specialties=['React'],skills=['TypeScript'],hourly_rate_usd=120,years_experience=9,city='Austin',country='United States',remote_available=True,onsite_available=True,availability_status='available',completed_projects=20,average_rating=None,review_count=0,response_rate=None,response_time_hours=None,verified_status=True,portfolio_tags=['SaaS'],industry_expertise=['technology'])
    data.update(overrides);return Provider(**data)

def test_metrics_and_bootstrap():
    assert ndcg([3,2,1],3)==1
    assert recall_at_k(['a','b'],['b','c'],1)==0
    assert mrr_at_k([0,3],10)==.5
    assert precision_at_k([3,2],2,3)==.5
    assert bootstrap_mean([.2,.4],seed=5)==bootstrap_mean([.2,.4],seed=5)
    assert ndcg([0,0],10)==0 and recall_at_k([],[],10)==0

def test_generation_reproducible_and_unique_queries():
    a=generate(9,30,20);b=generate(9,30,20)
    assert [p.model_dump() for p in a[0]]==[p.model_dump() for p in b[0]]
    assert a[3]==b[3]
    assert len({q.text.casefold() for q in a[1]})==20

def test_structured_intents_never_cross_query_splits():
    _,queries,_,splits=generate(13,40,100)
    partitions={}
    for query in queries:
        key=(query.category,tuple(sorted(x.casefold() for x in query.specialties)),tuple(sorted(x.casefold() for x in query.skills)))
        assert key not in partitions or partitions[key]==splits[query.query_id]
        partitions[key]=splits[query.query_id]
    assert set(splits.values())=={'train','validation','test'}

def test_hard_budget_location_remote_and_availability_never_relax():
    p=make_provider(hourly_rate_usd=120)
    engine=SearchEngine([p],with_semantic=False)
    base=dict(text='Need a React developer',category='Software development',specialties=['React'],skills=['TypeScript'])
    q=MarketplaceQuery(**base,max_rate_usd=50,hard_budget=True)
    assert engine.eligible(q)[0]==[]
    q=MarketplaceQuery(**base,city='Boston',country='United States',location_required=True)
    assert engine.eligible(q)[0]==[]
    q=MarketplaceQuery(**base,remote_required=True)
    assert engine.eligible(q)[0]==[p]
    q=MarketplaceQuery(**base,remote_preferred=True)
    assert engine.eligible(q)[0]==[p]  # preference does not become a hard filter
    q=MarketplaceQuery(**base,onsite_required=True)
    assert engine.eligible(q)[0]==[p]
    assert SearchEngine([make_provider(onsite_available=False)],with_semantic=False).eligible(q)[0]==[]
    q=MarketplaceQuery(**base,min_experience=10,experience_required=True)
    assert engine.eligible(q)[0]==[]
    q=MarketplaceQuery(**base,must_be_available=True)
    assert engine.eligible(q)[0]==[p]
    assert SearchEngine([make_provider(availability_status='unavailable')],with_semantic=False).eligible(q)[0]==[]
    assert SearchEngine([make_provider(remote_available=False)],with_semantic=False).eligible(MarketplaceQuery(**base,remote_required=True))[0]==[]
    with pytest.raises(ValueError):MarketplaceQuery(**base,location_required=True)

def test_features_explicitly_preserve_missing_history():
    p=make_provider()
    q=MarketplaceQuery(text='Need React TypeScript',category='Software development',specialties=['React'],skills=['TypeScript'],max_rate_usd=100)
    f=features(q,p)
    assert f.cold_start==1 and f.rating==3.5 and f.adjusted_rating==3.5 and f.rating_confidence==0
    assert f.rating_missing==1
    assert f.response_history_missing==1 and f.has_project_history==1
    assert len(vector(f))==len(FEATURE_NAMES) and all(map(lambda n:hasattr(f,n),FEATURE_NAMES))

def test_retrieval_union_is_unique_and_query_cache_uses_text():
    providers=[make_provider(),make_provider(provider_id='p2',headline='Bookkeeping specialist',description='QuickBooks bookkeeping and reconciliation',primary_category='Software development',specialties=['Bookkeeping'],skills=['QuickBooks']),make_provider(provider_id='p3',headline='React and TypeScript engineer',description='React SaaS application development',skills=['TypeScript','React'])]
    engine=SearchEngine(providers,encoder=SmokeEncoder(),candidate_k=2)
    q1=MarketplaceQuery(query_id='shared-id',text='React TypeScript specialist',category='Software development',specialties=['React'],skills=['TypeScript'])
    q2=MarketplaceQuery(query_id='shared-id',text='QuickBooks reconciliation bookkeeping',category='Software development',specialties=['Bookkeeping'],skills=['QuickBooks'])
    first=engine.semantic_scores(q1,providers);second=engine.semantic_scores(q2,providers)
    assert first!=second
    lexical=engine.lexical_scores(q1,providers)
    assert lexical['p1']>lexical['p2']
    eligible,_=engine.eligible(q1);candidates,counts=engine.retrieve(q1,eligible)
    ids=[provider.provider_id for provider,_,_ in candidates]
    assert len(ids)==len(set(ids)) and counts['union']==len(ids)
    assert RankingService(engine).search(q1,'rules',10).results
