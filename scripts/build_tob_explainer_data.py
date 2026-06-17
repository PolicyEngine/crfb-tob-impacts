"""Build the data behind the dashboard's "how benefit taxation works" explainer.

Two payloads, both computed rather than typed in:

- ``curves``: for single and joint retiree households at several Social
  Security benefit levels, the taxable share of benefits as non-benefit
  income rises — each point from a policyengine-us household simulation
  under 2026 current law.
- ``context``: population facts from the calibrated v2 baseline years —
  how many beneficiary households pay any tax on benefits now and at the
  far horizon, and where the revenue goes.

Statutory parameters (thresholds, inclusion rates) are read from the
policyengine-us parameter tree, never hardcoded.

Usage:
    uv run python scripts/build_tob_explainer_data.py \
        --baseline-dir projected_datasets_v2pop \
        --output dashboard/public/data/tob_explainer.json
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CURVE_YEAR = 2026
SS_BENEFIT_LEVELS = [18_000, 24_000, 36_000, 48_000]
OTHER_INCOME_GRID = list(range(0, 122_500, 2_500))
CONTEXT_YEARS = (2026, 2050, 2100)


def statutory_parameters() -> dict:
    from policyengine_us.system import system

    tax = system.parameters.gov.irs.social_security.taxability
    instant = f"{CURVE_YEAR}-01-01"
    return {
        "year": CURVE_YEAR,
        "source": (
            "IRC §86 as represented in policyengine-us parameters "
            "gov.irs.social_security.taxability"
        ),
        "base_threshold": {
            "SINGLE": float(tax.threshold.base.main.SINGLE(instant)),
            "JOINT": float(tax.threshold.base.main.JOINT(instant)),
        },
        "adjusted_base_threshold": {
            "SINGLE": float(tax.threshold.adjusted_base.main.SINGLE(instant)),
            "JOINT": float(tax.threshold.adjusted_base.main.JOINT(instant)),
        },
        "base_inclusion_rate": float(tax.rate.base.excess(instant)),
        "additional_inclusion_rate": float(tax.rate.additional.excess(instant)),
        "benefit_inclusion_cap": float(tax.rate.additional.benefit_cap(instant)),
        "combined_income_ss_fraction": float(tax.combined_income_ss_fraction(instant)),
    }


def household_situation(
    filing_status: str, ss_benefit: float, other_income: float
) -> dict:
    people = {
        "you": {
            "age": {CURVE_YEAR: 67},
            "social_security_retirement": {CURVE_YEAR: ss_benefit},
            "taxable_pension_income": {CURVE_YEAR: other_income},
        }
    }
    members = ["you"]
    if filing_status == "JOINT":
        people["spouse"] = {"age": {CURVE_YEAR: 67}}
        members.append("spouse")
    return {
        "people": people,
        "tax_units": {"tax_unit": {"members": members}},
        "families": {"family": {"members": members}},
        "spm_units": {"spm_unit": {"members": members}},
        "households": {
            "household": {"members": members, "state_name": {CURVE_YEAR: "TX"}}
        },
        "marital_units": (
            {"marital_unit": {"members": members}} if filing_status == "JOINT" else {}
        ),
    }


def build_curves() -> list[dict]:
    from policyengine_us import Simulation

    curves = []
    for filing_status in ("SINGLE", "JOINT"):
        for ss_benefit in SS_BENEFIT_LEVELS:
            points = []
            for other_income in OTHER_INCOME_GRID:
                sim = Simulation(
                    situation=household_situation(
                        filing_status, ss_benefit, other_income
                    )
                )
                taxable = float(
                    sim.calculate("taxable_social_security", CURVE_YEAR)[0]
                )
                points.append(
                    {
                        "other_income": other_income,
                        "taxable_amount": round(taxable, 2),
                        "taxable_share": round(taxable / ss_benefit, 4),
                    }
                )
            curves.append(
                {
                    "filing_status": filing_status,
                    "ss_benefit": ss_benefit,
                    "points": points,
                }
            )
            print(
                f"curve {filing_status} ${ss_benefit:,}: "
                f"max share {max(p['taxable_share'] for p in points):.0%}",
                flush=True,
            )
    return curves


def build_context(baseline_dir: Path) -> list[dict]:
    from policyengine_us import Microsimulation

    from src.pipeline import _tax_assumption_reform

    records = []
    for year in CONTEXT_YEARS:
        dataset = baseline_dir / f"{year}.h5"
        if not dataset.exists():
            print(f"context {year}: dataset missing, skipping", file=sys.stderr)
            continue
        sim = Microsimulation(
            dataset=str(dataset), reform=_tax_assumption_reform(year)
        )
        ss_hh = sim.calc("social_security", period=year, map_to="household")
        tob_oasdi_hh = sim.calc(
            "tob_revenue_oasdi", period=year, map_to="household"
        )
        tob_hi_hh = sim.calc(
            "tob_revenue_medicare_hi", period=year, map_to="household"
        )
        tob_hh = tob_oasdi_hh + tob_hi_hh
        tob_oasdi_total = sim.calc("tob_revenue_oasdi", period=year)
        tob_hi_total = sim.calc("tob_revenue_medicare_hi", period=year)
        beneficiary_households = float((ss_hh > 0).sum())
        paying_households = float(((ss_hh > 0) & (tob_hh > 0)).sum())
        records.append(
            {
                "year": year,
                "beneficiary_households": beneficiary_households,
                "tob_paying_households": paying_households,
                "share_of_beneficiary_households_paying": round(
                    paying_households / beneficiary_households, 4
                ),
                "tob_oasdi_billions": round(float(tob_oasdi_total.sum()) / 1e9, 1),
                "tob_medicare_hi_billions": round(float(tob_hi_total.sum()) / 1e9, 1),
            }
        )
        print(
            f"context {year}: {records[-1]['share_of_beneficiary_households_paying']:.1%} "
            f"of beneficiary households pay TOB",
            flush=True,
        )
        del sim
        gc.collect()
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", default="projected_datasets_v2pop")
    parser.add_argument(
        "--output", default="dashboard/public/data/tob_explainer.json"
    )
    args = parser.parse_args()

    from importlib.metadata import version

    payload = {
        "schema": "crfb_tob_explainer/v1",
        "policyengine_us_version": version("policyengine-us"),
        "curve_year": CURVE_YEAR,
        "parameters": statutory_parameters(),
        "curves": build_curves(),
        "context": build_context(REPO_ROOT / args.baseline_dir),
        "lineage": {
            "curves": (
                "policyengine-us household simulations under "
                f"{CURVE_YEAR} current law (post-OBBBA)"
            ),
            "context": (
                "calibrated v2 baseline year datasets "
                "(crfb-longrun-v2pop-tr2026-9f1260b-20260611)"
            ),
        },
    }
    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=1))
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
