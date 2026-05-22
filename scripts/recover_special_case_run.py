from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_recover import download_volume_prefix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def default_output_root(output_prefix: str) -> Path:
    slug = output_prefix.strip("/").replace("/", "__")
    return REPO_ROOT / "results" / "recovered_special_case_runs" / slug


def read_result_rows(results_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not results_dir.exists():
        return rows
    for path in sorted(results_dir.glob("*_static_results.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader, None)
            if row is not None:
                rows.append(row)
    return rows


def years_from_rows(rows: list[dict[str, str]]) -> list[int]:
    years: list[int] = []
    for row in rows:
        value = row.get("year")
        if value not in (None, ""):
            years.append(int(float(value)))
    return sorted(years)


def common_value(rows: list[dict[str, str]], key: str) -> str | None:
    values = {row.get(key, "") for row in rows}
    values.discard("")
    if len(values) == 1:
        return values.pop()
    return None


def write_manifest(output_prefix: str, output_root: Path) -> Path:
    option13_rows = read_result_rows(output_root / "option13")
    option14_rows = read_result_rows(output_root / "option14")
    option13_years = years_from_rows(option13_rows)
    option14_years = years_from_rows(option14_rows)

    all_rows = option13_rows + option14_rows
    manifest = {
        "run_id": output_prefix,
        "output_prefix": output_prefix,
        "recovered_at": datetime.now().isoformat(),
        "local_output_root": str(output_root),
        "option13_dir": str(output_root / "option13"),
        "option14_dir": str(output_root / "option14"),
        "option13_years": option13_years,
        "option14_years": option14_years,
        "tax_assumption_factory": common_value(all_rows, "tax_assumption_factory"),
        "tax_assumption_start_year": common_value(
            all_rows,
            "tax_assumption_start_year",
        ),
        "tax_assumption_end_year": common_value(all_rows, "tax_assumption_end_year"),
        "option14_comparison_baseline": common_value(
            option14_rows,
            "comparison_baseline",
        ),
        "option14_stacked_reform": common_value(option14_rows, "stacked_reform"),
        "notes": (
            "Recovered paired static Option 13 and stacked Option 14 special-case "
            "outputs from the Modal results volume."
        ),
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    args = parse_args()
    output_root = args.output_root or default_output_root(args.output_prefix)
    recovered = download_volume_prefix(args.output_prefix, output_root)
    manifest_path = write_manifest(args.output_prefix, output_root)

    print(f"Recovered Modal volume prefix: {args.output_prefix}")
    print(f"Local output root: {output_root}")
    print(f"Recovery marker: {recovered}")
    print(f"Manifest: {manifest_path}")
    if (output_root / "option13").exists():
        print(f"Option 13 dir: {output_root / 'option13'}")
    if (output_root / "option14").exists():
        print(f"Option 14 dir: {output_root / 'option14'}")


if __name__ == "__main__":
    main()
