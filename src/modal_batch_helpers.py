from __future__ import annotations

import csv
from pathlib import Path


REFORM_HOUSEHOLD_METRICS_DIRNAME = "reform_household_metrics"
OBJECT_STORE_ROOT_PART = "results"


def stem_with_scoring(stem: str, scoring: str) -> str:
    suffix = f"_{scoring}"
    return stem if stem.endswith(suffix) else f"{stem}{suffix}"


def parse_years(years: str) -> list[int]:
    parsed: list[int] = []
    for part in years.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", maxsplit=1)
            parsed.extend(range(int(start), int(end) + 1))
        else:
            parsed.append(int(part))
    return parsed


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


def reform_household_metrics_start_year(
    raw: str | None,
    *,
    default: int | None = 2040,
) -> int | None:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"", "0", "false", "no", "off", "none"}:
        return None
    return int(value)


def reform_household_metrics_requested(
    year: int,
    start_year: int | None,
) -> bool:
    return start_year is not None and year >= start_year


def reform_household_metrics_artifact_dir(
    save_path: str | Path,
    *,
    year: int,
    reform_id: str,
    volume_root: str | Path = "/results",
) -> Path:
    save_path_value = str(save_path).strip("/")
    volume_path = Path(volume_root) / save_path_value
    if volume_path.suffix:
        root = (
            volume_path.parent.parent
            if volume_path.parent.name == reform_id
            else volume_path.parent
        )
    else:
        root = volume_path
    return (
        root / REFORM_HOUSEHOLD_METRICS_DIRNAME / f"year={year}" / f"reform={reform_id}"
    )


def object_store_key_for_path(
    path: str | Path,
    *,
    prefix: str,
) -> str:
    path_parts = Path(path).parts
    if OBJECT_STORE_ROOT_PART in path_parts:
        root_index = path_parts.index(OBJECT_STORE_ROOT_PART)
        relative_parts = path_parts[root_index + 1 :]
    else:
        relative_parts = (Path(path).name,)

    clean_prefix = prefix.strip("/")
    relative_key = "/".join(part.strip("/") for part in relative_parts if part)
    return f"{clean_prefix}/{relative_key}" if clean_prefix else relative_key
