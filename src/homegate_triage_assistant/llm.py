from __future__ import annotations

from typing import Any

from openai import OpenAI

from .config import Config
from .schemas import ExtractedListing, LLMReview, MissingInformation


class LLMJudge:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = OpenAI(api_key=config.openai.api_key) if config.openai.is_configured else None

    def evaluate(self, listing: ExtractedListing) -> LLMReview:
        if self._client is None:
            return self._fallback_review(listing, "OPENAI_API_KEY is not configured.")

        facts = {
            "title": listing.title,
            "address": listing.address,
            "city": listing.city,
            "total_cost_chf": listing.total_cost_chf,
            "rent_chf": listing.rent_chf,
            "living_space_sqm": listing.living_space_sqm,
            "rooms": listing.rooms,
            "available_from": listing.available_from.isoformat() if listing.available_from else None,
            "last_refurbishment_year": listing.last_refurbishment_year,
            "year_built": listing.year_built,
            "listing_type": listing.listing_type,
            "is_roommate_listing": listing.is_roommate_listing,
            "public_transport_walk_minutes": listing.public_transport_walk_minutes,
            "supermarket_walk_minutes": listing.supermarket_walk_minutes,
            "office_commute_minutes": listing.office_commute_minutes,
            "description": listing.description,
            "extraction_status": listing.extraction_status,
        }

        instructions = (
            "You are evaluating one Zurich rental listing for fast personal triage. "
            "Only score ambiguous factors. Use the facts provided. "
            "Return JSON matching the schema exactly. "
            "Summary lines must be exactly 5 short lines, each self-contained. "
            "judge_opinion must be positive, neutral, or negative. "
            "Flag missing_information only when a gap materially affects a decision."
        )
        try:
            response = self._client.responses.parse(
                model=self.config.openai.model,
                instructions=instructions,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Score these factors from 0 to 10: "
                                    "vfm, kitchen quality, and condition. "
                                    "Condition means old vs modern vs renovated. "
                                    "Then provide a short judge opinion for inspect/ignore/contact triage.\n\n"
                                    f"Listing facts:\n{facts}"
                                ),
                            }
                        ],
                    }
                ],
                text_format=LLMReview,
                max_output_tokens=self.config.openai.max_output_tokens,
                temperature=0.2,
                text={"verbosity": "low"},
            )
            parsed = response.output_parsed
            if parsed is None:
                raise RuntimeError("OpenAI returned no structured output.")
            return parsed
        except Exception as exc:
            return self._fallback_review(listing, f"LLM evaluation failed: {exc}")

    def _fallback_review(self, listing: ExtractedListing, reason: str) -> LLMReview:
        summary_lines = _build_summary_lines(listing)
        missing = list(_heuristic_missing_info(listing))
        missing.append(MissingInformation(field="llm_review", reason=reason, critical=False))
        return LLMReview(
            vfm_score=5.0,
            kitchen_quality_score=5.0,
            condition_score=5.0,
            judge_opinion="neutral",
            judge_rationale="LLM review unavailable, so ambiguous factors are neutral and require inspection.",
            confidence=0.35,
            summary_lines=summary_lines,
            missing_information=missing,
        )


def _build_summary_lines(listing: ExtractedListing) -> list[str]:
    return [
        f"Price: CHF {listing.total_cost_chf:.0f}" if listing.total_cost_chf else "Price: unknown",
        f"Size: {listing.living_space_sqm:.0f} sqm" if listing.living_space_sqm else "Size: unknown",
        f"Commute: {listing.office_commute_minutes} min to office" if listing.office_commute_minutes else "Commute: unknown",
        f"Move-in: {listing.available_from.isoformat()}" if listing.available_from else "Move-in: unknown",
        f"Signal: {listing.extraction_status} extraction, manual review advised",
    ]


def _heuristic_missing_info(listing: ExtractedListing) -> list[MissingInformation]:
    missing: list[MissingInformation] = []
    if listing.total_cost_chf is None:
        missing.append(MissingInformation(field="total_cost_per_month", reason="Total monthly cost is missing.", critical=True))
    if listing.available_from is None:
        missing.append(MissingInformation(field="move_in_date_fit", reason="Move-in date is missing.", critical=True))
    if listing.description is None:
        missing.append(MissingInformation(field="description", reason="Listing description is missing.", critical=False))
    return missing
