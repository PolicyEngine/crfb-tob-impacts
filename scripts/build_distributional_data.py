"""Build per-reform, per-year distributional impact by income decile.

For each anchor year we run one baseline simulation to get each household's
baseline net income and income decile, then diff every reform's saved
reform-output H5 (already cached locally from the aggregation runs) against
that baseline by household. The result is the average and percentage change
in household net income within each baseline income decile.

All weighting goes through MicroDataFrame; no raw weight arrays are touched.

Usage:
    uv run python scripts/build_distributional_data.py \
        --output dashboard/public/data/distributional.json
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

import microdf as mdf
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BASELINE_DIR = REPO / "projected_datasets_v2pop"
ANCHOR_YEARS = [2026, 2030] + list(range(2035, 2101, 5))
REFORMS = [f"option{i}" for i in range(1, 13)] + ["reverse_roth", "tax93"]

# The reform-output H5s were cached locally by the aggregation runs. Static
# 2026-2070 live under the original prefix cache; 2075-2100 under the no-clone
# cache. Each entry maps a year to (cache_root, run_prefix).
STATIC_CACHE = REPO / "tmp" / "reform_full_h5_r2_cache_v2pop"
NOCLONE_CACHE = REPO / "tmp" / "r2_cache_noclone"


def scenario_path(year: int, reform: str) -> Path:
    if year <= 2070:
        return (
            STATIC_CACHE
            / "axiom-corpus/crfb/reform_full_h5/v2pop_tr2026_20260611"
            / "reform_full_h5"
            / f"year={year}"
            / f"reform={reform}"
            / "scenario.h5"
        )
    return (
        NOCLONE_CACHE
        / "axiom-corpus/crfb/reform_full_h5/v2pop_tr2026_noclone_20260612"
        / "reform_full_h5"
        / f"year={year}"
        / f"reform={reform}"
        / "scenario.h5"
    )


def baseline_households(year: int) -> pd.DataFrame:
    """Baseline household net income + decile + weight, by household_id."""
    from policyengine_us import Microsimulation

    from src.v2_pipeline import _tax_assumption_reform

    sim = Microsimulation(
        dataset=str(BASELINE_DIR / f"{year}.h5"),
        reform=_tax_assumption_reform(year),
    )
    hh_id = np.asarray(sim.calculate("household_id", period=year).values)
    net = np.asarray(
        sim.calculate("household_net_income", period=year).values, dtype=float
    )
    weight = np.asarray(
        sim.calculate("household_weight", period=year).values, dtype=float
    )
    frame = pd.DataFrame(
        {"household_id": hh_id, "baseline_net_income": net, "household_weight": weight}
    )
    # Population-weighted income deciles on baseline household net income.
    mdf_frame = mdf.MicroDataFrame(
        frame[["baseline_net_income"]], weights=frame["household_weight"]
    )
    ranks = mdf_frame["baseline_net_income"].rank(pct=True)
    frame["decile"] = np.clip(np.ceil(np.asarray(ranks) * 10), 1, 10).astype(int)
    del sim
    gc.collect()
    return frame


def reform_net_income(year: int, reform: str) -> pd.DataFrame:
    path = scenario_path(year, reform)
    if not path.exists():
        raise FileNotFoundError(path)
    with pd.HDFStore(path, mode="r") as store:
        hh = store["household"]
    return hh[["household_id", "household_net_income"]].rename(
        columns={"household_net_income": "reform_net_income"}
    )


def decile_impacts(baseline: pd.DataFrame, reform: pd.DataFrame) -> list[dict]:
    merged = baseline.merge(
        reform, on="household_id", how="inner", validate="one_to_one"
    )
    merged["change"] = merged["reform_net_income"] - merged["baseline_net_income"]
    rows: list[dict] = []
    for decile in range(1, 11):
        group = merged[merged["decile"] == decile]
        weighted = mdf.MicroDataFrame(
            group[["change", "baseline_net_income"]],
            weights=group["household_weight"],
        )
        total_change = float(weighted["change"].sum())
        total_baseline = float(weighted["baseline_net_income"].sum())
        household_count = float(group["household_weight"].sum())
        rows.append(
            {
                "decile": decile,
                "avg_change": round(total_change / household_count, 2)
                if household_count
                else 0.0,
                "pct_change": round(100.0 * total_change / total_baseline, 3)
                if total_baseline
                else 0.0,
                "total_change_billions": round(total_change / 1e9, 3),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "dashboard" / "public" / "data" / "distributional.json",
    )
    parser.add_argument("--years", default=None, help="Comma list; default all anchors")
    args = parser.parse_args()

    years = [int(y) for y in args.years.split(",")] if args.years else ANCHOR_YEARS
    data: dict[str, dict] = {reform: {} for reform in REFORMS}
    for year in years:
        print(f"baseline {year}…", flush=True)
        baseline = baseline_households(year)
        for reform in REFORMS:
            try:
                reform_frame = reform_net_income(year, reform)
            except FileNotFoundError:
                print(f"  {reform} {year}: scenario missing, skipping", file=sys.stderr)
                continue
            data[reform][str(year)] = decile_impacts(baseline, reform_frame)
        print(
            f"  {year}: {sum(str(year) in data[r] for r in REFORMS)} reforms",
            flush=True,
        )
        del baseline
        gc.collect()

    payload = {
        "schema": "crfb_distributional/v1",
        "metric": "change in household net income by baseline income decile",
        "anchor_years": years,
        "reforms": REFORMS,
        "note": (
            "Deciles rank households by baseline net income. avg_change is the "
            "mean dollar change in net income per household in the decile; "
            "pct_change is the decile's aggregate net-income change as a "
            "percent of its baseline net income. Computed from saved reform "
            "microdata against a baseline simulation; anchor years only."
        ),
        "data": data,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
