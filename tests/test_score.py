from __future__ import annotations

from datetime import date, timedelta, timezone, datetime

from homegate_triage_assistant.llm import LLMJudge
from homegate_triage_assistant.schemas import ExtractedListing, LLMReview
from homegate_triage_assistant.score import ListingScorer


class PositiveJudge:
    def evaluate(self, listing: ExtractedListing) -> LLMReview:
        return LLMReview(
            vfm_score=8,
            kitchen_quality_score=8,
            condition_score=8,
            judge_opinion="positive",
            judge_rationale="Strong overall fit.",
            confidence=0.9,
            summary_lines=[
                "Price is close to the cap but still acceptable.",
                "Size and commute are strong.",
                "Private apartment, not a WG.",
                "Move-in fits the preferred window.",
                "Worth contacting quickly.",
            ],
            missing_information=[],
        )


def test_scoring_marks_over_budget_listing_for_ignore(test_config) -> None:
    scorer = ListingScorer(test_config, PositiveJudge())
    listing = ExtractedListing(
        homegate_id="1",
        url="https://www.homegate.ch/rent/1",
        city="Zurich",
        total_cost_chf=1900,
        living_space_sqm=65,
        office_commute_minutes=20,
        supermarket_walk_minutes=5,
        is_roommate_listing=False,
        public_transport_walk_minutes=4,
        available_from=date.today() + timedelta(weeks=4),
        extraction_status="success",
    )
    evaluation = scorer.evaluate(listing)
    assert evaluation.triage_decision == "ignore"
    assert evaluation.hard_filter_reasons


def test_scoring_marks_strong_listing_as_contact_candidate(test_config) -> None:
    scorer = ListingScorer(test_config, PositiveJudge())
    listing = ExtractedListing(
        homegate_id="2",
        url="https://www.homegate.ch/rent/2",
        city="Zurich",
        total_cost_chf=1600,
        living_space_sqm=62,
        office_commute_minutes=24,
        supermarket_walk_minutes=6,
        is_roommate_listing=False,
        public_transport_walk_minutes=4,
        available_from=date.today() + timedelta(weeks=5),
        extraction_status="success",
    )
    evaluation = scorer.evaluate(listing)
    assert evaluation.triage_decision == "contact_candidate"
    assert evaluation.total_score >= 7.8


def test_scoring_routes_blocked_extraction_to_inspect(test_config) -> None:
    scorer = ListingScorer(test_config, PositiveJudge())
    listing = ExtractedListing(
        homegate_id="3",
        url="https://www.homegate.ch/rent/3",
        extraction_status="blocked",
    )
    evaluation = scorer.evaluate(listing)
    assert evaluation.triage_decision == "inspect"
