"""Pure CRFB reform-panel scheduling helpers.

This module deliberately imports no Modal APIs so tests can lock the production
launch contract without making Modal a local test dependency.
"""

from __future__ import annotations

BEHAVIORAL_ENDPOINT_YEARS = (2026, 2100)
SUPPORTED_SCORING_TYPES = ("static", "behavioral")
PANEL_REFORMS = (
    "option1",
    "option2",
    "option3",
    "option4",
    "option5",
    "option6",
    "option7",
    "option8",
    "option9",
    "option10",
    "option11",
    "option12",
    "tax93",
    "reverse_roth",
)


def normalize_scoring_type(scoring_type: str) -> str:
    normalized = scoring_type.strip().lower()
    if normalized not in SUPPORTED_SCORING_TYPES:
        allowed = ", ".join(SUPPORTED_SCORING_TYPES)
        raise ValueError(
            f"Unknown scoring_type {scoring_type!r}; expected one of: {allowed}"
        )
    return normalized


def normalize_scoring_types(scoring_types) -> tuple[str, ...]:
    normalized: list[str] = []
    for scoring_type in scoring_types:
        value = normalize_scoring_type(scoring_type)
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def years_for_scoring(scoring_type: str, year_list) -> list[int]:
    scoring_type = normalize_scoring_type(scoring_type)
    if scoring_type == "static":
        return list(year_list)
    return [y for y in BEHAVIORAL_ENDPOINT_YEARS if y in year_list]


def validate_scoring_year(scoring_type: str, year: int) -> None:
    scoring_type = normalize_scoring_type(scoring_type)
    if scoring_type == "static":
        return
    if year not in BEHAVIORAL_ENDPOINT_YEARS:
        raise ValueError(
            f"{scoring_type!r} scoring is endpoint-only {BEHAVIORAL_ENDPOINT_YEARS}; "
            f"refusing per-year LSR cell for year {year}"
        )


def cell_key(reform_id: str, year: int, scoring_type: str = "static") -> str:
    scoring_type = normalize_scoring_type(scoring_type)
    suffix = "" if scoring_type == "static" else f"_{scoring_type}"
    return f"{reform_id}_{year}{suffix}"


def wanted_cell_keys(
    reform_list,
    year_list,
    scoring_types,
) -> set[str]:
    scoring_types = normalize_scoring_types(scoring_types)
    return {
        cell_key(reform_id, year, scoring_type)
        for scoring_type in scoring_types
        for year in years_for_scoring(scoring_type, year_list)
        for reform_id in reform_list
    }


def needed_baseline_years(year_list, scoring_types) -> list[int]:
    scoring_types = normalize_scoring_types(scoring_types)
    needed = {
        year
        for scoring_type in scoring_types
        for year in years_for_scoring(scoring_type, year_list)
    }
    return [year for year in year_list if year in needed]
