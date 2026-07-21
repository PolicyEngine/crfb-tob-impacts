"""Build the per-reform net earnings response of labor-supply scoring.

For each behavioral endpoint cell (14 reforms x {2026, 2100}, run prefix
``lsrfix_behavioral_20260719`` — the corrected runs with the substitution
channel live), computes total earnings (employment + self-employment income,
person-weighted) and compares against the same year's baseline earnings.
Baseline earnings come from a static cell of the same year: static scoring
applies no labor-supply response, so its earnings equal the dataset inputs
and are reform-invariant (asserted against a second reform's static cell).

Behavioral scenario H5s are fetched from R2 (cached under
``tmp/lsrfix_behavioral_cells/``); credentials as in
``scripts/aggregate_reform_full_h5_results.py``.

Output: ``dashboard/public/data/earnings_response.csv`` with one row per
reform x endpoint year: baseline and behavioral earnings (billions) and the
percent change. The dashboard shows the percent when labor-response scoring
is active; intermediate years are not emitted (the dashboard interpolates
and labels them, matching the behavioral revenue convention).
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RUN_PREFIX = "lsrfix_behavioral_20260719"
BUCKET = "axiom-corpus"
CACHE = REPO / "tmp" / "lsrfix_behavioral_cells"
OUTPUT = REPO / "dashboard" / "public" / "data" / "earnings_response.csv"
REFORMS = [f"option{i}" for i in range(1, 13)] + ["reverse_roth", "tax93"]
YEARS = (2026, 2100)

STATIC_2026 = (
    REPO
    / "tmp/reform_full_h5_r2_cache_v2pop/axiom-corpus/crfb/reform_full_h5"
    / "v2pop_tr2026_20260611/reform_full_h5/year=2026/reform={reform}/scenario.h5"
)
STATIC_2100 = (
    REPO
    / "tmp/r2_cache_noclone/axiom-corpus/crfb/reform_full_h5"
    / "v2pop_tr2026_noclone_20260612/reform_full_h5/year=2100/reform={reform}/scenario.h5"
)


def _r2_client():
    spec = importlib.util.spec_from_file_location(
        "agg", Path(__file__).resolve().parent / "aggregate_reform_full_h5_results.py"
    )
    agg = importlib.util.module_from_spec(spec)
    sys.modules["agg"] = agg
    spec.loader.exec_module(agg)
    return agg._r2_client_from_env()


def total_earnings(scenario: Path) -> float:
    with pd.HDFStore(scenario, mode="r") as store:
        person = store["person"]
    earnings = person["employment_income"] + person["self_employment_income"]
    return float((earnings * person["person_weight"]).sum())


def baseline_earnings(year: int) -> float:
    template = STATIC_2026 if year == 2026 else STATIC_2100
    values = [
        total_earnings(Path(str(template).format(reform=reform)))
        for reform in ("option1", "option8")
    ]
    # Static scoring applies no labor-supply response, so earnings are the
    # dataset inputs and must be identical across reforms.
    assert abs(values[0] - values[1]) < 1e3, (year, values)
    return values[0]


def behavioral_scenario(client, year: int, reform: str) -> Path:
    dest = CACHE / f"year={year}" / f"reform={reform}" / "scenario.h5"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        key = (
            f"crfb/reform_full_h5/{RUN_PREFIX}/reform_full_h5"
            f"/year={year}/reform={reform}/scenario.h5"
        )
        client.download_file(BUCKET, key, str(dest))
        print(f"fetched {year}/{reform}", flush=True)
    return dest


def main() -> int:
    client = _r2_client()
    base = {year: baseline_earnings(year) for year in YEARS}
    rows = []
    for year in YEARS:
        for reform in REFORMS:
            behavioral = total_earnings(behavioral_scenario(client, year, reform))
            pct = behavioral / base[year] - 1
            rows.append(
                {
                    "reform_name": reform,
                    "year": year,
                    "baseline_earnings_billions": f"{base[year] / 1e9:.4f}",
                    "behavioral_earnings_billions": f"{behavioral / 1e9:.4f}",
                    "pct_change": f"{pct:.6f}",
                }
            )
            print(f"{reform} {year}: {pct * 100:+.3f}%", flush=True)
    with OUTPUT.open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUTPUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
