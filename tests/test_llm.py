from __future__ import annotations

from datetime import date

from homegate_triage_assistant.llm import LLMJudge
from homegate_triage_assistant.schemas import ExtractedListing


def test_llm_falls_back_to_neutral_structured_review_without_api_key(test_config) -> None:
    judge = LLMJudge(test_config)
    review = judge.evaluate(
        ExtractedListing(
            homegate_id="1",
            url="https://www.homegate.ch/rent/1",
            total_cost_chf=1700,
            living_space_sqm=55,
            available_from=date(2026, 6, 1),
            extraction_status="partial",
        )
    )
    assert review.judge_opinion == "neutral"
    assert len(review.summary_lines) == 5
    assert any(item.field == "llm_review" for item in review.missing_information)
