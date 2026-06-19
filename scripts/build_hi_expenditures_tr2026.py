from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "data" / "sources" / "tr2026" / "HI Cost and Income Rates.csv"
HI_PAYROLL = REPO / "dashboard" / "public" / "data" / "hi_taxable_payroll.csv"
OUTPUT = REPO / "data" / "hi_expenditures_tr2026.csv"
MANIFEST = REPO / "data" / "tr2026_sources.manifest.json"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_hi_cost_rates(source: Path = SOURCE) -> pd.DataFrame:
    """Return HI cost rates as decimals by calendar year."""

    with source.open(encoding="utf-8-sig") as handle:
        records = []
        for row in csv.reader(handle):
            year_cell = (row[0] if row else "").strip()
            if not year_cell.isdigit():
                continue
            try:
                year = int(year_cell)
                cost_rate_pct = float(row[1])
            except (IndexError, ValueError):
                continue
            records.append({"year": year, "cost_rate": cost_rate_pct / 100.0})
    frame = pd.DataFrame(records).drop_duplicates("year", keep="last")
    if frame.empty:
        raise ValueError(f"No HI cost-rate records parsed from {source}.")
    return frame


def build_hi_expenditures_tr2026(
    *,
    source: Path = SOURCE,
    hi_payroll_path: Path = HI_PAYROLL,
    output_path: Path = OUTPUT,
) -> pd.DataFrame:
    rates = extract_hi_cost_rates(source)
    payroll = pd.read_csv(hi_payroll_path)
    payroll = payroll[["year", "hi_taxable_payroll"]].copy()
    # Dashboard denominator file is in billions of nominal dollars. The legacy
    # expenditure schema stores dollars.
    payroll["hi_taxable_payroll"] = payroll["hi_taxable_payroll"].astype(float) * 1e9
    payroll["year"] = payroll["year"].astype(int)

    frame = payroll.merge(rates, on="year", how="inner")
    frame = frame[frame["year"].between(2035, 2100)].copy()
    if frame["year"].nunique() != 66:
        missing = sorted(set(range(2035, 2101)).difference(frame["year"]))
        raise ValueError(f"TR2026 HI expenditures missing years: {missing[:10]}")
    frame["hi_expenditures"] = frame["cost_rate"] * frame["hi_taxable_payroll"]
    frame = frame[
        ["year", "cost_rate", "hi_taxable_payroll", "hi_expenditures"]
    ].sort_values("year")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return frame


def update_manifest(
    *,
    output_path: Path = OUTPUT,
    manifest_path: Path = MANIFEST,
) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.setdefault("files", [])
    records = [
        {
            "file": str(SOURCE.relative_to(REPO)),
            "sha256": file_sha256(SOURCE),
            "source": (
                "https://www.cms.gov/files/zip/"
                "2026-expanded-supplementary-tables-figures.zip "
                "(retrieved direct, 2026-06-10)"
            ),
        },
        {
            "file": str(output_path.relative_to(REPO)),
            "sha256": file_sha256(output_path),
            "source": (
                "Derived from data/sources/tr2026/HI Cost and Income Rates.csv "
                "cost rates times dashboard/public/data/hi_taxable_payroll.csv "
                "TR2026-scaled HI taxable payroll."
            ),
        },
    ]
    record_paths = {record["file"] for record in records}
    files[:] = [item for item in files if item.get("file") not in record_paths]
    files.extend(records)

    notes = manifest.setdefault("notes", [])
    note = (
        "HI expenditures for balanced-fix scoring use TR2026 HI cost rates "
        "times the TR2026-adjusted HI taxable payroll denominator series."
    )
    if note not in notes:
        notes.append(note)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    frame = build_hi_expenditures_tr2026()
    update_manifest()
    print(f"wrote {OUTPUT} ({len(frame)} years)")
    print(frame[frame.year.isin([2035, 2050, 2075, 2100])].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
