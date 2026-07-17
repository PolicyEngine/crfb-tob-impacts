"""Aggregate certified tax_panel_2005 full-H5 cells into dollar rows.

Usage (main repo venv, cwd = crfb-tob-impacts):
  .venv/bin/python scripts/tax_panel_2005_aggregate.py rows

Pairs the certrepro reform legs with the SAME rebuilt datasets' baselines
(``tmp/magi100_certrepro_baselines.json`` — reform-independent, computed on
byte-identical datasets; see docs/current/magi100-provenance.md for why
published-baseline pairing is wrong at the far horizon), prints per-year
impacts with drift diagnostics, enforces the structural bound
``tax_panel_2005 <= option2`` (both cap taxable benefits at 85%), and writes
``tmp/tax_panel_2005_rows_dollars.json`` for the assembly script.
"""

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "PolicyEngine/crfb-cert"))

spec = importlib.util.spec_from_file_location(
    "agg",
    Path.home() / "PolicyEngine/crfb-cert/scripts/aggregate_reform_full_h5_results.py",
)
agg = importlib.util.module_from_spec(spec)
sys.modules["agg"] = agg
spec.loader.exec_module(agg)

import pandas as pd  # noqa: E402

MAIN = Path.home() / "PolicyEngine/crfb-tob-impacts"
RUN_PREFIX = "tax_panel_2005_certrepro_20260717"
ROOT = MAIN / "tmp/full_h5_tax_panel_2005" / RUN_PREFIX / "reform_full_h5"
RESULTS = MAIN / "dashboard/public/data/results.csv"
BASELINES = MAIN / "tmp/magi100_certrepro_baselines.json"
ANCHOR_YEARS = (2026, 2028, 2029, 2030, *range(2035, 2101, 5))


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] != "rows":
        print(__doc__)
        return 2

    cache = json.loads(BASELINES.read_text())
    published = pd.read_csv(RESULTS)
    published = published[published.scoring_type == "static"]
    option2 = published[published.reform_name == "option2"].set_index("year")

    out = []
    bound_ok = True
    for year in ANCHOR_YEARS:
        scenario = ROOT / f"year={year}" / "reform=tax_panel_2005" / "scenario.h5"
        if not scenario.exists():
            raise RuntimeError(
                f"missing scenario.h5 for {year}; refusing partial aggregation"
            )
        c = cache[str(year)]
        baseline = agg.BaselineResult(
            revenue=c["revenue"],
            tob_medicare_hi=c["tob_medicare_hi"],
            tob_oasdi=c["tob_oasdi"],
            tob_total=c["tob_total"],
            social_security=c["social_security"],
            taxable_payroll=c["taxable_payroll"],
            tax_assumption_name=c["tax_assumption_name"],
            tax_assumption_active=c["tax_assumption_active"],
        )
        totals = agg._aggregate_full_output_h5(scenario)
        row = agg.build_reform_result_from_aggregates(
            reform_id="tax_panel_2005",
            year=year,
            baseline=baseline,
            reform_totals=totals,
            employer_net_reforms=agg.MODAL_EMPLOYER_NET_REFORMS,
            default_net_impact_mode="direct",
            scoring_type="static",
        )
        impact = row["revenue_impact"] / 1e9
        pub_base = float(published[published.year == year].iloc[0]["baseline_revenue"])
        drift = (c["revenue"] / 1e9 / pub_base - 1) * 100
        o2 = float(option2.loc[year, "revenue_impact"])
        # Structural upper bound: option2 taxes 85% of benefits for everyone,
        # so any regime capped at 85% of benefits raises weakly less. The
        # published option2 rows share this certrepro family to ~0.00%
        # through 2070; at 2075+ the far-horizon baseline drift makes the
        # comparison indicative rather than exact.
        violated = impact > o2 + 0.5
        if violated and year <= 2070:
            bound_ok = False
        marker = " BOUND-VIOLATION" if violated else ""
        print(
            f"tax_panel_2005 {year}: impact {impact:+,.2f}B  "
            f"(option2 {o2:+,.2f}B, baseline drift {drift:+.2f}%)"
            f"{marker}"
        )
        out.append(row)

    dest = MAIN / "tmp/tax_panel_2005_rows_dollars.json"
    dest.write_text(json.dumps(out, indent=1, default=float))
    print(f"wrote {dest} ({len(out)} rows)")
    print("[bound]", "OK (<= option2 through 2070)" if bound_ok else "VIOLATED")
    return 0 if bound_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
