from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TriageDecision = Literal["contact_candidate", "inspect", "ignore"]
ManualDecision = Literal["inspect", "ignore", "contact"]
ExtractionStatus = Literal["pending", "success", "partial", "blocked", "failed"]
JudgeOpinion = Literal["positive", "neutral", "negative"]


class ParsedAlert(BaseModel):
    message_id: str
    sender: str
    subject: str
    received_at: datetime | None = None
    raw_text: str
    raw_html: str | None = None
    listing_urls: list[str]


class MissingInformation(BaseModel):
    field: str
    reason: str
    critical: bool = False


class FactorScore(BaseModel):
    score: float = Field(ge=0, le=10)
    weight: float = Field(gt=0)
    evidence: str
    source: Literal["deterministic", "llm", "fallback"]
    missing: bool = False


class ExtractedListing(BaseModel):
    homegate_id: str
    url: str
    title: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    rent_chf: float | None = None
    extra_costs_chf: float | None = None
    total_cost_chf: float | None = None
    rooms: float | None = None
    living_space_sqm: float | None = None
    available_from: date | None = None
    last_refurbishment_year: int | None = None
    year_built: int | None = None
    listing_type: str | None = None
    is_roommate_listing: bool | None = None
    public_transport_walk_minutes: int | None = None
    public_transport_name: str | None = None
    supermarket_walk_minutes: int | None = None
    supermarket_name: str | None = None
    office_commute_minutes: int | None = None
    description: str | None = None
    raw_text: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    extraction_status: ExtractionStatus = "pending"
    extraction_error: str | None = None


class LLMReview(BaseModel):
    vfm_score: float = Field(ge=0, le=10)
    kitchen_quality_score: float = Field(ge=0, le=10)
    condition_score: float = Field(ge=0, le=10)
    judge_opinion: JudgeOpinion
    judge_rationale: str
    confidence: float = Field(ge=0, le=1)
    summary_lines: list[str] = Field(min_length=5, max_length=5)
    missing_information: list[MissingInformation] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    deterministic_score: float = Field(ge=0, le=10)
    total_score: float = Field(ge=0, le=10)
    triage_decision: TriageDecision
    judge_opinion: JudgeOpinion
    judge_rationale: str
    confidence: float = Field(ge=0, le=1)
    summary_lines: list[str] = Field(min_length=5, max_length=5)
    missing_information: list[MissingInformation] = Field(default_factory=list)
    critical_missing_fields: list[str] = Field(default_factory=list)
    factor_scores: dict[str, FactorScore]
    hard_filter_reasons: list[str] = Field(default_factory=list)


class ListingRecord(BaseModel):
    id: int
    source: str
    homegate_id: str
    url: str
    title: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    rent_chf: float | None = None
    extra_costs_chf: float | None = None
    total_cost_chf: float | None = None
    rooms: float | None = None
    living_space_sqm: float | None = None
    available_from: date | None = None
    last_refurbishment_year: int | None = None
    year_built: int | None = None
    listing_type: str | None = None
    is_roommate_listing: bool | None = None
    public_transport_walk_minutes: int | None = None
    public_transport_name: str | None = None
    supermarket_walk_minutes: int | None = None
    supermarket_name: str | None = None
    office_commute_minutes: int | None = None
    description: str | None = None
    raw_text: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    source_email_sender: str | None = None
    source_email_subject: str | None = None
    source_email_received_at: datetime | None = None
    source_email_excerpt: str | None = None
    extraction_status: ExtractionStatus
    extraction_error: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    updated_at: datetime


class InboxItem(BaseModel):
    listing: ListingRecord
    evaluation: EvaluationResult | None = None
    manual_state: ManualDecision | None = None
    manual_note: str = ""


class TriageRunSummary(BaseModel):
    processed_alerts: int = 0
    touched_listings: int = 0
    extracted_listings: int = 0
    evaluated_listings: int = 0
    notified_listings: int = 0
