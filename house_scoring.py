from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

RATING_MIN = 0.0
RATING_MAX = 10.0
NEUTRAL_RATING = 5.0


@dataclass(frozen=True)
class Factor:
    key: str
    label: str
    description: str
    default_weight: float = 1.0


FACTORS: List[Factor] = [
    Factor(
        "total_cost_per_month",
        "Total cost per month",
        "All-in recurring monthly housing cost. Higher rating means lower real monthly spend.",
    ),
    Factor(
        "value_for_money",
        "Value for money",
        "How good the apartment feels relative to what it costs in the current Zurich market.",
    ),
    Factor(
        "size_sqm",
        "Size",
        "Usable living area and whether the space feels sufficient for daily life.",
    ),
    Factor(
        "proximity_to_office_beethovenstrasse_48",
        "Proximity to office",
        "Door-to-desk commute quality to Beethovenstrasse 48.",
    ),
    Factor(
        "proximity_to_good_gym_with_sauna",
        "Proximity to good gym with sauna",
        "How convenient it is to reach a gym that actually meets your training and sauna requirements.",
    ),
    Factor(
        "proximity_to_big_supermarket",
        "Proximity to big supermarket",
        "Ease of access to a large grocery store such as Migros, Coop, Aldi, or Lidl.",
    ),
    Factor(
        "estimated_total_move_in_cost",
        "Estimated total move-in cost",
        "Deposit, first month, setup spending, and any major one-off costs.",
    ),
    Factor(
        "proximity_to_public_transport",
        "Proximity to public transport",
        "Walking convenience to tram, bus, or S-Bahn stops.",
    ),
    Factor(
        "commute_reliability",
        "Commute reliability",
        "How robust the commute is across normal delays, weather, transfers, and evening hours.",
    ),
    Factor(
        "neighborhood_safety",
        "Neighborhood safety",
        "How safe and comfortable the area feels, especially at night.",
    ),
    Factor(
        "daytime_noise",
        "Daytime noise",
        "How quiet and workable the apartment is during the day.",
    ),
    Factor(
        "nighttime_noise",
        "Nighttime noise",
        "How quiet and sleep-friendly the apartment is at night.",
    ),
    Factor(
        "natural_light",
        "Natural light",
        "Amount and quality of daylight in the apartment.",
    ),
    Factor(
        "layout_efficiency",
        "Layout efficiency",
        "How well the floor plan uses the available square meters.",
    ),
    Factor(
        "storage_space",
        "Storage space",
        "Closets, cellar, pantry, and practical room for belongings.",
    ),
    Factor(
        "laundry_convenience",
        "Laundry convenience",
        "Private washer, shared laundry access, scheduling friction, and drying setup.",
    ),
    Factor(
        "kitchen_quality",
        "Kitchen quality",
        "Kitchen size, appliances, counter space, and overall usability.",
    ),
    Factor(
        "bathroom_quality",
        "Bathroom quality",
        "Bathroom size, condition, ventilation, and practical comfort.",
    ),
    Factor(
        "building_condition",
        "Building condition",
        "General maintenance quality of the building, common areas, and infrastructure.",
    ),
    Factor(
        "heating_efficiency_and_winter_comfort",
        "Heating efficiency and winter comfort",
        "How warm and comfortable the apartment is in winter without excessive heating waste.",
    ),
    Factor(
        "summer_heat_comfort",
        "Summer heat comfort",
        "How livable the apartment is during hot periods.",
    ),
    Factor(
        "energy_efficiency_and_insulation",
        "Energy efficiency and insulation",
        "Window quality, insulation, and likely energy performance.",
    ),
    Factor(
        "internet_connectivity",
        "Internet connectivity",
        "Expected home internet quality and provider options.",
    ),
    Factor(
        "balcony_or_outdoor_space",
        "Balcony or outdoor space",
        "Quality and usefulness of any balcony, terrace, garden, or shared outdoor area.",
    ),
    Factor(
        "view_and_privacy",
        "View and privacy",
        "How private the apartment feels and whether the outlook improves daily quality of life.",
    ),
    Factor(
        "floor_level_and_elevator_convenience",
        "Floor level and elevator convenience",
        "Practicality of the floor level, stairs, and elevator access.",
    ),
    Factor(
        "furnished_fit",
        "Furnished fit",
        "Whether the furnishing situation matches your needs and avoids unwanted costs.",
    ),
    Factor(
        "contract_flexibility",
        "Contract flexibility",
        "How workable the notice period, renewal terms, and general lease flexibility are.",
    ),
    Factor(
        "minimum_lease_fit",
        "Minimum lease fit",
        "Whether the minimum rental commitment matches your likely plans.",
    ),
    Factor(
        "move_in_date_fit",
        "Move-in date fit",
        "How well the availability date matches your relocation timeline.",
    ),
    Factor(
        "landlord_or_agency_responsiveness",
        "Landlord or agency responsiveness",
        "How competent, responsive, and straightforward the counterparty seems.",
    ),
    Factor(
        "chance_of_application_success",
        "Chance of application success",
        "How realistic it is that you could actually secure the apartment.",
    ),
    Factor(
        "neighborhood_vibe",
        "Neighborhood vibe",
        "Whether the area feels aligned with how you want to live day to day.",
    ),
    Factor(
        "proximity_to_parks_or_water",
        "Proximity to parks or water",
        "Ease of reaching green space, lakeside, or other good outdoor decompression spots.",
    ),
    Factor(
        "walkability_for_daily_errands",
        "Walkability for daily errands",
        "How easy it is to cover most everyday needs on foot.",
    ),
    Factor(
        "bike_friendliness",
        "Bike friendliness",
        "How practical the area is for regular cycling and bike storage.",
    ),
]


DEFAULT_WEIGHTS: Dict[str, float] = {factor.key: factor.default_weight for factor in FACTORS}

# Suggested starting point that reflects the priorities you mentioned.
SUGGESTED_STARTER_WEIGHTS: Dict[str, float] = {
    **DEFAULT_WEIGHTS,
    "total_cost_per_month": 2.0,
    "value_for_money": 1.8,
    "size_sqm": 1.5,
    "proximity_to_office_beethovenstrasse_48": 2.0,
    "proximity_to_good_gym_with_sauna": 1.4,
    "proximity_to_big_supermarket": 1.3,
    "estimated_total_move_in_cost": 1.2,
    "proximity_to_public_transport": 1.3,
    "commute_reliability": 1.4,
    "neighborhood_safety": 1.3,
    "nighttime_noise": 1.2,
    "walkability_for_daily_errands": 1.2,
}


def _factor_map() -> Dict[str, Factor]:
    return {factor.key: factor for factor in FACTORS}


def _validate_unknown_keys(mapping: Dict[str, float], label: str) -> None:
    known_keys = _factor_map().keys()
    unknown = sorted(set(mapping) - set(known_keys))
    if unknown:
        raise KeyError(f"Unknown {label} keys: {', '.join(unknown)}")


def _validate_weights(weights: Dict[str, float]) -> None:
    _validate_unknown_keys(weights, "weight")
    invalid = {key: value for key, value in weights.items() if value <= 0}
    if invalid:
        details = ", ".join(f"{key}={value}" for key, value in sorted(invalid.items()))
        raise ValueError(f"All weights must be positive. Invalid weights: {details}")


def _validate_ratings(ratings: Dict[str, float]) -> None:
    _validate_unknown_keys(ratings, "rating")
    invalid = {
        key: value
        for key, value in ratings.items()
        if not (RATING_MIN <= float(value) <= RATING_MAX)
    }
    if invalid:
        details = ", ".join(f"{key}={value}" for key, value in sorted(invalid.items()))
        raise ValueError(
            f"Ratings must be between {RATING_MIN} and {RATING_MAX}. Invalid ratings: {details}"
        )


def calculate_house_score(
    ratings: Dict[str, float],
    weights: Dict[str, float] | None = None,
    allow_missing: bool = False,
) -> Dict[str, object]:
    """
    Calculate a weighted apartment score.

    Ratings are expected on a 0-10 scale where 10 is best.
    Weights can be any positive values.
    If allow_missing is True, missing factors are ignored and coverage is reported.
    """

    chosen_weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    _validate_weights(chosen_weights)
    _validate_ratings(ratings)

    factor_lookup = _factor_map()
    weighted_rows: List[Dict[str, float | str]] = []
    missing_factors: List[str] = []

    for factor in FACTORS:
        if factor.key not in ratings:
            if allow_missing:
                missing_factors.append(factor.key)
                continue
            raise KeyError(f"Missing rating for factor: {factor.key}")

        rating = float(ratings[factor.key])
        weight = float(chosen_weights.get(factor.key, DEFAULT_WEIGHTS[factor.key]))
        weighted_rows.append(
            {
                "key": factor.key,
                "label": factor.label,
                "rating": rating,
                "weight": weight,
                "weighted_points": rating * weight,
                "impact_vs_neutral": (rating - NEUTRAL_RATING) * weight,
            }
        )

    if not weighted_rows:
        raise ValueError("No rated factors were provided.")

    total_weight = sum(float(row["weight"]) for row in weighted_rows)
    total_possible_weight = sum(float(chosen_weights.get(factor.key, DEFAULT_WEIGHTS[factor.key])) for factor in FACTORS)
    weighted_average = sum(float(row["weighted_points"]) for row in weighted_rows) / total_weight
    coverage = total_weight / total_possible_weight if total_possible_weight else 0.0

    strongest = sorted(weighted_rows, key=lambda row: float(row["impact_vs_neutral"]), reverse=True)[:5]
    weakest = sorted(weighted_rows, key=lambda row: float(row["impact_vs_neutral"]))[:5]

    return {
        "score_out_of_10": round(weighted_average, 2),
        "score_out_of_100": round(weighted_average * 10, 1),
        "coverage_percent": round(coverage * 100, 1),
        "rated_factor_count": len(weighted_rows),
        "missing_factors": missing_factors,
        "strongest_factors": strongest,
        "weakest_factors": weakest,
    }


def print_factor_catalog() -> None:
    print("Factor catalog")
    print("-" * 80)
    for index, factor in enumerate(FACTORS, start=1):
        print(f"{index:>2}. {factor.key}")
        print(f"    {factor.label}: {factor.description}")


def print_score_report(title: str, result: Dict[str, object]) -> None:
    print(title)
    print("=" * len(title))
    print(f"Score: {result['score_out_of_10']} / 10")
    print(f"Score: {result['score_out_of_100']} / 100")
    print(f"Coverage: {result['coverage_percent']}%")
    print(f"Rated factors: {result['rated_factor_count']}")

    if result["missing_factors"]:
        print("Missing factors:")
        for factor_key in result["missing_factors"]:
            print(f"  - {factor_key}")

    print("\nStrongest factors")
    print("-" * 80)
    for row in result["strongest_factors"]:
        print(
            f"{row['label']}: rating={row['rating']}, weight={row['weight']}, "
            f"impact_vs_neutral={row['impact_vs_neutral']:.2f}"
        )

    print("\nWeakest factors")
    print("-" * 80)
    for row in result["weakest_factors"]:
        print(
            f"{row['label']}: rating={row['rating']}, weight={row['weight']}, "
            f"impact_vs_neutral={row['impact_vs_neutral']:.2f}"
        )


EXAMPLE_RATINGS: Dict[str, float] = {
    "total_cost_per_month": 6.5,
    "value_for_money": 7.0,
    "size_sqm": 7.5,
    "proximity_to_office_beethovenstrasse_48": 8.5,
    "proximity_to_good_gym_with_sauna": 9.0,
    "proximity_to_big_supermarket": 8.0,
    "estimated_total_move_in_cost": 5.5,
    "proximity_to_public_transport": 9.0,
    "commute_reliability": 8.0,
    "neighborhood_safety": 8.5,
    "daytime_noise": 6.5,
    "nighttime_noise": 7.5,
    "natural_light": 8.0,
    "layout_efficiency": 7.5,
    "storage_space": 6.0,
    "laundry_convenience": 6.5,
    "kitchen_quality": 7.5,
    "bathroom_quality": 7.0,
    "building_condition": 8.0,
    "heating_efficiency_and_winter_comfort": 7.5,
    "summer_heat_comfort": 6.0,
    "energy_efficiency_and_insulation": 7.0,
    "internet_connectivity": 8.5,
    "balcony_or_outdoor_space": 6.0,
    "view_and_privacy": 7.0,
    "floor_level_and_elevator_convenience": 7.5,
    "furnished_fit": 8.0,
    "contract_flexibility": 6.0,
    "minimum_lease_fit": 8.0,
    "move_in_date_fit": 9.0,
    "landlord_or_agency_responsiveness": 8.5,
    "chance_of_application_success": 6.5,
    "neighborhood_vibe": 8.0,
    "proximity_to_parks_or_water": 7.0,
    "walkability_for_daily_errands": 9.0,
    "bike_friendliness": 7.0,
}


if __name__ == "__main__":
    print_factor_catalog()
    print()
    example_result = calculate_house_score(
        EXAMPLE_RATINGS,
        weights=SUGGESTED_STARTER_WEIGHTS,
        allow_missing=False,
    )
    print_score_report("Example apartment evaluation", example_result)
