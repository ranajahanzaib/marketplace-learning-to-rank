from __future__ import annotations
import json, random
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from marketplace_learning_to_rank.core.models import Provider, MarketplaceQuery
from marketplace_learning_to_rank.data.splits import grouped_split

CATALOG = {
 "Software development": {"React": ["TypeScript", "Next.js", "Node.js", "GraphQL"], "Mobile apps": ["Swift", "Kotlin", "React Native"], "Backend systems": ["Python", "FastAPI", "PostgreSQL", "AWS"], "Machine learning": ["Python", "scikit-learn", "PyTorch", "MLflow"]},
 "Design": {"Product design": ["Figma", "prototyping", "design systems"], "UX research": ["interviews", "usability testing", "accessibility"]},
 "Marketing": {"SEO": ["technical SEO", "content strategy", "analytics"], "Paid acquisition": ["Google Ads", "Meta Ads", "attribution"]},
 "Business services": {"Bookkeeping": ["QuickBooks", "Xero", "reconciliation"], "Cybersecurity": ["penetration testing", "OWASP", "cloud security"]},
}
REGIONS = [("Austin", "United States"), ("Toronto", "Canada"), ("London", "United Kingdom"), ("Lahore", "Pakistan"), ("Berlin", "Germany"), ("Melbourne", "Australia")]
FIRST = ["Avery", "Jordan", "Morgan", "Riley", "Casey", "Taylor", "Quinn", "Cameron", "Drew", "Sage", "Robin", "Alex"]
LAST = ["North", "River", "Vale", "Stone", "Wells", "Park", "Reed", "Cedar", "Lane", "Shore"]


def generate(seed: int = 42, provider_count: int = 300, query_count: int = 400,
             candidate_count: int = 80, cold_start_fraction: float = .15,
             label_noise: float = .08, output: Path | None = None, categories: list[str] | None = None, regions: list[tuple[str,str]] | None = None):
    if provider_count<2 or query_count<3:raise ValueError("provider_count must be ≥2 and query_count must be ≥3")
    if candidate_count<1 or candidate_count>500:raise ValueError("candidate_count must be between 1 and 500")
    if not 0<=cold_start_fraction<=0.8:raise ValueError("cold_start_fraction must be between 0 and 0.8")
    if not 0<=label_noise<=1:raise ValueError("label_noise must be between 0 and 1")
    rng = random.Random(seed)
    selected_categories=categories or list(CATALOG)
    if not selected_categories:raise ValueError("At least one category is required")
    if set(selected_categories)-set(CATALOG):raise ValueError(f"Unknown categories: {sorted(set(selected_categories)-set(CATALOG))}")
    region_pool=regions or REGIONS
    if not region_pool:raise ValueError("At least one region is required")
    providers = []
    skills_by_cat = [(c, s, skills) for c, specs in CATALOG.items() if c in selected_categories for s, skills in specs.items()]
    rare_specialties={"Machine learning","Cybersecurity","UX research","Bookkeeping","Paid acquisition"}
    specialty_weights=[.2 if specialty in rare_specialties else 1.0 for _,specialty,_ in skills_by_cat]
    for i in range(provider_count):
        cat, specialty, skills = rng.choices(skills_by_cat,weights=specialty_weights,k=1)[0]
        experience = max(0, int(rng.gauss(7, 5)))
        base = {"Software development": 68, "Design": 58, "Marketing": 52, "Business services": 62}[cat]
        rate = max(20, round(base + experience * rng.uniform(2, 5) + rng.gauss(0, 18)))
        cold = rng.random() < cold_start_fraction
        reviews = 0 if cold else max(0, int(rng.expovariate(1 / 22)))
        rating = None if reviews == 0 else round(min(5, max(3.2, rng.gauss(4.65, .3))), 2)
        city, country = rng.choice(region_pool)
        avail = rng.choices(["available", "limited", "unavailable"], [0.61, .27, .12])[0]
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)} {i:03d}"
        provider = Provider(provider_id=f"p{i:05d}", display_name=name,
            headline=f"{specialty} specialist for growing teams", description=f"{name} helps {cat.lower()} clients with {', '.join(skills[:3])}. Recent work includes {rng.choice(['SaaS platforms', 'local businesses', 'financial services', 'health technology', 'independent teams'])}.",
            primary_category=cat, specialties=[specialty], skills=skills[:], hourly_rate_usd=rate,
            years_experience=experience, city=city, country=country, remote_available=rng.random() < .82,
            onsite_available=rng.random() < .35, availability_status=avail,
            next_available_date=date(2026, 1, 1) + timedelta(days=rng.randint(0, 35)),
            completed_projects=0 if cold else max(0, int(experience * rng.uniform(1, 5))),
            average_rating=rating, review_count=reviews, response_rate=None if cold else round(rng.uniform(.65, .99), 2),
            response_time_hours=None if cold else round(rng.uniform(1, 36), 1), verified_status=rng.random() < .55,
            portfolio_tags=[specialty, rng.choice(["SaaS", "enterprise", "startup", "e-commerce"])],
            industry_expertise=[rng.choice(["technology", "finance", "health", "retail", "education"])],
            created_at=date(2026,1,1)-timedelta(days=rng.randint(0,900) if cold else rng.randint(900,3000)),updated_at=date(2026,1,1))
        providers.append(provider)

    holdout_rng=random.Random(seed+991);provider_holdout=set(holdout_rng.sample([p.provider_id for p in providers],max(1,int(provider_count*.15)))) if provider_count>1 else set()
    queries, judgments = [], []
    query_texts=set()
    contexts=["validate a product launch", "replace a legacy workflow", "improve customer onboarding", "build an internal platform", "ship a new service", "reduce manual operations", "modernize an existing system", "support an expansion", "improve reporting", "prepare a security review", "refresh a customer journey", "connect business systems", "scale a growing product", "audit current performance", "deliver a research sprint", "prototype a new concept", "migrate core infrastructure", "support a seasonal campaign", "improve data quality", "launch a mobile experience", "strengthen operational resilience", "prepare a market entry", "refresh a brand system", "improve conversion tracking", "document a technical platform"]
    industries=["SaaS", "finance", "health technology", "retail", "education", "logistics", "professional services", "climate technology"]
    for qid in range(query_count):
        cat, specialty, skills = rng.choices(skills_by_cat,weights=specialty_weights,k=1)[0]
        budget = rng.choice([45, 65, 90, 130])
        city, country = rng.choice(region_pool)
        remote = rng.choice([True, True, False])
        phrase_templates=[f"Looking for {specialty.lower()} help using {skills[0]} to {{context}} for a {{industry}} team in {city}.",
                          f"Need an experienced {specialty.lower()} provider who knows {skills[0]} to {{context}} for a {{industry}} team.",
                          f"Seeking {skills[0]} expertise for a {{industry}} team working to {{context}}."]
        for _ in range(200):
            text=rng.choice(phrase_templates).format(context=rng.choice(contexts),industry=rng.choice(industries))
            normalized=" ".join(text.casefold().split())
            if normalized not in query_texts:break
        else: raise ValueError("Could not generate a unique search request; reduce query_count")
        query_texts.add(normalized)
        q = MarketplaceQuery(query_id=f"q{qid:05d}", text=text, category=cat,
            specialties=[specialty], skills=rng.sample(skills, min(2, len(skills))), max_rate_usd=budget,
            hard_budget=(qid % 5 == 0), remote_preferred=remote, city=city, country=country,
            location_required=(qid % 13 == 0), min_experience=rng.choice([None, 2, 4]),
            experience_required=False, must_be_available=(qid % 17 == 0))
        queries.append(q)
        # Full eligible universe labels, with preference interactions and noise distinct from rules.
        eligible = [p for p in providers if p.active and p.primary_category == cat and
                    not (q.hard_budget and p.hourly_rate_usd > budget) and
                    not (q.must_be_available and p.availability_status == "unavailable") and
                    not (q.location_required and (p.city != city or p.country != country))]
        for p in eligible:
            spec = float(specialty.lower() in " ".join(p.specialties).lower())
            skill = len(set(x.lower() for x in q.skills) & set(x.lower() for x in p.skills)) / max(1, len(q.skills))
            budget_fit = max(0, 1 - max(0, p.hourly_rate_usd - budget) / max(budget, 1))
            exp_fit = min(1, p.years_experience / 10)
            # Nonlinear style: preference mix rotates; pairwise skill + project-history interaction.
            preference = qid % 4
            raw = (1.6 * spec + (1.5 if preference in (0, 2) else .8) * skill +
                   (1.2 if preference in (1, 3) else .6) * budget_fit +
                   (.7 if preference in (0, 3) else 1.1) * exp_fit +
                   (.5 if p.availability_status == "available" else .1) +
                   (.4 if p.remote_available == remote else 0) +
                   (.35 if (p.completed_projects > 20 and skill > .5) else 0) +
                   (.25 if p.average_rating and p.average_rating > 4.7 and p.review_count > 10 else 0))
            raw += rng.gauss(0, label_noise * 3)
            label = max(0, min(4, round(raw - .9)))
            judgments.append({"query_id": q.query_id, "provider_id": p.provider_id, "label": label})

    split=grouped_split(queries,seed)
    if output:
        output.mkdir(parents=True, exist_ok=True)
        (output / "providers.json").write_text(json.dumps([p.model_dump(mode="json") for p in providers], indent=2))
        (output / "queries.json").write_text(json.dumps([q.model_dump(mode="json") for q in queries], indent=2))
        (output / "judgments.json").write_text(json.dumps(judgments, separators=(",", ":")))
        (output / "splits.json").write_text(json.dumps(split, indent=2))
        (output / "provider_holdout.json").write_text(json.dumps(sorted(provider_holdout),indent=2))
        (output / "manifest.json").write_text(json.dumps({"generator_version":"0.1.0", "seed":seed,"provider_count":provider_count,"query_count":query_count,"judgment_count":len(judgments),"schema_version":1,"provider_holdout_count":len(provider_holdout),"settings":{"cold_start_fraction":cold_start_fraction,"label_noise":label_noise,"candidate_count":candidate_count,"specialty_weights":{"rare":0.2,"common":1.0},"categories":sorted(selected_categories),"regions":region_pool},"created_at":datetime.now(timezone.utc).isoformat(),"labeling":"Simulated graded relevance; not observed behavior.","synthetic_limitations":"Fictitious providers and simulated customer preference; not human judgments or booking outcomes."}, indent=2))
    return providers, queries, judgments, split
