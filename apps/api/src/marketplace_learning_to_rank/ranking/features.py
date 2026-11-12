from datetime import date
import re
from marketplace_learning_to_rank.core.models import CandidateFeatures, MarketplaceQuery, Provider

FEATURE_VERSION = "1.1.0"
FEATURE_NAMES = list(CandidateFeatures.model_fields)
REFERENCE_DATE = date(2026, 1, 1)

def features(q: MarketplaceQuery, p: Provider, lexical: float = 0, semantic: float = 0) -> CandidateFeatures:
    qskills={s.casefold() for s in q.skills}; pskills={s.casefold() for s in p.skills}
    qspec={s.casefold() for s in q.specialties}; pspec={s.casefold() for s in p.specialties}
    overlap=len(qskills & pskills)/max(1,len(qskills)); specialty=float(bool(qspec & pspec))
    qtokens=set(re.findall(r"[a-z0-9]+", q.text.casefold())); ptokens=set(re.findall(r"[a-z0-9]+", p.searchable_text().casefold()))
    token_overlap=len(qtokens & ptokens)/max(1,len(qtokens))
    budget=q.max_rate_usd
    ratio=(p.hourly_rate_usd/budget if budget else 0.0)
    within=float(budget is None or p.hourly_rate_usd<=budget)
    budget_fit=(1.0 if budget is None else max(0.0,1-abs(p.hourly_rate_usd-budget)/budget))
    min_exp=q.min_experience or 0
    exp_gap=float(max(0,min_exp-p.years_experience))
    exp_satisfied=float(q.min_experience is None or p.years_experience>=min_exp)
    avail_code={"unavailable":0.0,"limited":0.5,"available":1.0}[p.availability_status]
    days=float(max(0,(p.next_available_date-REFERENCE_DATE).days)) if p.next_available_date else 90.0
    avail_fit=avail_code if q.must_be_available else max(avail_code, .5 if days<=30 else 0)
    city=float(bool(q.city and p.city.casefold()==q.city.casefold()))
    country=float(bool(q.country and p.country.casefold()==q.country.casefold()))
    remote=float(p.remote_available)
    onsite=float(p.onsite_available)
    remote_pref=(0.5 if q.remote_preferred is None else float(p.remote_available==q.remote_preferred))
    loc=city if q.city else country if q.country else 1.0
    n=p.review_count; confidence=n/(n+10) if n else 0.0
    rating=p.average_rating if p.average_rating is not None else 3.5
    adjusted=(confidence*rating+(1-confidence)*3.5)
    return CandidateFeatures(specialty_overlap=specialty,skill_overlap=overlap,lexical_score=float(lexical),
        semantic_score=float(semantic),exact_category_match=float(p.primary_category==q.category),text_token_overlap=token_overlap,
        hourly_rate=p.hourly_rate_usd,requested_budget=budget or 0.0,rate_to_budget_ratio=ratio,budget_fit=budget_fit,within_budget=within,
        experience_years=p.years_experience,experience_gap=exp_gap,experience_satisfied=exp_satisfied,experience_fit=min(1.0,p.years_experience/10.0),completed_projects=p.completed_projects,
        availability_state=avail_code,days_until_available=days,availability_fit=avail_fit,same_city=city,same_country=country,
        remote_compatible=remote,remote_preference_match=remote_pref,onsite_compatible=onsite,location_fit=loc,rating=rating,rating_missing=float(p.average_rating is None),review_count=n,
        adjusted_rating=adjusted,rating_confidence=confidence,response_rate=p.response_rate or 0.0,
        response_time_hours=p.response_time_hours or 0.0,verified=float(p.verified_status),
        provider_tenure_days=float(max(0,(REFERENCE_DATE-p.created_at).days)),cold_start=float(n==0),
        has_review_history=float(n>0),has_project_history=float(p.completed_projects>0),response_history_missing=float(p.response_rate is None))

def vector(f: CandidateFeatures) -> list[float]:
    values=[float(getattr(f,name)) for name in FEATURE_NAMES]
    if any(not __import__('math').isfinite(x) for x in values): raise ValueError("Non-finite feature value")
    return values
