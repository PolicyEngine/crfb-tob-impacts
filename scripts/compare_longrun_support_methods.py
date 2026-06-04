"""Compare donor-supported and thin-reweighted long-run datasets.

This diagnostic checks whether two datasets that hit the same Trustees
aggregate targets also place tax-relevant income in similar parts of the tax
schedule. It is intended for late-horizon CRFB sentinel years, where sparse
microdata support can make reweight-only calibration mechanically clean but
policy-unstable.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from policyengine_us import Microsimulation

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.reforms import (  # noqa: E402
    get_option1_reform,
    get_option2_reform,
    get_option8_reform,
    get_option12_reform,
)
from src.tax_assumption_loader import (  # noqa: E402
    load_tax_assumption_reform,
    resolve_tax_assumption_module,
)


# These default to bundles produced by the local CRFB long-run pipeline, which
# live outside the repo. Override the directory with CRFB_LOCAL_RUNS_DIR, or pass
# explicit paths on the command line, to run on another machine.
LOCAL_RUNS_DIR = Path(
    os.environ.get(
        "CRFB_LOCAL_RUNS_DIR", str(Path.home() / "PolicyEngine" / "_local_runs")
    )
)
DEFAULT_SUPPORT_DATASET = str(
    LOCAL_RUNS_DIR / "crfb_py_bundle_2100_20260513" / "2100.h5"
)
DEFAULT_NO_SUPPORT_DATASET = str(
    LOCAL_RUNS_DIR / "crfb_py_bundle_2100_no_support_20260513" / "2100.h5"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "tmp" / "longrun_support_validation"

REFORM_FACTORIES = {
    "option1": get_option1_reform,
    "option2": get_option2_reform,
    "option8": get_option8_reform,
    "option12": get_option12_reform,
}

TOTAL_VARIABLES: tuple[tuple[str, str, str], ...] = (
    ("income_tax", "income_tax", "tax_unit"),
    ("income_tax_before_credits", "income_tax_before_credits", "tax_unit"),
    ("irs_gross_income", "irs_gross_income", "tax_unit"),
    ("adjusted_gross_income", "adjusted_gross_income", "tax_unit"),
    ("taxable_income", "taxable_income", "tax_unit"),
    ("taxable_social_security", "taxable_social_security", "tax_unit"),
    ("social_security", "social_security", "tax_unit"),
    ("employment_income", "employment_income", "tax_unit"),
    ("self_employment_income", "self_employment_income", "tax_unit"),
    ("tob_revenue_oasdi", "tob_revenue_oasdi", "tax_unit"),
    ("tob_revenue_medicare_hi", "tob_revenue_medicare_hi", "tax_unit"),
)

TAXABLE_INCOME_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("below_0", None, 0),
    ("0_to_100k", 0, 100_000),
    ("100k_to_500k", 100_000, 500_000),
    ("500k_to_1m", 500_000, 1_000_000),
    ("1m_to_2m", 1_000_000, 2_000_000),
    ("2m_plus", 2_000_000, None),
)

MARGINAL_RATE_BINS: tuple[tuple[str, float | None, float | None], ...] = (
    ("negative", None, 0),
    ("0_to_10pct", 0, 0.10),
    ("10_to_20pct", 0.10, 0.20),
    ("20_to_30pct", 0.20, 0.30),
    ("30_to_40pct", 0.30, 0.40),
    ("40_to_60pct", 0.40, 0.60),
    ("60pct_plus", 0.60, None),
)

# SSA Trustees 2025 Report, Table IV.B3, intermediate assumptions.
# https://www.ssa.gov/OACT/TR/2025/lr4b3.html
#
# The table reports covered workers with OASDI taxes due during the year and
# beneficiaries in current-payment status as of June 30. PolicyEngine person
# counts are annual positive-benefit/positive-taxable-earnings proxies, so these
# are validation holdouts rather than exact calibration constraints.
TRUSTEES_IVB3_HOLDOUTS_MILLIONS: dict[int, dict[str, float]] = {
    2100: {
        "covered_workers": 228.446,
        "oasi_beneficiaries": 96.987,
        "di_beneficiaries": 13.326,
        "oasdi_beneficiaries": 110.313,
    }
}


@dataclass(frozen=True)
class DatasetSpec:
    label: str
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2100)
    parser.add_argument("--support-dataset", default=DEFAULT_SUPPORT_DATASET)
    parser.add_argument("--no-support-dataset", default=DEFAULT_NO_SUPPORT_DATASET)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tax-assumption-module")
    parser.add_argument(
        "--tax-assumption-factory",
        default="create_trustees_core_thresholds_reform",
    )
    parser.add_argument("--tax-assumption-start-year", type=int, default=2035)
    parser.add_argument("--tax-assumption-end-year", type=int, default=2100)
    return parser.parse_args()


def metadata_path(dataset_path: Path) -> Path:
    return Path(f"{dataset_path}.metadata.json")


def load_metadata(dataset_path: Path) -> dict[str, Any]:
    path = metadata_path(dataset_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_baseline_tax_reform(args: argparse.Namespace):
    module_path = resolve_tax_assumption_module(args.tax_assumption_module)
    factories = [
        args.tax_assumption_factory,
        "create_wage_indexed_core_thresholds_reform",
        "create_trustees_core_thresholds_reform",
    ]
    errors: list[str] = []
    for factory in dict.fromkeys(factories):
        try:
            return load_tax_assumption_reform(
                module_path,
                factory,
                args.tax_assumption_start_year,
                args.tax_assumption_end_year,
            )
        except AttributeError as exc:
            errors.append(f"{factory}: {exc}")
    raise AttributeError(
        f"No supported tax assumption factory found in {module_path}: "
        + "; ".join(errors)
    )


def combine_reform(baseline_reform, reform):
    return (baseline_reform, reform) if baseline_reform is not None else reform


def make_sim(dataset: DatasetSpec, year: int, reform=None) -> Microsimulation:
    print(
        f"[sim] {dataset.label} year={year} reform={type(reform).__name__}",
        flush=True,
    )
    return Microsimulation(dataset=str(dataset.path), reform=reform)


def calc(sim: Microsimulation, variable: str, year: int, map_to: str = "tax_unit"):
    return sim.calculate(variable, period=year, map_to=map_to)


def weighted_sum(series, mask=None) -> float:
    if mask is None:
        return float(series.sum())
    return float((series * mask).sum())


def weighted_count(mask) -> float:
    return float(mask.astype(float).sum())


def make_mask(series, lower: float | None, upper: float | None):
    mask = series == series
    if lower is not None:
        mask &= series >= lower
    if upper is not None:
        mask &= series < upper
    return mask


def support_summary_rows(dataset: DatasetSpec) -> list[dict[str, Any]]:
    metadata = load_metadata(dataset.path)
    audit = metadata.get("calibration_audit", {})
    support = metadata.get("support_augmentation") or {}
    rows: list[dict[str, Any]] = []
    for key in (
        "positive_weight_count",
        "negative_weight_count",
        "effective_sample_size",
        "top_10_weight_share_pct",
        "top_100_weight_share_pct",
        "ss_total_positive_contributor_count",
        "ss_total_contributor_effective_sample_size",
        "payroll_total_positive_contributor_count",
        "payroll_total_contributor_effective_sample_size",
        "oasdi_tob_positive_contributor_count",
        "oasdi_tob_contributor_effective_sample_size",
        "hi_tob_positive_contributor_count",
        "hi_tob_contributor_effective_sample_size",
        "top_100_oasdi_tob_contribution_share_pct",
        "top_100_hi_tob_contribution_share_pct",
    ):
        rows.append(
            {
                "dataset": dataset.label,
                "section": "support",
                "metric": key,
                "value": audit.get(key),
            }
        )
    rows.append(
        {
            "dataset": dataset.label,
            "section": "support",
            "metric": "support_augmentation_name",
            "value": support.get("name", "none"),
        }
    )
    rows.append(
        {
            "dataset": dataset.label,
            "section": "support",
            "metric": "clone_household_count",
            "value": support.get("report_summary", {}).get("clone_household_count"),
        }
    )
    return rows


def baseline_total_rows(
    dataset: DatasetSpec,
    year: int,
    baseline_reform,
) -> tuple[list[dict[str, Any]], Microsimulation]:
    sim = make_sim(dataset, year, reform=baseline_reform)
    rows: list[dict[str, Any]] = []
    for metric, variable, map_to in TOTAL_VARIABLES:
        value = weighted_sum(calc(sim, variable, year, map_to=map_to))
        rows.append(
            {
                "dataset": dataset.label,
                "section": "baseline_total",
                "metric": metric,
                "value": value,
                "value_b": value / 1e9,
            }
        )
    taxable_payroll = weighted_sum(
        calc(sim, "taxable_earnings_for_social_security", year)
        + calc(sim, "social_security_taxable_self_employment_income", year)
    )
    rows.append(
        {
            "dataset": dataset.label,
            "section": "baseline_total",
            "metric": "taxable_payroll",
            "value": taxable_payroll,
            "value_b": taxable_payroll / 1e9,
        }
    )
    return rows, sim


def baseline_bin_rows(
    dataset: DatasetSpec,
    year: int,
    baseline_sim: Microsimulation,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    taxable_income = calc(baseline_sim, "taxable_income", year)
    metrics = {
        "tax_unit_count": taxable_income == taxable_income,
        "income_tax": calc(baseline_sim, "income_tax", year),
        "adjusted_gross_income": calc(baseline_sim, "adjusted_gross_income", year),
        "taxable_income": taxable_income,
        "social_security": calc(baseline_sim, "social_security", year),
        "taxable_social_security": calc(baseline_sim, "taxable_social_security", year),
        "taxable_payroll": calc(
            baseline_sim,
            "taxable_earnings_for_social_security",
            year,
        )
        + calc(
            baseline_sim,
            "social_security_taxable_self_employment_income",
            year,
        ),
    }
    totals = {
        key: weighted_count(value) if key == "tax_unit_count" else weighted_sum(value)
        for key, value in metrics.items()
    }
    for bin_label, lower, upper in TAXABLE_INCOME_BINS:
        mask = make_mask(taxable_income, lower, upper)
        for metric, series in metrics.items():
            value = weighted_count(mask) if metric == "tax_unit_count" else weighted_sum(series, mask)
            total = totals[metric]
            rows.append(
                {
                    "dataset": dataset.label,
                    "section": "baseline_taxable_income_bin",
                    "bin": bin_label,
                    "metric": metric,
                    "value": value,
                    "value_b": value / 1e9,
                    "share": value / total if total else None,
                }
            )
    return rows


def external_trustees_holdout_rows(
    dataset: DatasetSpec,
    year: int,
    baseline_sim: Microsimulation,
) -> list[dict[str, Any]]:
    targets = TRUSTEES_IVB3_HOLDOUTS_MILLIONS.get(year)
    if targets is None:
        return []

    taxable_wages = calc(
        baseline_sim,
        "taxable_earnings_for_social_security",
        year,
        map_to="person",
    )
    taxable_self_employment = calc(
        baseline_sim,
        "social_security_taxable_self_employment_income",
        year,
        map_to="person",
    )
    retirement = calc(baseline_sim, "social_security_retirement", year, map_to="person")
    survivors = calc(baseline_sim, "social_security_survivors", year, map_to="person")
    dependents = calc(baseline_sim, "social_security_dependents", year, map_to="person")
    disability = calc(baseline_sim, "social_security_disability", year, map_to="person")
    social_security = calc(baseline_sim, "social_security", year, map_to="person")

    model_counts = {
        "covered_workers": weighted_count((taxable_wages + taxable_self_employment) > 0)
        / 1e6,
        "oasi_beneficiaries": weighted_count(
            (retirement + survivors + dependents) > 0
        )
        / 1e6,
        "di_beneficiaries": weighted_count(disability > 0) / 1e6,
        "oasdi_beneficiaries": weighted_count(social_security > 0) / 1e6,
    }
    rows: list[dict[str, Any]] = []
    for metric, target_m in targets.items():
        model_m = model_counts[metric]
        error_m = model_m - target_m
        rows.append(
            {
                "dataset": dataset.label,
                "section": "external_trustees_holdout",
                "metric": metric,
                "value": model_m,
                "target": target_m,
                "error": error_m,
                "pct_error": error_m / target_m if target_m else None,
                "source": "SSA Trustees 2025 Table IV.B3 intermediate",
            }
        )
    return rows


def sentinel_rows(
    dataset: DatasetSpec,
    year: int,
    baseline_reform,
    baseline_income_tax: float,
) -> tuple[list[dict[str, Any]], dict[str, Microsimulation]]:
    rows: list[dict[str, Any]] = []
    sims: dict[str, Microsimulation] = {}
    for reform_id, factory in REFORM_FACTORIES.items():
        reform = combine_reform(baseline_reform, factory())
        sim = make_sim(dataset, year, reform=reform)
        sims[reform_id] = sim
        income_tax = weighted_sum(calc(sim, "income_tax", year))
        taxable_social_security = weighted_sum(calc(sim, "taxable_social_security", year))
        rows.extend(
            [
                {
                    "dataset": dataset.label,
                    "section": "policy_sentinel",
                    "reform": reform_id,
                    "metric": "income_tax",
                    "value": income_tax,
                    "value_b": income_tax / 1e9,
                },
                {
                    "dataset": dataset.label,
                    "section": "policy_sentinel",
                    "reform": reform_id,
                    "metric": "income_tax_impact",
                    "value": income_tax - baseline_income_tax,
                    "value_b": (income_tax - baseline_income_tax) / 1e9,
                },
                {
                    "dataset": dataset.label,
                    "section": "policy_sentinel",
                    "reform": reform_id,
                    "metric": "taxable_social_security",
                    "value": taxable_social_security,
                    "value_b": taxable_social_security / 1e9,
                },
            ]
        )
    return rows, sims


def option12_exposure_rows(
    dataset: DatasetSpec,
    year: int,
    option_sims: dict[str, Microsimulation],
) -> list[dict[str, Any]]:
    option1 = option_sims["option1"]
    option12 = option_sims["option12"]
    income_tax_delta = calc(option12, "income_tax", year) - calc(option1, "income_tax", year)
    employer_inclusion = calc(option12, "irs_gross_income", year) - calc(
        option1,
        "irs_gross_income",
        year,
    )
    option1_taxable_income = calc(option1, "taxable_income", year)
    option1_mtr = calc(option1, "marginal_tax_rate", year)

    rows: list[dict[str, Any]] = []
    total_inclusion = weighted_sum(employer_inclusion)
    total_tax_delta = weighted_sum(income_tax_delta)

    for metric, value in (
        ("employer_inclusion", total_inclusion),
        ("income_tax_delta_on_employer_inclusion", total_tax_delta),
        (
            "effective_tax_rate_on_employer_inclusion",
            total_tax_delta / total_inclusion if total_inclusion else None,
        ),
    ):
        is_rate = metric == "effective_tax_rate_on_employer_inclusion"
        rows.append(
            {
                "dataset": dataset.label,
                "section": "option12_exposure_total",
                "metric": metric,
                "value": value,
                "value_b": None if is_rate or value is None else value / 1e9,
            }
        )

    for grouping, bins, grouper in (
        ("option1_taxable_income_bin", TAXABLE_INCOME_BINS, option1_taxable_income),
        ("option1_marginal_rate_bin", MARGINAL_RATE_BINS, option1_mtr),
    ):
        for bin_label, lower, upper in bins:
            mask = make_mask(grouper, lower, upper)
            inclusion = weighted_sum(employer_inclusion, mask)
            tax_delta = weighted_sum(income_tax_delta, mask)
            rows.extend(
                [
                    {
                        "dataset": dataset.label,
                        "section": grouping,
                        "bin": bin_label,
                        "metric": "tax_unit_count",
                        "value": weighted_count(mask),
                    },
                    {
                        "dataset": dataset.label,
                        "section": grouping,
                        "bin": bin_label,
                        "metric": "employer_inclusion",
                        "value": inclusion,
                        "value_b": inclusion / 1e9,
                        "share": inclusion / total_inclusion if total_inclusion else None,
                    },
                    {
                        "dataset": dataset.label,
                        "section": grouping,
                        "bin": bin_label,
                        "metric": "income_tax_delta_on_employer_inclusion",
                        "value": tax_delta,
                        "value_b": tax_delta / 1e9,
                        "share": tax_delta / total_tax_delta if total_tax_delta else None,
                    },
                    {
                        "dataset": dataset.label,
                        "section": grouping,
                        "bin": bin_label,
                        "metric": "effective_tax_rate_on_employer_inclusion",
                        "value": tax_delta / inclusion if inclusion else None,
                    },
                ]
            )
    return rows


def write_report(
    output_path: Path,
    *,
    year: int,
    rows: pd.DataFrame,
) -> None:
    def value(
        dataset: str,
        section: str,
        metric: str,
        reform: str | None = None,
        *,
        column: str = "value_b",
    ):
        mask = (
            (rows["dataset"] == dataset)
            & (rows["section"] == section)
            & (rows["metric"] == metric)
        )
        if reform is not None:
            mask &= rows["reform"] == reform
        series = rows.loc[mask, column]
        if series.empty or series.isna().all():
            series = rows.loc[mask, "value"]
        if series.empty:
            return None
        numeric = pd.to_numeric(series, errors="coerce").dropna()
        return None if numeric.empty else float(numeric.iloc[0])

    support_baseline = value("support", "baseline_total", "income_tax")
    thin_baseline = value("no_support", "baseline_total", "income_tax")
    support_option12 = value(
        "support",
        "option12_exposure_total",
        "income_tax_delta_on_employer_inclusion",
    )
    thin_option12 = value(
        "no_support",
        "option12_exposure_total",
        "income_tax_delta_on_employer_inclusion",
    )
    support_rate = value(
        "support",
        "option12_exposure_total",
        "effective_tax_rate_on_employer_inclusion",
        column="value",
    )
    thin_rate = value(
        "no_support",
        "option12_exposure_total",
        "effective_tax_rate_on_employer_inclusion",
        column="value",
    )

    lines = [
        f"# Long-Run Support Method Validation ({year})",
        "",
        "This diagnostic compares the donor-supported long-run dataset with the",
        "thin reweight-only dataset on policy-relevant holdouts. Both datasets can",
        "hit the Trustees aggregate targets; the question is whether they place",
        "income and payroll-tax inclusion in similar parts of the tax schedule.",
        "",
        "## Headline",
        "",
        f"- Baseline income tax: support ${support_baseline:,.0f}B; "
        f"no support ${thin_baseline:,.0f}B.",
        f"- Option 12 tax on employer inclusion: support ${support_option12:,.0f}B; "
        f"no support ${thin_option12:,.0f}B.",
        f"- Effective tax rate on employer inclusion: support {support_rate:.1%}; "
        f"no support {thin_rate:.1%}.",
        "",
        "## External Trustees Holdouts",
        "",
        "SSA Trustees Table IV.B3 gives covered-worker and beneficiary counts",
        "that were not used as calibration targets. PolicyEngine counts are",
        "annual positive-amount proxies, so these are directional validation",
        "holdouts rather than exact constraints.",
        "",
    ]

    holdouts = rows[rows["section"] == "external_trustees_holdout"]
    if not holdouts.empty:
        lines.extend(
            [
                "| Metric | Trustees target (M) | Donor support (M) | Donor error | Thin reweighting (M) | Thin error |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for metric in (
            "covered_workers",
            "oasi_beneficiaries",
            "di_beneficiaries",
            "oasdi_beneficiaries",
        ):
            support = holdouts[
                (holdouts["dataset"] == "support") & (holdouts["metric"] == metric)
            ].iloc[0]
            thin = holdouts[
                (holdouts["dataset"] == "no_support") & (holdouts["metric"] == metric)
            ].iloc[0]
            label = metric.replace("_", " ")
            lines.append(
                f"| {label} | {support['target']:,.3f} | "
                f"{support['value']:,.3f} | {support['pct_error']:.1%} | "
                f"{thin['value']:,.3f} | {thin['pct_error']:.1%} |"
            )
        lines.append("")
        lines.extend(
            [
                "Thin reweighting is closer on covered workers, but donor support is",
                "closer on OASI, DI, and total OASDI beneficiary counts.",
                "",
            ]
        )

    lines.extend(
        [
        "A publishable choice should prefer the method that remains stable after",
        "adding income-tax-base and marginal-rate-exposure holdouts, not merely the",
        "method with fewer synthetic records.",
        "",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    year = args.year
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = [
        DatasetSpec("support", Path(args.support_dataset).expanduser()),
        DatasetSpec("no_support", Path(args.no_support_dataset).expanduser()),
    ]
    baseline_reform = load_baseline_tax_reform(args)

    rows: list[dict[str, Any]] = []
    for dataset in datasets:
        print(f"[dataset] {dataset.label}: {dataset.path}", flush=True)
        rows.extend(support_summary_rows(dataset))
        baseline_rows, baseline_sim = baseline_total_rows(dataset, year, baseline_reform)
        rows.extend(baseline_rows)
        baseline_income_tax = next(
            row["value"]
            for row in baseline_rows
            if row["metric"] == "income_tax"
        )
        rows.extend(baseline_bin_rows(dataset, year, baseline_sim))
        rows.extend(external_trustees_holdout_rows(dataset, year, baseline_sim))
        policy_rows, option_sims = sentinel_rows(
            dataset,
            year,
            baseline_reform,
            baseline_income_tax,
        )
        rows.extend(policy_rows)
        rows.extend(option12_exposure_rows(dataset, year, option_sims))

    result = pd.DataFrame(rows)
    csv_path = output_dir / f"longrun_support_method_validation_{year}.csv"
    report_path = output_dir / f"longrun_support_method_validation_{year}.md"
    result.to_csv(csv_path, index=False)
    write_report(report_path, year=year, rows=result)
    print(f"[wrote] {csv_path}", flush=True)
    print(f"[wrote] {report_path}", flush=True)


if __name__ == "__main__":
    main()
