from __future__ import annotations

from datetime import date, datetime, timezone

from .config import Config
from .llm import LLMJudge
from .schemas import EvaluationResult, ExtractedListing, FactorScore, MissingInformation


class ListingScorer:
    def __init__(self, config: Config, judge: LLMJudge) -> None:
        self.config = config
        self.judge = judge

    def evaluate(self, listing: ExtractedListing) -> EvaluationResult:
        factor_scores: dict[str, FactorScore] = {}
        missing_information: list[MissingInformation] = []
        hard_filter_reasons: list[str] = []

        cost_score = self._cost_score(listing.total_cost_chf)
        factor_scores["total_cost_per_month"] = cost_score
        if listing.total_cost_chf is None:
            missing_information.append(MissingInformation(field="total_cost_per_month", reason="Total monthly cost is unknown.", critical=True))
        elif listing.total_cost_chf > self.config.search.max_total_cost_chf:
            hard_filter_reasons.append(
                f"Total monthly cost CHF {listing.total_cost_chf:.0f} exceeds the configured cap of CHF {self.config.search.max_total_cost_chf}."
            )

        factor_scores["size"] = self._size_score(listing.living_space_sqm)
        if listing.living_space_sqm is None:
            missing_information.append(MissingInformation(field="size", reason="Living space is unknown.", critical=False))

        factor_scores["proximity_to_office_beethovenstrasse_48"] = self._office_score(listing.office_commute_minutes)
        if listing.office_commute_minutes is None:
            missing_information.append(MissingInformation(field="proximity_to_office_beethovenstrasse_48", reason="Office commute could not be calculated.", critical=True))

        factor_scores["proximity_to_big_supermarket"] = self._supermarket_score(listing.supermarket_walk_minutes)
        if listing.supermarket_walk_minutes is None:
            missing_information.append(MissingInformation(field="proximity_to_big_supermarket", reason="Nearest supermarket distance is unknown.", critical=False))

        factor_scores["alone_or_with_roommates"] = self._roommate_score(listing.is_roommate_listing)
        if listing.is_roommate_listing is None:
            missing_information.append(MissingInformation(field="alone_or_with_roommates", reason="Roommate signal is unclear.", critical=False))

        factor_scores["proximity_to_public_transport"] = self._public_transport_score(listing.public_transport_walk_minutes)
        if listing.public_transport_walk_minutes is None:
            missing_information.append(MissingInformation(field="proximity_to_public_transport", reason="Public transport walking time is unknown.", critical=False))

        factor_scores["move_in_date_fit"] = self._move_in_score(listing.available_from)
        if listing.available_from is None:
            missing_information.append(MissingInformation(field="move_in_date_fit", reason="Move-in date is missing.", critical=True))

        if listing.city and "zur" not in listing.city.casefold():
            hard_filter_reasons.append(f"Listing city is {listing.city}, outside the Zurich-only search.")

        llm_review = self.judge.evaluate(listing)
        factor_scores["vfm"] = FactorScore(
            score=llm_review.vfm_score,
            weight=self.config.weights["vfm"],
            evidence="LLM judged value for money from cost, size, condition, and listing description.",
            source="llm",
        )
        factor_scores["kitchen_quality"] = FactorScore(
            score=llm_review.kitchen_quality_score,
            weight=self.config.weights["kitchen_quality"],
            evidence="LLM judged kitchen quality from listing description and extracted facts.",
            source="llm",
        )
        factor_scores["condition"] = FactorScore(
            score=llm_review.condition_score,
            weight=self.config.weights["condition"],
            evidence="LLM judged old/modern/renovated condition using refurbishment and description clues.",
            source="llm",
        )
        missing_information.extend(llm_review.missing_information)

        total_score = round(_weighted_average(factor_scores), 2)
        deterministic_score = round(
            _weighted_average({key: value for key, value in factor_scores.items() if value.source == "deterministic"}),
            2,
        )
        critical_missing_fields = sorted({item.field for item in missing_information if item.critical})

        confidence = round(
            min(
                1.0,
                max(
                    0.2,
                    (llm_review.confidence + _deterministic_completeness(factor_scores)) / 2,
                ),
            ),
            2,
        )
        triage_decision = _triage_decision(
            total_score=total_score,
            judge_opinion=llm_review.judge_opinion,
            critical_missing_fields=critical_missing_fields,
            hard_filter_reasons=hard_filter_reasons,
            extraction_status=listing.extraction_status,
        )

        return EvaluationResult(
            deterministic_score=deterministic_score,
            total_score=total_score,
            triage_decision=triage_decision,
            judge_opinion=llm_review.judge_opinion,
            judge_rationale=llm_review.judge_rationale,
            confidence=confidence,
            summary_lines=llm_review.summary_lines,
            missing_information=_dedupe_missing(missing_information),
            critical_missing_fields=critical_missing_fields,
            factor_scores=factor_scores,
            hard_filter_reasons=hard_filter_reasons,
        )

    def _cost_score(self, total_cost_chf: float | None) -> FactorScore:
        if total_cost_chf is None:
            return FactorScore(
                score=5,
                weight=self.config.weights["total_cost_per_month"],
                evidence="Total monthly cost is missing.",
                source="deterministic",
                missing=True,
            )
        if total_cost_chf <= 1400:
            score, evidence = 10, "Monthly cost is at or below the strong target range."
        elif total_cost_chf <= 1600:
            score, evidence = 8, "Monthly cost is solid and below the upper-middle range."
        elif total_cost_chf <= self.config.search.max_total_cost_chf:
            score, evidence = 6, "Monthly cost is acceptable but close to the cap."
        else:
            score, evidence = 0, "Monthly cost exceeds the configured cap."
        return FactorScore(score=score, weight=self.config.weights["total_cost_per_month"], evidence=evidence, source="deterministic")

    def _size_score(self, size_sqm: float | None) -> FactorScore:
        if size_sqm is None:
            return FactorScore(score=5, weight=self.config.weights["size"], evidence="Living space is unknown.", source="deterministic", missing=True)
        if size_sqm >= 60:
            score, evidence = 10, "Living space is in the strong target range."
        elif size_sqm >= 50:
            score, evidence = 8, "Living space is good for the price band."
        elif size_sqm >= 40:
            score, evidence = 6, "Living space is workable but modest."
        else:
            score, evidence = 3, "Living space is likely too small for comfort."
        return FactorScore(score=score, weight=self.config.weights["size"], evidence=evidence, source="deterministic")

    def _office_score(self, commute_minutes: int | None) -> FactorScore:
        if commute_minutes is None:
            return FactorScore(score=5, weight=self.config.weights["proximity_to_office_beethovenstrasse_48"], evidence="Office commute is unknown.", source="deterministic", missing=True)
        if commute_minutes <= 25:
            score, evidence = 10, "Commute is in the preferred range."
        elif commute_minutes <= 35:
            score, evidence = 8, "Commute is still solid for Zurich."
        elif commute_minutes <= 45:
            score, evidence = 5, "Commute is acceptable but no longer strong."
        else:
            score, evidence = 2, "Commute is longer than desired."
        return FactorScore(score=score, weight=self.config.weights["proximity_to_office_beethovenstrasse_48"], evidence=evidence, source="deterministic")

    def _supermarket_score(self, minutes: int | None) -> FactorScore:
        if minutes is None:
            return FactorScore(score=5, weight=self.config.weights["proximity_to_big_supermarket"], evidence="Supermarket distance is unknown.", source="deterministic", missing=True)
        if minutes <= 7:
            score, evidence = 10, "A large supermarket is close by."
        elif minutes <= 12:
            score, evidence = 7, "Supermarket access is acceptable."
        elif minutes <= 20:
            score, evidence = 5, "Supermarket access is workable but not convenient."
        else:
            score, evidence = 3, "Supermarket access looks inconvenient."
        return FactorScore(score=score, weight=self.config.weights["proximity_to_big_supermarket"], evidence=evidence, source="deterministic")

    def _roommate_score(self, is_roommate_listing: bool | None) -> FactorScore:
        if is_roommate_listing is None:
            return FactorScore(score=5, weight=self.config.weights["alone_or_with_roommates"], evidence="Roommate signal is unclear.", source="deterministic", missing=True)
        if is_roommate_listing:
            score, evidence = 3, "Listing appears to involve roommates or a shared setup."
        else:
            score, evidence = 10, "Listing appears to be a private apartment."
        return FactorScore(score=score, weight=self.config.weights["alone_or_with_roommates"], evidence=evidence, source="deterministic")

    def _public_transport_score(self, minutes: int | None) -> FactorScore:
        if minutes is None:
            return FactorScore(score=5, weight=self.config.weights["proximity_to_public_transport"], evidence="Public transport distance is unknown.", source="deterministic", missing=True)
        if minutes <= 5:
            score, evidence = 10, "Public transport access is excellent."
        elif minutes <= 10:
            score, evidence = 7, "Public transport access is good."
        elif minutes <= 15:
            score, evidence = 5, "Public transport access is acceptable."
        else:
            score, evidence = 3, "Public transport access is weak."
        return FactorScore(score=score, weight=self.config.weights["proximity_to_public_transport"], evidence=evidence, source="deterministic")

    def _move_in_score(self, available_from: date | None) -> FactorScore:
        if available_from is None:
            return FactorScore(score=5, weight=self.config.weights["move_in_date_fit"], evidence="Move-in date is unknown.", source="deterministic", missing=True)
        today = datetime.now(timezone.utc).date()
        delta_days = (available_from - today).days
        weeks = delta_days / 7
        if weeks < 0:
            score, evidence = 8, "Apartment is already available."
        elif weeks < self.config.search.desired_move_in_min_weeks:
            score, evidence = 8, "Immediate availability is workable."
        elif weeks <= self.config.search.desired_move_in_max_weeks:
            score, evidence = 10, "Move-in timing is in the preferred window."
        elif weeks <= self.config.search.acceptable_move_in_max_weeks:
            score, evidence = 5, "Move-in timing is later than ideal but still workable."
        else:
            score, evidence = 3, "Move-in timing is too late for the current search."
        return FactorScore(score=score, weight=self.config.weights["move_in_date_fit"], evidence=evidence, source="deterministic")


def _weighted_average(factor_scores: dict[str, FactorScore]) -> float:
    total_weight = sum(score.weight for score in factor_scores.values())
    if not total_weight:
        return 0.0
    return sum(score.score * score.weight for score in factor_scores.values()) / total_weight


def _deterministic_completeness(factor_scores: dict[str, FactorScore]) -> float:
    deterministic = [score for score in factor_scores.values() if score.source == "deterministic"]
    if not deterministic:
        return 0.0
    covered = [score for score in deterministic if not score.missing]
    return len(covered) / len(deterministic)


def _triage_decision(
    *,
    total_score: float,
    judge_opinion: str,
    critical_missing_fields: list[str],
    hard_filter_reasons: list[str],
    extraction_status: str,
) -> str:
    if hard_filter_reasons:
        return "ignore"
    if extraction_status != "success":
        return "inspect"
    if critical_missing_fields:
        return "inspect"
    if total_score >= 7.8 and judge_opinion == "positive" and not critical_missing_fields:
        return "contact_candidate"
    if total_score < 6.0:
        return "ignore"
    return "inspect"


def _dedupe_missing(items: list[MissingInformation]) -> list[MissingInformation]:
    seen: set[tuple[str, str, bool]] = set()
    result: list[MissingInformation] = []
    for item in items:
        key = (item.field, item.reason, item.critical)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
