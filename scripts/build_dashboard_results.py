"""Build the dashboard results.csv (static + behavioral, all years, with the
OASDI / Medicare-HI trust-fund decomposition) from:

  - results/reform_panel.json: exact static revenue deltas + behavioral
    endpoint multipliers per reform/year (scripts/assemble_reform_panel.py).
  - the decomposition endpoints (crfb-decomposition volume): per reform, the
    OASDI/HI/employer-tax weighted sums at 2026 and 2100.

The trust-fund split ratio is stable, so it is computed at the two endpoints and
linearly interpolated across years (the established method), then applied to the
exact revenue panel. Emits dashboard/public/data/results.csv with one row per
(reform, year, scoring_type).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFORMS = [
    "option1", "option2", "option3", "option4", "option5", "option6",
    "option7", "option8", "option9", "option10", "option11", "option12",
    "tax93", "reverse_roth",
]
LO, HI = 2026, 2100


def _interp(a: float, b: float, year: int) -> float:
    return a + (b - a) * ((year - LO) / (HI - LO))


def _ratio(impact: float, revenue: float) -> float:
    return impact / revenue if abs(revenue) > 1e-9 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decomp", default="/tmp/decomp_dl")
    args = ap.parse_args()

    panel = json.loads((ROOT / "results" / "reform_panel.json").read_text())
    years = panel["years"]

    # decomposition endpoints: {reform: {year: {baseline:{...}, reform:{...}}}}
    dec: dict = {}
    for p in Path(args.decomp).glob("*.json"):
        d = json.loads(p.read_text())
        dec.setdefault(d["reform_id"], {})[int(d["year"])] = d

    def impacts(reform: str, year: int) -> dict:
        cell = dec[reform][year]
        b, f = cell["baseline"], cell["reform"]
        return {
            "revenue": f["income_tax"] - b["income_tax"],
            "tob_oasdi": f["tob_revenue_oasdi"] - b["tob_revenue_oasdi"],
            "tob_hi": f["tob_revenue_medicare_hi"] - b["tob_revenue_medicare_hi"],
            "emp_ss": f["employer_ss_tax_income_tax_revenue"] - b["employer_ss_tax_income_tax_revenue"],
            "emp_hi": f["employer_medicare_tax_income_tax_revenue"] - b["employer_medicare_tax_income_tax_revenue"],
            "base_tob_oasdi": b["tob_revenue_oasdi"],
            "base_tob_hi": b["tob_revenue_medicare_hi"],
        }

    rows = []
    for r in REFORMS:
        has_both = r in dec and LO in dec[r] and HI in dec[r]
        ep = {y: impacts(r, y) for y in (LO, HI)} if has_both else None
        # endpoint ratios (component impact / revenue impact), stable across years
        if ep:
            rat = {
                k: {y: _ratio(ep[y][k], ep[y]["revenue"]) for y in (LO, HI)}
                for k in ("tob_oasdi", "tob_hi", "emp_ss", "emp_hi")
            }
        for scoring in ("static", "behavioral"):
            for y in years:
                cell = panel["reforms"][r]["by_year"][str(y)]
                rev = cell["static"] if scoring == "static" else cell["behavioral"]
                if rev is None:
                    continue
                if ep:
                    tob_oasdi = rev * _interp(rat["tob_oasdi"][LO], rat["tob_oasdi"][HI], y)
                    tob_hi = rev * _interp(rat["tob_hi"][LO], rat["tob_hi"][HI], y)
                    emp_ss = rev * _interp(rat["emp_ss"][LO], rat["emp_ss"][HI], y)
                    emp_hi = rev * _interp(rat["emp_hi"][LO], rat["emp_hi"][HI], y)
                    base_oasdi = _interp(ep[LO]["base_tob_oasdi"], ep[HI]["base_tob_oasdi"], y)
                    base_hi = _interp(ep[LO]["base_tob_hi"], ep[HI]["base_tob_hi"], y)
                else:  # no decomposition for this reform -> totals only
                    tob_oasdi = tob_hi = emp_ss = emp_hi = base_oasdi = base_hi = 0.0
                rows.append({
                    "reform_name": r,
                    "year": y,
                    "scoring_type": scoring,
                    "revenue_impact": rev / 1e9,
                    "baseline_tob_oasdi": base_oasdi / 1e9,
                    "baseline_tob_medicare_hi": base_hi / 1e9,
                    "tob_oasdi_impact": tob_oasdi / 1e9,
                    "tob_medicare_hi_impact": tob_hi / 1e9,
                    "tob_total_impact": (tob_oasdi + tob_hi) / 1e9,
                    "oasdi_net_impact": (tob_oasdi + emp_ss) / 1e9,
                    "hi_net_impact": (tob_hi + emp_hi) / 1e9,
                    "employer_ss_tax_revenue": emp_ss / 1e9,
                    "employer_medicare_tax_revenue": emp_hi / 1e9,
                })

    out = ROOT / "dashboard" / "public" / "data" / "results.csv"
    cols = list(rows[0].keys())
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    # root-compat copy (matches publish_dashboard_results.py behavior)
    (ROOT / "results.csv").write_text(out.read_text())
    print(f"wrote {out} ({len(rows)} rows: {len(REFORMS)} reforms x {len(years)} years x 2 scoring)")
    missing = [r for r in REFORMS if r not in dec]
    print(f"reforms missing decomposition (totals only): {missing or 'none'}")


if __name__ == "__main__":
    main()
