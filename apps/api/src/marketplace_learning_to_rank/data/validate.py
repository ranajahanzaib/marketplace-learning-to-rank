from __future__ import annotations
import json,re
from collections import Counter
from statistics import median
from pathlib import Path
from marketplace_learning_to_rank.core.models import MarketplaceQuery,Provider
from marketplace_learning_to_rank.data.generate import CATALOG
from marketplace_learning_to_rank.data.splits import intent_key
from marketplace_learning_to_rank.retrieval.search import SearchEngine

def validate(data_dir:Path)->dict:
    providers=[Provider.model_validate(x) for x in json.loads((data_dir/'providers.json').read_text())]
    queries=[MarketplaceQuery.model_validate(x) for x in json.loads((data_dir/'queries.json').read_text())]
    judgments=json.loads((data_dir/'judgments.json').read_text());splits=json.loads((data_dir/'splits.json').read_text())
    pids=[p.provider_id for p in providers];pid_set=set(pids);qids=[q.query_id for q in queries];qid_set=set(qids)
    if len(pid_set)!=len(pids):raise ValueError("Duplicate provider IDs")
    for provider in providers:
        if provider.primary_category not in CATALOG:raise ValueError(f"Unknown provider category: {provider.primary_category}")
        if not provider.headline.strip() or not provider.description.strip():raise ValueError(f"Empty profile text: {provider.provider_id}")
        if not provider.city.strip() or not provider.country.strip():raise ValueError(f"Incomplete location: {provider.provider_id}")
        if provider.review_count==0 and provider.average_rating is not None:raise ValueError(f"Rating without reviews: {provider.provider_id}")
    if None in qids or len(qid_set)!=len(queries):raise ValueError("Missing or duplicate query IDs")
    normalized=[re.sub(r"\W+"," ",q.text.casefold()).strip() for q in queries]
    if len(set(normalized))!=len(normalized):raise ValueError("Duplicate normalized query texts across groups")
    if set(splits)!=qid_set:raise ValueError("Split map does not exactly cover query IDs")
    if any(value not in {"train","validation","test"} for value in splits.values()):raise ValueError("Unknown query split")
    intent_partitions={}
    for query in queries:
        if query.category not in CATALOG:raise ValueError(f"Unknown query category: {query.category}")
        previous=intent_partitions.setdefault(intent_key(query),splits[query.query_id])
        if previous!=splits[query.query_id]:raise ValueError("Near-identical structured query intent crosses train/validation/test partitions")
    if not {"train","validation","test"}.issubset(set(splits.values())):raise ValueError("Missing train, validation, or test partition")
    seen=set();byq={qid:set() for qid in qids};label_counts=Counter()
    for row in judgments:
        key=(row['query_id'],row['provider_id'])
        if key in seen:raise ValueError(f"Duplicate query/provider judgment: {key}")
        if row['query_id'] not in qid_set or row['provider_id'] not in pid_set:raise ValueError(f"Unknown judgment reference: {key}")
        if isinstance(row['label'],bool) or int(row['label']) not in range(5):raise ValueError(f"Invalid relevance label: {row['label']}")
        seen.add(key);byq[row['query_id']].add(row['provider_id']);label_counts[str(row['label'])]+=1
    holdout_path=data_dir/"provider_holdout.json";heldout=set(json.loads(holdout_path.read_text())) if holdout_path.exists() else set()
    if not heldout.issubset(pid_set):raise ValueError("Unknown provider ID in cold-start holdout")
    settings=json.loads((data_dir/"manifest.json").read_text()).get("settings",{})
    engine=SearchEngine(providers,with_semantic=False,candidate_k=int(settings.get("candidate_count",60)))
    coverage=[]
    for q in queries:
        eligible,_=engine.eligible(q);expected={p.provider_id for p in eligible};observed=byq[q.query_id]
        if observed!=expected:raise ValueError(f"Judgment universe for {q.query_id} differs: {len(observed)} judged / {len(expected)} eligible")
        coverage.append(len(observed)/max(1,len(eligible)))
    if any(p.hourly_rate_usd<=0 or p.years_experience<0 for p in providers):raise ValueError("Invalid provider numeric fields")
    category_counts=Counter(p.primary_category for p in providers)
    query_category_counts=Counter(q.category for q in queries)
    cold=sum(p.review_count==0 for p in providers)
    split_counts={name:sum(value==name for value in splits.values()) for name in ('train','validation','test')}
    rates=sorted(p.hourly_rate_usd for p in providers);rating_counts=Counter(str(p.average_rating) if p.average_rating is not None else "missing" for p in providers)
    budget_bins={"≤50":sum(rate<=50 for rate in rates),"51–75":sum(50<rate<=75 for rate in rates),"76–100":sum(75<rate<=100 for rate in rates),"101–150":sum(100<rate<=150 for rate in rates),">150":sum(rate>150 for rate in rates)}
    availability_counts=Counter(p.availability_status for p in providers);region_counts=Counter(f"{p.city}, {p.country}" for p in providers)
    return {"valid":True,"seed":json.loads((data_dir/'manifest.json').read_text()).get('seed'),"provider_count":len(providers),"query_count":len(queries),"judgment_count":len(judgments),
      "split_query_counts":split_counts,"provider_category_counts":dict(category_counts),"query_category_counts":dict(query_category_counts),"label_counts":dict(label_counts),
      "cold_start_provider_count":cold,"cold_start_provider_fraction":cold/max(1,len(providers)),"unseen_provider_holdout_count":len(heldout),
      "providers_without_review_history":sum(p.review_count==0 for p in providers),"providers_without_response_history":sum(p.response_rate is None for p in providers),"rating_counts":dict(rating_counts),"availability_counts":dict(availability_counts),"region_counts":dict(region_counts),"hourly_rate_usd":{"min":rates[0],"median":median(rates),"max":rates[-1],"distribution":budget_bins},
      "mean_judgment_coverage_of_eligible_universe":sum(coverage)/max(1,len(coverage)),"zero_eligible_query_count":sum(not engine.eligible(q)[0] for q in queries),"duplicate_query_texts":0}
