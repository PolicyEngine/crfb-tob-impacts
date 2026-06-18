from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path

from .modal_batch_helpers import parse_years


STANDARD_REFORMS = tuple(f"option{i}" for i in range(1, 13))
DEFAULT_ANNUAL_YEARS = tuple(range(2026, 2036))
DEFAULT_FIVE_YEAR_YEARS = tuple(range(2040, 2101, 5))
DEFAULT_JUNCTURE_YEARS = (2048, 2049, 2062, 2063)


@dataclass(frozen=True)
class SelectedCells:
    reforms: tuple[str, ...]
    years: tuple[int, ...]
    cells: tuple[tuple[str, int], ...]
    metadata: dict[str, object]


def parse_reforms(reforms: str | None = None) -> tuple[str, ...]:
    if not reforms:
        return STANDARD_REFORMS
    parsed = tuple(value.strip() for value in reforms.split(",") if value.strip())
    if not parsed:
        raise ValueError("At least one reform is required.")
    return parsed


def default_selected_years() -> tuple[int, ...]:
    return tuple(
        sorted(
            set(DEFAULT_ANNUAL_YEARS)
            | set(DEFAULT_FIVE_YEAR_YEARS)
            | set(DEFAULT_JUNCTURE_YEARS)
        )
    )


def parse_selected_years(years: str | None = None) -> tuple[int, ...]:
    if not years:
        return default_selected_years()
    parsed = tuple(sorted(set(parse_years(years))))
    if not parsed:
        raise ValueError("At least one year is required.")
    return parsed


def build_selected_cells(
    *,
    reforms: str | None = None,
    years: str | None = None,
) -> SelectedCells:
    parsed_reforms = parse_reforms(reforms)
    parsed_years = parse_selected_years(years)
    cells = tuple(
        (reform_id, year) for reform_id in parsed_reforms for year in parsed_years
    )
    metadata: dict[str, object] = {
        "schema": "crfb_tob_selected_cells/v1",
        "description": (
            "Selected CRFB long-run scoring panel: annual budget-window years, "
            "five-year long-run sentinels, and reform transition junctures."
        ),
        "reforms": list(parsed_reforms),
        "years": list(parsed_years),
        "year_policy": {
            "annual_years": list(DEFAULT_ANNUAL_YEARS),
            "five_year_years": list(DEFAULT_FIVE_YEAR_YEARS),
            "juncture_years": list(DEFAULT_JUNCTURE_YEARS),
        },
        "reform_count": len(parsed_reforms),
        "year_count": len(parsed_years),
        "cell_count": len(cells),
    }
    return SelectedCells(
        reforms=parsed_reforms,
        years=parsed_years,
        cells=cells,
        metadata=metadata,
    )


def metadata_path_for_cells(output_path: Path) -> Path:
    return output_path.with_suffix(output_path.suffix + ".metadata.json")


def write_selected_cells(
    output_path: Path,
    *,
    reforms: str | None = None,
    years: str | None = None,
) -> SelectedCells:
    selected = build_selected_cells(reforms=reforms, years=years)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["reform_id", "year"])
        writer.writeheader()
        writer.writerows(
            {"reform_id": reform_id, "year": year} for reform_id, year in selected.cells
        )
    metadata_path_for_cells(output_path).write_text(
        json.dumps(selected.metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return selected


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the selected CRFB long-run Modal reform/year cells."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="CSV output path with reform_id,year columns.",
    )
    parser.add_argument(
        "--reforms",
        help="Optional comma-separated reform IDs. Defaults to option1-option12.",
    )
    parser.add_argument(
        "--years",
        help=(
            "Optional year range/list using selected-cell syntax. "
            "Defaults to annual 2026-2035, every five years 2040-2100, "
            "and 2048,2049,2062,2063 junctures."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selected = write_selected_cells(args.output, reforms=args.reforms, years=args.years)
    print(
        f"Wrote {len(selected.cells)} cells across {len(selected.reforms)} reforms "
        f"and {len(selected.years)} years to {args.output}"
    )
    print(f"Metadata: {metadata_path_for_cells(args.output)}")
    return 0
