"""Regenerate distributional deciles for the cliff-fix years 2028/2029.

Uses the SAME inputs/logic as scripts/build_distributional_data.py, but pointed
at the certified cliff-fix artifacts (all local):
  - baseline: crfb-cert/projected_datasets_certrepro/{year}.h5 + the worker's
    current-law tax-assumption reform (trustees-2025-core-thresholds-v1)
  - reform output: certinfill scenario.h5 household tables
Run with crfb-cert/.venv (pe-us 1.700.2) so it matches the scenario H5 env.
"""
from __future__ import annotations
import sys, json, warnings
from pathlib import Path
warnings.filterwarnings("ignore")

CERT = "/Users/maxghenis/PolicyEngine/crfb-cert"
sys.path.insert(0, CERT)
import pandas as pd
import microdf as mdf
from policyengine_us import Microsimulation
from src.tax_assumption_loader import load_tax_assumption_reform_for_dataset

REFORMS = [f"option{i}" for i in range(1, 13)] + ["reverse_roth", "tax93"]
YEARS = [2028, 2029]
BASE = Path(CERT) / "projected_datasets_certrepro"
SCEN = Path(CERT) / "tmp/full_h5_certinfill/certinfill_9f1260b_20260625/reform_full_h5"


def baseline_households(year: int) -> mdf.MicroDataFrame:
    ds = str(BASE / f"{year}.h5")
    reform = load_tax_assumption_reform_for_dataset(ds, year)
    sim = Microsimulation(dataset=ds, reform=reform)
    hh_id = sim.calc("household_id", period=year).reset_index(drop=True)
    net = sim.calc("household_net_income", period=year)
    weights = net.weights.reset_index(drop=True)
    net = net.reset_index(drop=True)
    frame = mdf.MicroDataFrame(
        {
            "household_id": pd.Series(hh_id).reset_index(drop=True),
            "baseline_net_income": pd.Series(net).reset_index(drop=True),
        },
        weights=weights,
    )
    frame["decile"] = frame["baseline_net_income"].decile_rank().astype(int)
    return frame


def reform_net_income(year: int, reform: str) -> pd.DataFrame:
    p = SCEN / f"year={year}" / f"reform={reform}" / "scenario.h5"
    with pd.HDFStore(p, mode="r") as store:
        hh = store["household"]
    return hh[["household_id", "household_net_income"]].rename(
        columns={"household_net_income": "reform_net_income"}
    )


def decile_impacts(baseline, reform) -> list[dict]:
    merged = baseline.merge(reform, on="household_id", how="inner", validate="one_to_one")
    merged["change"] = merged["reform_net_income"] - merged["baseline_net_income"]
    rows: list[dict] = []
    for decile in range(1, 11):
        group = merged.loc[merged["decile"] == decile]
        if group.empty:
            rows.append({"decile": decile, "avg_change": 0.0, "pct_change": None, "total_change_billions": 0.0})
            continue
        total_change = float(group["change"].sum())
        total_baseline = float(group["baseline_net_income"].sum())
        avg_change = float(group["change"].mean())
        rows.append({
            "decile": decile,
            "avg_change": round(avg_change, 2),
            "pct_change": round(100.0 * total_change / total_baseline, 3) if total_baseline > 0 else None,
            "total_change_billions": round(total_change / 1e9, 3),
        })
    return rows


out: dict[str, dict] = {}
for y in YEARS:
    print(f"baseline {y}...", flush=True)
    b = baseline_households(y)
    for rf in REFORMS:
        out.setdefault(rf, {})[str(y)] = decile_impacts(b, reform_net_income(y, rf))
    print(f"  {y}: {len(REFORMS)} reforms", flush=True)

json.dump(out, open("/tmp/distrib_2028_2029.json", "w"))
# sanity: option7 (no senior deduction) should show the 2028->2029 cliff
print("\n=== SANITY: option7 (no senior deduction) avg_change by decile ===")
for y in ("2028", "2029"):
    vals = [r["avg_change"] for r in out["option7"][y]]
    print(f"  {y}: {vals}")
print("=== option1 (full repeal) avg_change by decile ===")
for y in ("2028", "2029"):
    vals = [r["avg_change"] for r in out["option1"][y]]
    print(f"  {y}: {vals}")
print("wrote /tmp/distrib_2028_2029.json")
