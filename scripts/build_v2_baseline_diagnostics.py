"""Compute the full baseline-aggregate battery from the v2 year datasets.

For every built year this simulates the artifact (with the Trustees
long-run tax assumption from 2035) and records calibrated aggregates next
to their TR2026 targets plus the *uncalibrated* by-products — income tax,
AGI, payroll taxes, income components, beneficiary and worker counts — so
the dashboard can show how every baseline series evolves through 2100 and
how far the free series sit from external references.

Usage:
    uv run python scripts/build_v2_baseline_diagnostics.py \
        --dataset-dir projected_datasets_v2 \
        --output dashboard/public/data/v2_baseline_diagnostics.csv
"""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# (csv_column, policyengine variable, how)
DOLLAR_AGGREGATES = (
    ("income_tax", "income_tax"),
    ("adjusted_gross_income", "adjusted_gross_income"),
    ("taxable_income", "taxable_income"),
    ("employment_income", "employment_income"),
    ("self_employment_income", "self_employment_income"),
    ("social_security", "social_security"),
    ("taxable_social_security", "taxable_social_security"),
    ("tob_revenue_oasdi", "tob_revenue_oasdi"),
    ("tob_revenue_medicare_hi", "tob_revenue_medicare_hi"),
    ("taxable_interest_income", "taxable_interest_income"),
    ("tax_exempt_interest_income", "tax_exempt_interest_income"),
    ("qualified_dividend_income", "qualified_dividend_income"),
    ("non_qualified_dividend_income", "non_qualified_dividend_income"),
    ("long_term_capital_gains", "long_term_capital_gains"),
    ("short_term_capital_gains", "short_term_capital_gains"),
    ("taxable_pension_income", "taxable_pension_income"),
    ("taxable_ira_distributions", "taxable_ira_distributions"),
    ("partnership_s_corp_income", "partnership_s_corp_income"),
    ("rental_income", "rental_income"),
    ("employee_social_security_tax", "employee_social_security_tax"),
    ("employee_medicare_tax", "employee_medicare_tax"),
    ("self_employment_social_security_tax", "self_employment_social_security_tax"),
    ("self_employment_medicare_tax", "self_employment_medicare_tax"),
)


def year_aggregates(dataset_path: Path, year: int) -> dict:
    from policyengine_us import Microsimulation

    from src.v2_pipeline import _tax_assumption_reform

    reform = _tax_assumption_reform(year)
    sim = Microsimulation(dataset=str(dataset_path), reform=reform)

    record: dict = {"year": year}
    for column, variable in DOLLAR_AGGREGATES:
        if variable not in sim.tax_benefit_system.variables:
            record[column] = None
            continue
        try:
            record[column] = float(sim.calculate(variable, period=year).sum())
        except Exception as error:  # noqa: BLE001 - diagnostic battery
            print(f"  {year} {variable}: {error}", file=sys.stderr)
            record[column] = None

    payroll = float(
        sim.calculate("taxable_earnings_for_social_security", period=year).sum()
    ) + float(
        sim.calculate(
            "social_security_taxable_self_employment_income", period=year
        ).sum()
    )
    record["ssa_taxable_payroll"] = payroll

    age = sim.calculate("age", period=year)
    weights = np.asarray(age.weights, dtype=float)
    ages = np.asarray(age.values)
    record["population"] = float(weights.sum())
    record["population_65_plus"] = float(weights[ages >= 65].sum())

    ss_person = sim.calculate("social_security", period=year, map_to="person")
    ss_values = np.asarray(ss_person.values)
    ss_weights = np.asarray(ss_person.weights, dtype=float)
    record["ss_beneficiary_persons"] = float(ss_weights[ss_values > 0].sum())

    earners = np.asarray(
        sim.calculate("payroll_tax_gross_wages", period=year).values
    ) + np.asarray(sim.calculate("taxable_self_employment_income", period=year).values)
    record["covered_worker_persons"] = float(ss_weights[earners > 0].sum())

    households = sim.calculate("household_id", period=year, map_to="household")
    record["household_count"] = float(np.asarray(households.weights).sum())

    tob_hh = sim.calculate(
        "tob_revenue_oasdi", period=year, map_to="household"
    ) + sim.calculate("tob_revenue_medicare_hi", period=year, map_to="household")
    tob_values = np.asarray(tob_hh.values)
    tob_weights = np.asarray(tob_hh.weights, dtype=float)
    record["tob_paying_households"] = float(tob_weights[tob_values > 0].sum())

    del sim
    gc.collect()
    return record


def attach_references(frame: pd.DataFrame) -> pd.DataFrame:
    aux = pd.read_csv(REPO_ROOT / "data" / "social_security_aux_tr2026.csv")
    population = pd.read_csv(REPO_ROOT / "data" / "SSPopJul_TR2026_interim.csv")
    pop_totals = population.groupby("Year").Total.sum()
    pop_65 = population[population.Age >= 65].groupby("Year").Total.sum()
    hi_payroll = pd.read_csv(
        REPO_ROOT / "dashboard" / "public" / "data" / "hi_taxable_payroll.csv"
    ).set_index("year")

    aux = aux.set_index("year")
    frame = frame.set_index("year")
    frame["target_population"] = pop_totals
    frame["target_population_65_plus"] = pop_65
    frame["target_social_security"] = aux.oasdi_cost_in_billion_nominal_usd * 1e9
    frame["target_ssa_taxable_payroll"] = (
        aux.taxable_payroll_in_billion_nominal_usd * 1e9
    )
    frame["target_tob_revenue_oasdi"] = aux.oasdi_tob_billions_nominal_usd * 1e9
    frame["target_tob_revenue_medicare_hi"] = aux.hi_tob_billions_nominal_usd * 1e9
    frame["gdp"] = aux.gdp_in_billion_nominal_usd * 1e9
    frame["reference_covered_workers"] = aux.covered_workers_thousands * 1e3
    frame["reference_oasdi_beneficiaries"] = aux.oasdi_beneficiaries_thousands * 1e3
    # Mechanical payroll-tax checks: statutory rates on the payroll bases.
    frame["reference_oasdi_payroll_tax"] = (
        0.124 * aux.taxable_payroll_in_billion_nominal_usd * 1e9
    )
    frame["reference_hi_payroll_tax"] = 0.029 * hi_payroll.hi_taxable_payroll * 1e9
    return frame.reset_index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default="projected_datasets_v2")
    parser.add_argument(
        "--output",
        default="dashboard/public/data/v2_baseline_diagnostics.csv",
    )
    parser.add_argument("--years", default=None, help="Comma list; default all")
    args = parser.parse_args()

    dataset_dir = REPO_ROOT / args.dataset_dir
    years = sorted(
        int(path.stem) for path in dataset_dir.glob("*.h5") if path.stem.isdigit()
    )
    if args.years:
        wanted = {int(y) for y in args.years.split(",")}
        years = [y for y in years if y in wanted]
    if not years:
        raise SystemExit(f"No year datasets in {dataset_dir}")

    records = []
    for year in years:
        print(f"computing {year}…", flush=True)
        records.append(year_aggregates(dataset_dir / f"{year}.h5", year))

    frame = attach_references(pd.DataFrame(records))
    output = REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    print(f"wrote {output}")

    show = frame[frame.year.isin([years[0], 2060, 2100])]
    for _, row in show.iterrows():
        print(
            f"  {int(row.year)}: income tax ${row.income_tax / 1e9:,.0f}B "
            f"({row.income_tax / row.gdp:.1%} of GDP), AGI/GDP "
            f"{row.adjusted_gross_income / row.gdp:.1%}, TOB/benefits "
            f"{(row.tob_revenue_oasdi + row.tob_revenue_medicare_hi) / row.social_security:.1%}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
