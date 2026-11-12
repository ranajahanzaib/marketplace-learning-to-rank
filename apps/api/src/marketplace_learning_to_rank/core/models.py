from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Provider(BaseModel):
    provider_id: str
    display_name: str
    headline: str
    description: str
    primary_category: str
    specialties: list[str]
    skills: list[str]
    hourly_rate_usd: float = Field(gt=0)
    years_experience: int = Field(ge=0)
    city: str
    country: str
    remote_available: bool
    onsite_available: bool
    availability_status: Literal["available", "limited", "unavailable"]
    next_available_date: date | None = None
    completed_projects: int = Field(ge=0)
    average_rating: float | None = Field(default=None, ge=1, le=5)
    review_count: int = Field(ge=0)
    response_rate: float | None = Field(default=None, ge=0, le=1)
    response_time_hours: float | None = Field(default=None, ge=0)
    verified_status: bool
    portfolio_tags: list[str]
    industry_expertise: list[str]
    created_at: date = date(2020, 1, 1)
    updated_at: date = date(2026, 1, 1)
    active: bool = True

    def searchable_text(self) -> str:
        return " ".join([self.headline, self.description, self.primary_category,
                         *self.specialties, *self.skills, *self.portfolio_tags,
                         *self.industry_expertise])

class MarketplaceQuery(BaseModel):
    query_id: str | None = None
    text: str = Field(min_length=3, max_length=1200)
    category: str = Field(min_length=1,max_length=120)
    specialties: list[str] = Field(default_factory=list,max_length=40)
    skills: list[str] = Field(default_factory=list,max_length=80)
    max_rate_usd: float | None = Field(default=None, gt=0, le=10000)
    hard_budget: bool = False
    remote_preferred: bool | None = None
    remote_required: bool = False
    onsite_required: bool = False
    city: str | None = Field(default=None,max_length=120)
    country: str | None = Field(default=None,max_length=120)
    location_required: bool = False
    min_experience: int | None = Field(default=None, ge=0, le=80)
    experience_required: bool = False
    must_be_available: bool = False

    @model_validator(mode="after")
    def location_constraints_need_location(self):
        if self.location_required and (not self.city or not self.country):
            raise ValueError("city and country are required when location_required is true")
        if self.remote_required and self.onsite_required:
            raise ValueError("remote and on-site cannot both be mandatory")
        return self

class CandidateFeatures(BaseModel):
    specialty_overlap: float
    skill_overlap: float
    lexical_score: float
    semantic_score: float
    exact_category_match: float
    text_token_overlap: float
    hourly_rate: float
    requested_budget: float
    rate_to_budget_ratio: float
    budget_fit: float
    within_budget: float
    experience_years: float
    experience_gap: float
    experience_satisfied: float
    experience_fit: float
    completed_projects: float
    availability_state: float
    days_until_available: float
    availability_fit: float
    same_city: float
    same_country: float
    remote_compatible: float
    remote_preference_match: float
    onsite_compatible: float
    location_fit: float
    rating: float
    rating_missing: float
    review_count: float
    adjusted_rating: float
    rating_confidence: float
    response_rate: float
    response_time_hours: float
    verified: float
    provider_tenure_days: float
    cold_start: float
    has_review_history: float
    has_project_history: float
    response_history_missing: float

class SearchResult(BaseModel):
    provider: Provider
    score: float
    rank: int
    features: CandidateFeatures
    explanation: list[str]
    feature_contributions: dict[str, float] = Field(default_factory=dict)

class SearchResponse(BaseModel):
    request_id: str | None = None
    model_version: str | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    synthetic_demo_data: bool = True
    strategy: str
    results: list[SearchResult]
    eligible_count: int
    candidate_counts: dict[str, int]
    constraints_applied: list[str]
    message: str | None = None
