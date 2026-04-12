from __future__ import annotations

import csv
from pathlib import Path


def stem_with_scoring(stem: str, scoring: str) -> str:
    suffix = f"_{scoring}"
    return stem if stem.endswith(suffix) else f"{stem}{suffix}"


def parse_years(years: str) -> list[int]:
    if "-" in years:
        start, end = years.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(year.strip()) for year in years.split(",") if year.strip()]


def parse_cells_file(cells_file: str | Path) -> list[tuple[str, int]]:
    path = Path(cells_file)
    rows: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            reform_id = (
                row.get("reform_id")
                or row.get("reform_name")
                or row.get("reform")
                or ""
            ).strip()
            year_raw = (row.get("year") or "").strip()
            if not reform_id or not year_raw:
                continue
            cell = (reform_id, int(year_raw))
            if cell in seen:
                continue
            seen.add(cell)
            rows.append(cell)

    return rows


def cell_output_paths(output: str, scoring: str) -> tuple[Path, str, Path]:
    output_path = Path(output)
    stem = stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_path, stem, output_dir


def default_submission_manifest_path(
    repo_root: Path,
    stem: str,
    run_id: str,
) -> Path:
    return repo_root / "results" / "modal_submissions" / f"{stem}_{run_id}.json"
