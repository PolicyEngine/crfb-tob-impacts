from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import pandas as pd
from policyengine_core.periods import period as get_period
from policyengine_core.reforms import Reform

from .hi_expenditures import hi_expenditures_for_year
from .reform_full_h5_worker import materialize_tob_revenue_pair
from .reforms import (
    get_option1_reform,
    get_option2_reform,
    get_option8_reform,
    get_option12_reform,
)
from .tax_assumption_loader import (
    TaxAssumptionContract,
    load_tax_assumption_reform_for_dataset,
    tax_assumption_contract_for_dataset,
)
from .trust_fund_allocation import split_revenue_impacts


BALANCED_FIX_ANCHOR_YEARS = (2035, 2050, 2075, 2100)
BALANCED_FIX_SPOT_CHECK_YEARS = (2065,)
BALANCED_FIX_PUBLISH_ANCHOR_YEARS = tuple(
    sorted((*BALANCED_FIX_ANCHOR_YEARS, *BALANCED_FIX_SPOT_CHECK_YEARS))
)
BALANCED_FIX_REFORMS = ("option1", "option2", "option8", "option12")
BALANCED_FIX_HEAVY_SIMS_PER_YEAR = 7
BALANCED_FIX_EMPLOYER_NET_REFORMS = frozenset({"option12"})

SS_INCOME_VARIABLES = (
    "employee_social_security_tax",
    "employer_social_security_tax",
    "self_employment_social_security_tax",
    "tob_revenue_oasdi",
)
HI_INCOME_VARIABLES = (
    "employee_medicare_tax",
    "employer_medicare_tax",
    "self_employment_medicare_tax",
    "additional_medicare_tax",
    "tob_revenue_medicare_hi",
)
PAYROLL_RATE_PARAMETER_PATHS = {
    "ss_employee": "gov.irs.payroll.social_security.rate.employee",
    "ss_employer": "gov.irs.payroll.social_security.rate.employer",
    "hi_employee": "gov.irs.payroll.medicare.rate.employee",
    "hi_employer": "gov.irs.payroll.medicare.rate.employer",
}
RESULT_DOLLAR_COLUMNS = (
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_total",
    "reform_tob_total",
    "tob_total_impact",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_gain",
    "hi_gain",
    "oasdi_loss",
    "hi_loss",
    "oasdi_net_impact",
    "hi_net_impact",
    "solvent_oasdi_impact",
    "solvent_medicare_hi_impact",
    "solvent_general_fund_impact",
)
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_CSV = REPO_ROOT / "results.csv"


STATIC_REFORM_FUNCTIONS = {
    "option1": get_option1_reform,
    "option2": get_option2_reform,
    "option8": get_option8_reform,
    "option12": get_option12_reform,
}


def dataset_microsimulation(dataset: str | Path, reform: Any = None, **kwargs: Any):
    """Build a microsimulation on an already-certified CRFB H5.

    Balanced-fix has to match the live full-H5 production rows, whose baseline
    files record `policyengine_us.version == 1.700.2`. The Modal runner validates
    that metadata before scoring; after that check, direct `policyengine_us`
    construction is the narrowest path because old `policyengine.py` manifests
    do not certify that exact patch release.
    """

    from policyengine_us import Microsimulation

    return Microsimulation(dataset=str(dataset), reform=reform, **kwargs)


@dataclass(frozen=True)
class BaselineResult:
    revenue: float
    tob_medicare_hi: float
    tob_oasdi: float
    tob_total: float
    social_security: float
    taxable_payroll: float
    tax_assumption_name: str | None = None
    tax_assumption_active: bool = False


@dataclass(frozen=True)
class ScenarioAggregate:
    revenue: float
    tob_medicare_hi: float
    tob_oasdi: float
    tob_total: float
    social_security: float
    taxable_payroll: float
    employer_ss_tax_revenue: float
    employer_medicare_tax_revenue: float


def baseline_result_from_aggregate(
    aggregate: ScenarioAggregate,
    *,
    tax_assumption_name: str | None = None,
    tax_assumption_active: bool = False,
) -> BaselineResult:
    return BaselineResult(
        revenue=aggregate.revenue,
        tob_medicare_hi=aggregate.tob_medicare_hi,
        tob_oasdi=aggregate.tob_oasdi,
        tob_total=aggregate.tob_total,
        social_security=aggregate.social_security,
        taxable_payroll=aggregate.taxable_payroll,
        tax_assumption_name=tax_assumption_name,
        tax_assumption_active=tax_assumption_active,
    )


def _default_net_impacts(
    tob_oasdi_impact: float,
    tob_medicare_impact: float,
    *,
    default_net_impact_mode: str = "zero",
) -> dict[str, float]:
    if default_net_impact_mode == "direct":
        oasdi_net = tob_oasdi_impact
        hi_net = tob_medicare_impact
    else:
        oasdi_net = 0.0
        hi_net = 0.0
    return {
        "employer_ss_tax_revenue": 0.0,
        "employer_medicare_tax_revenue": 0.0,
        "oasdi_gain": 0.0,
        "hi_gain": 0.0,
        "oasdi_loss": 0.0,
        "hi_loss": 0.0,
        "oasdi_net_impact": oasdi_net,
        "hi_net_impact": hi_net,
    }


def build_reform_result_from_aggregates(
    *,
    reform_id: str,
    year: int,
    baseline: BaselineResult,
    reform_totals: ScenarioAggregate,
    employer_net_reforms: Iterable[str],
    default_net_impact_mode: str = "zero",
    scoring_type: str = "static",
) -> dict[str, float | int | str | bool]:
    revenue_impact = reform_totals.revenue - baseline.revenue
    tob_medicare_impact = reform_totals.tob_medicare_hi - baseline.tob_medicare_hi
    tob_oasdi_impact = reform_totals.tob_oasdi - baseline.tob_oasdi
    tob_total_impact = reform_totals.tob_total - baseline.tob_total
    allocation_impacts = _default_net_impacts(
        tob_oasdi_impact,
        tob_medicare_impact,
        default_net_impact_mode=default_net_impact_mode,
    )
    if reform_id in set(employer_net_reforms):
        oasdi_loss = baseline.tob_oasdi - reform_totals.tob_oasdi
        hi_loss = baseline.tob_medicare_hi - reform_totals.tob_medicare_hi
        allocation_impacts = {
            "employer_ss_tax_revenue": reform_totals.employer_ss_tax_revenue,
            "employer_medicare_tax_revenue": (
                reform_totals.employer_medicare_tax_revenue
            ),
            "oasdi_gain": reform_totals.employer_ss_tax_revenue,
            "hi_gain": reform_totals.employer_medicare_tax_revenue,
            "oasdi_loss": oasdi_loss,
            "hi_loss": hi_loss,
            "oasdi_net_impact": reform_totals.employer_ss_tax_revenue - oasdi_loss,
            "hi_net_impact": reform_totals.employer_medicare_tax_revenue - hi_loss,
        }

    return {
        "reform_name": reform_id,
        "year": year,
        "baseline_tax_assumption_name": baseline.tax_assumption_name or "",
        "baseline_tax_assumption_active": baseline.tax_assumption_active,
        "baseline_revenue": baseline.revenue,
        "reform_revenue": reform_totals.revenue,
        "revenue_impact": revenue_impact,
        "baseline_tob_medicare_hi": baseline.tob_medicare_hi,
        "reform_tob_medicare_hi": reform_totals.tob_medicare_hi,
        "tob_medicare_hi_impact": tob_medicare_impact,
        "baseline_tob_oasdi": baseline.tob_oasdi,
        "reform_tob_oasdi": reform_totals.tob_oasdi,
        "tob_oasdi_impact": tob_oasdi_impact,
        "baseline_tob_total": baseline.tob_total,
        "reform_tob_total": reform_totals.tob_total,
        "tob_total_impact": tob_total_impact,
        "scoring_type": scoring_type,
        **allocation_impacts,
    }


@dataclass(frozen=True)
class TrustFundGap:
    ss_income: float
    ss_benefits: float
    ss_gap: float
    hi_income: float
    hi_expenditures: float
    hi_gap: float

    def to_dict(self) -> dict[str, float]:
        return {
            "ss_income": float(self.ss_income),
            "ss_benefits": float(self.ss_benefits),
            "ss_gap": float(self.ss_gap),
            "hi_income": float(self.hi_income),
            "hi_expenditures": float(self.hi_expenditures),
            "hi_gap": float(self.hi_gap),
        }


@dataclass(frozen=True)
class PayrollRates:
    ss_employee: float
    ss_employer: float
    hi_employee: float
    hi_employer: float

    def to_dict(self) -> dict[str, float]:
        return {
            "ss_employee": float(self.ss_employee),
            "ss_employer": float(self.ss_employer),
            "hi_employee": float(self.hi_employee),
            "hi_employer": float(self.hi_employer),
        }


@dataclass(frozen=True)
class SolventBaselineState:
    year: int
    dataset_path: str
    current_law_reform: Any | None
    tax_assumption_contract: TaxAssumptionContract
    hi_expenditures: float
    gap_before: TrustFundGap
    gap_after_stage1: TrustFundGap
    gap_after_final: TrustFundGap
    benefit_multiplier: float
    benefit_cut: float
    ss_rate_increase: float
    hi_rate_increase: float
    base_rates: PayrollRates
    final_rates: PayrollRates
    rate_reform_dict: dict[str, dict[str, float]]
    rate_reform: Any
    reduced_social_security: np.ndarray
    current_law_aggregate: ScenarioAggregate

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "year": int(self.year),
            "dataset_path": self.dataset_path,
            "tax_assumption_name": self.tax_assumption_contract.name,
            "tax_assumption_active": self.tax_assumption_contract.active,
            "hi_expenditures": float(self.hi_expenditures),
            "gap_before": self.gap_before.to_dict(),
            "gap_after_stage1": self.gap_after_stage1.to_dict(),
            "gap_after_final": self.gap_after_final.to_dict(),
            "benefit_multiplier": float(self.benefit_multiplier),
            "benefit_cut": float(self.benefit_cut),
            "ss_rate_increase": float(self.ss_rate_increase),
            "hi_rate_increase": float(self.hi_rate_increase),
            "base_rates": self.base_rates.to_dict(),
            "final_rates": self.final_rates.to_dict(),
            "rate_reform_dict": self.rate_reform_dict,
        }


@dataclass(frozen=True)
class CrossCheckResult:
    year: int
    current_law_revenue_billions: float
    live_baseline_revenue_billions: float
    current_law_oasdi_billions: float
    live_baseline_oasdi_billions: float
    revenue_relative_error: float
    oasdi_relative_error: float
    tolerance: float

    @property
    def passed(self) -> bool:
        return (
            self.revenue_relative_error <= self.tolerance
            and self.oasdi_relative_error <= self.tolerance
        )

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "year": int(self.year),
            "current_law_revenue_billions": float(self.current_law_revenue_billions),
            "live_baseline_revenue_billions": float(
                self.live_baseline_revenue_billions
            ),
            "current_law_oasdi_billions": float(self.current_law_oasdi_billions),
            "live_baseline_oasdi_billions": float(self.live_baseline_oasdi_billions),
            "revenue_relative_error": float(self.revenue_relative_error),
            "oasdi_relative_error": float(self.oasdi_relative_error),
            "tolerance": float(self.tolerance),
            "passed": self.passed,
        }


def balanced_fix_sim_count(years: Iterable[int]) -> int:
    """Return the expected heavy microsimulation count for balanced-fix scoring."""

    return len(tuple(years)) * BALANCED_FIX_HEAVY_SIMS_PER_YEAR


def balanced_fix_cost_estimate(
    years: Iterable[int],
    *,
    low_per_heavy_sim: float = 150 / 98,
    high_per_heavy_sim: float = 400 / 98,
) -> dict[str, float | int]:
    heavy_sims = balanced_fix_sim_count(years)
    return {
        "heavy_sims": heavy_sims,
        "low_usd": heavy_sims * low_per_heavy_sim,
        "high_usd": heavy_sims * high_per_heavy_sim,
    }


def _period_span(year: int) -> str:
    return f"{int(year)}-01-01.{int(year)}-12-31"


def _compose_reforms(*reforms: Any | None) -> Any | None:
    active = tuple(reform for reform in reforms if reform is not None)
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return active


def _parameter_value(root: Any, dotted_path: str) -> float:
    value = root
    for part in dotted_path.split("."):
        value = getattr(value, part)
    return float(value)


def _calculate_sum(
    sim: Any,
    variable_name: str,
    *,
    year: int,
    map_to: str | None = None,
) -> float:
    if map_to is None:
        values = sim.calculate(variable_name, period=year)
    else:
        values = sim.calculate(variable_name, period=year, map_to=map_to)
    return float(values.sum())


def compute_trust_fund_gap(
    sim: Any,
    *,
    year: int,
    hi_expenditures: float,
    materialize_tob: bool = True,
    progress: Callable[[str], None] | None = None,
) -> TrustFundGap:
    """Compute SS and HI gaps with MicroSeries sums only."""

    if materialize_tob:
        materialize_tob_revenue_pair(sim, year=year, progress=progress)
    ss_income = sum(
        _calculate_sum(sim, name, year=year) for name in SS_INCOME_VARIABLES
    )
    ss_benefits = _calculate_sum(sim, "social_security", year=year)
    hi_income = sum(
        _calculate_sum(sim, name, year=year) for name in HI_INCOME_VARIABLES
    )
    return TrustFundGap(
        ss_income=ss_income,
        ss_benefits=ss_benefits,
        ss_gap=ss_income - ss_benefits,
        hi_income=hi_income,
        hi_expenditures=float(hi_expenditures),
        hi_gap=hi_income - float(hi_expenditures),
    )


def payroll_rates_from_sim(sim: Any, *, year: int) -> PayrollRates:
    parameters = sim.tax_benefit_system.parameters(get_period(year))
    values = {
        name: _parameter_value(parameters, path)
        for name, path in PAYROLL_RATE_PARAMETER_PATHS.items()
    }
    return PayrollRates(**values)


def build_rate_reform_dict(
    *,
    year: int,
    base_rates: PayrollRates,
    ss_rate_increase: float,
    hi_rate_increase: float,
) -> dict[str, dict[str, float]]:
    final_rates = PayrollRates(
        ss_employee=base_rates.ss_employee + ss_rate_increase / 2,
        ss_employer=base_rates.ss_employer + ss_rate_increase / 2,
        hi_employee=base_rates.hi_employee + hi_rate_increase / 2,
        hi_employer=base_rates.hi_employer + hi_rate_increase / 2,
    )
    if min(final_rates.to_dict().values()) < 0:
        raise ValueError(
            f"Balanced-fix rate reform would set negative rates: {final_rates}"
        )

    span = _period_span(year)
    return {
        "gov.irs.payroll.social_security.rate.employee": {
            span: final_rates.ss_employee
        },
        "gov.irs.payroll.social_security.rate.employer": {
            span: final_rates.ss_employer
        },
        "gov.irs.payroll.medicare.rate.employee": {span: final_rates.hi_employee},
        "gov.irs.payroll.medicare.rate.employer": {span: final_rates.hi_employer},
    }


def rate_reform_from_dict(rate_reform_dict: Mapping[str, Mapping[str, float]]) -> Any:
    return Reform.from_dict(dict(rate_reform_dict), country_id="us")


def compute_scenario_aggregate_from_sim(
    sim: Any,
    *,
    year: int,
    progress: Callable[[str], None] | None = None,
) -> ScenarioAggregate:
    """Aggregate a prepared sim, including sims with set_input benefit cuts."""

    materialize_tob_revenue_pair(sim, year=year, progress=progress)
    tob_medicare_hi = _calculate_sum(
        sim,
        "tob_revenue_medicare_hi",
        year=year,
        map_to="household",
    )
    tob_oasdi = _calculate_sum(
        sim,
        "tob_revenue_oasdi",
        year=year,
        map_to="household",
    )
    taxable_payroll = _calculate_sum(
        sim,
        "taxable_earnings_for_social_security",
        year=year,
        map_to="household",
    ) + _calculate_sum(
        sim,
        "social_security_taxable_self_employment_income",
        year=year,
        map_to="household",
    )
    return ScenarioAggregate(
        revenue=_calculate_sum(sim, "income_tax", year=year, map_to="household"),
        tob_medicare_hi=tob_medicare_hi,
        tob_oasdi=tob_oasdi,
        tob_total=tob_oasdi + tob_medicare_hi,
        social_security=_calculate_sum(
            sim,
            "social_security",
            year=year,
            map_to="household",
        ),
        taxable_payroll=taxable_payroll,
        employer_ss_tax_revenue=_calculate_sum(
            sim,
            "employer_ss_tax_income_tax_revenue",
            year=year,
            map_to="household",
        ),
        employer_medicare_tax_revenue=_calculate_sum(
            sim,
            "employer_medicare_tax_income_tax_revenue",
            year=year,
            map_to="household",
        ),
    )


def build_solvent_baseline_state(
    *,
    year: int,
    dataset_path: str | Path,
    hi_expenditures: float | None = None,
    progress: Callable[[str], None] | None = None,
) -> SolventBaselineState:
    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    dataset_path = str(dataset_path)
    emit("resolving tax-assumption contract")
    tax_assumption_contract = tax_assumption_contract_for_dataset(dataset_path, year)
    current_law_reform = load_tax_assumption_reform_for_dataset(dataset_path, year)
    hi_data = hi_expenditures_for_year(year)
    hi_expenditures_value = (
        float(hi_expenditures)
        if hi_expenditures is not None
        else float(hi_data["hi_expenditures"])
    )

    emit("building current-law simulation")
    base = dataset_microsimulation(
        dataset_path,
        reform=current_law_reform,
        start_instant=f"{year}-01-01",
    )
    emit("aggregating current-law simulation")
    current_law_aggregate = compute_scenario_aggregate_from_sim(
        base,
        year=year,
        progress=lambda message: emit(f"current-law aggregate: {message}"),
    )
    emit("computing current-law trust-fund gap")
    gap_before = compute_trust_fund_gap(
        base,
        year=year,
        hi_expenditures=hi_expenditures_value,
        materialize_tob=False,
    )
    emit("reading current-law Social Security vector")
    social_security = base.calculate("social_security", period=year)
    ss_benefits = float(social_security.sum())
    if ss_benefits <= 0:
        raise ValueError(f"Social Security benefits are nonpositive in {year}.")
    ss_shortfall = abs(min(gap_before.ss_gap, 0.0))
    benefit_cut = ss_shortfall * 0.5
    benefit_multiplier = 1 - benefit_cut / ss_benefits
    if not 0 <= benefit_multiplier <= 1:
        raise ValueError(
            f"Balanced-fix benefit multiplier is outside [0, 1]: {benefit_multiplier}"
        )
    # This is not aggregation. The Stage-1 benefit cut is a required set_input
    # vector, and the spec requires reusing this exact vector for every sim.
    reduced_social_security = np.asarray(social_security.values) * benefit_multiplier

    emit("building Stage-1 benefit-cut simulation")
    stage1 = dataset_microsimulation(
        dataset_path,
        reform=current_law_reform,
        start_instant=f"{year}-01-01",
    )
    stage1.set_input("social_security", year, reduced_social_security)
    emit("computing Stage-1 trust-fund gap")
    gap_after_stage1 = compute_trust_fund_gap(
        stage1,
        year=year,
        hi_expenditures=hi_expenditures_value,
        progress=lambda message: emit(f"Stage-1 gap: {message}"),
    )
    emit("computing payroll denominators")
    oasdi_taxable_payroll = _calculate_sum(
        stage1,
        "taxable_earnings_for_social_security",
        year=year,
    )
    hi_taxable_payroll = _calculate_sum(stage1, "payroll_tax_gross_wages", year=year)
    if oasdi_taxable_payroll <= 0 or hi_taxable_payroll <= 0:
        raise ValueError(
            "Balanced-fix payroll denominators must be positive: "
            f"OASDI={oasdi_taxable_payroll}, HI={hi_taxable_payroll}"
        )
    ss_rate_increase = (
        abs(gap_after_stage1.ss_gap) / oasdi_taxable_payroll
        if gap_after_stage1.ss_gap < 0
        else 0.0
    )
    hi_rate_increase = (
        abs(gap_after_stage1.hi_gap) / hi_taxable_payroll
        if gap_after_stage1.hi_gap < 0
        else -gap_after_stage1.hi_gap / hi_taxable_payroll
    )
    base_rates = payroll_rates_from_sim(stage1, year=year)
    rate_reform_dict = build_rate_reform_dict(
        year=year,
        base_rates=base_rates,
        ss_rate_increase=ss_rate_increase,
        hi_rate_increase=hi_rate_increase,
    )
    rate_reform = rate_reform_from_dict(rate_reform_dict)
    final_rates = PayrollRates(
        ss_employee=base_rates.ss_employee + ss_rate_increase / 2,
        ss_employer=base_rates.ss_employer + ss_rate_increase / 2,
        hi_employee=base_rates.hi_employee + hi_rate_increase / 2,
        hi_employer=base_rates.hi_employer + hi_rate_increase / 2,
    )

    emit("building final solvent simulation")
    final_sim = build_solvent_sim(
        year=year,
        dataset_path=dataset_path,
        current_law_reform=current_law_reform,
        rate_reform=rate_reform,
        reduced_social_security=reduced_social_security,
    )
    emit("computing final trust-fund gap")
    gap_after_final = compute_trust_fund_gap(
        final_sim,
        year=year,
        hi_expenditures=hi_expenditures_value,
        progress=lambda message: emit(f"final gap: {message}"),
    )

    return SolventBaselineState(
        year=year,
        dataset_path=dataset_path,
        current_law_reform=current_law_reform,
        tax_assumption_contract=tax_assumption_contract,
        hi_expenditures=hi_expenditures_value,
        gap_before=gap_before,
        gap_after_stage1=gap_after_stage1,
        gap_after_final=gap_after_final,
        benefit_multiplier=benefit_multiplier,
        benefit_cut=benefit_cut,
        ss_rate_increase=ss_rate_increase,
        hi_rate_increase=hi_rate_increase,
        base_rates=base_rates,
        final_rates=final_rates,
        rate_reform_dict=rate_reform_dict,
        rate_reform=rate_reform,
        reduced_social_security=reduced_social_security,
        current_law_aggregate=current_law_aggregate,
    )


def build_solvent_sim(
    *,
    year: int,
    dataset_path: str | Path,
    current_law_reform: Any | None,
    rate_reform: Any,
    reduced_social_security: np.ndarray,
    extra_reform: Any | None = None,
) -> Any:
    sim = dataset_microsimulation(
        str(dataset_path),
        reform=_compose_reforms(current_law_reform, rate_reform, extra_reform),
        start_instant=f"{year}-01-01",
    )
    sim.set_input("social_security", year, reduced_social_security)
    return sim


def build_solvent_sim_from_state(
    state: SolventBaselineState,
    *,
    extra_reform: Any | None = None,
) -> Any:
    return build_solvent_sim(
        year=state.year,
        dataset_path=state.dataset_path,
        current_law_reform=state.current_law_reform,
        rate_reform=state.rate_reform,
        reduced_social_security=state.reduced_social_security,
        extra_reform=extra_reform,
    )


def _relative_error(actual: float, expected: float) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return abs(actual - expected) / abs(expected)


def current_law_cross_check(
    *,
    year: int,
    current_law_aggregate: ScenarioAggregate,
    results_csv: str | Path = DEFAULT_RESULTS_CSV,
    tolerance: float = 0.001,
) -> CrossCheckResult:
    results = pd.read_csv(results_csv)
    row = results[
        (results["year"].astype(int).eq(int(year)))
        & (results["scoring_type"].astype(str).eq("static"))
    ].iloc[0]
    current_law_revenue = current_law_aggregate.revenue / 1e9
    current_law_oasdi = current_law_aggregate.tob_oasdi / 1e9
    live_revenue = float(row["baseline_revenue"])
    live_oasdi = float(row["baseline_tob_oasdi"])
    return CrossCheckResult(
        year=year,
        current_law_revenue_billions=current_law_revenue,
        live_baseline_revenue_billions=live_revenue,
        current_law_oasdi_billions=current_law_oasdi,
        live_baseline_oasdi_billions=live_oasdi,
        revenue_relative_error=_relative_error(current_law_revenue, live_revenue),
        oasdi_relative_error=_relative_error(current_law_oasdi, live_oasdi),
        tolerance=tolerance,
    )


def validate_current_law_cross_check(result: CrossCheckResult) -> None:
    if result.passed:
        return
    raise ValueError(
        "Balanced-fix 2035 current-law cross-check failed: "
        f"revenue error={result.revenue_relative_error:.6%}, "
        f"OASDI TOB error={result.oasdi_relative_error:.6%}, "
        f"tolerance={result.tolerance:.6%}."
    )


def validate_gap_closed(
    gap: TrustFundGap,
    *,
    tolerance_dollars: float = 1e8,
    tolerance_relative: float = 1e-4,
) -> None:
    failures: list[str] = []
    ss_scale = max(abs(gap.ss_income), abs(gap.ss_benefits), 1.0)
    hi_scale = max(abs(gap.hi_income), abs(gap.hi_expenditures), 1.0)
    if (
        abs(gap.ss_gap) > tolerance_dollars
        and abs(gap.ss_gap) / ss_scale > tolerance_relative
    ):
        failures.append(f"SS gap={gap.ss_gap:,.0f}")
    if (
        abs(gap.hi_gap) > tolerance_dollars
        and abs(gap.hi_gap) / hi_scale > tolerance_relative
    ):
        failures.append(f"HI gap={gap.hi_gap:,.0f}")
    if failures:
        raise ValueError("Balanced-fix gap did not close: " + ", ".join(failures))


def reform_for_id(reform_id: str) -> Any:
    try:
        return STATIC_REFORM_FUNCTIONS[reform_id]()
    except KeyError as error:
        raise KeyError(
            f"Balanced-fix scoring does not support {reform_id!r}"
        ) from error


def result_row_with_split(
    *,
    reform_id: str,
    year: int,
    baseline: BaselineResult,
    reform_aggregate: ScenarioAggregate,
) -> dict[str, float | int | str | bool]:
    row = build_reform_result_from_aggregates(
        reform_id=reform_id,
        year=year,
        baseline=baseline,
        reform_totals=reform_aggregate,
        employer_net_reforms=BALANCED_FIX_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="zero",
        scoring_type="static",
    )
    _, oasdi_impact, hi_impact = split_revenue_impacts(
        row,
        allocation_mode="baselineShares",
    )
    row["solvent_baseline"] = "ss_solvent"
    row["solvent_oasdi_impact"] = oasdi_impact
    row["solvent_medicare_hi_impact"] = hi_impact
    row["solvent_general_fund_impact"] = (
        float(row["revenue_impact"]) - oasdi_impact - hi_impact
    )
    total = (
        float(row["solvent_oasdi_impact"])
        + float(row["solvent_medicare_hi_impact"])
        + float(row["solvent_general_fund_impact"])
    )
    if abs(total - float(row["revenue_impact"])) > 1e-6:
        raise AssertionError(
            "Balanced-fix split does not sum to total revenue impact: "
            f"{total} != {row['revenue_impact']}"
        )
    return row


def scale_result_rows_to_billions(rows: list[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in RESULT_DOLLAR_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce") / 1e9
    return frame


def compute_balanced_fix_year(
    *,
    year: int,
    dataset_path: str | Path,
    reforms: tuple[str, ...] = BALANCED_FIX_REFORMS,
    results_csv: str | Path = DEFAULT_RESULTS_CSV,
    enforce_cross_check: bool = True,
    enforce_gap_closed: bool = True,
) -> dict[str, Any]:
    state = build_solvent_baseline_state(year=year, dataset_path=dataset_path)
    if enforce_gap_closed:
        validate_gap_closed(state.gap_after_final)

    cross_check = current_law_cross_check(
        year=year,
        current_law_aggregate=state.current_law_aggregate,
        results_csv=results_csv,
    )
    if enforce_cross_check:
        validate_current_law_cross_check(cross_check)

    solvent_baseline_sim = build_solvent_sim_from_state(state)
    solvent_baseline_aggregate = compute_scenario_aggregate_from_sim(
        solvent_baseline_sim,
        year=year,
    )
    baseline = baseline_result_from_aggregate(
        solvent_baseline_aggregate,
        tax_assumption_name=state.tax_assumption_contract.name,
        tax_assumption_active=state.tax_assumption_contract.active,
    )

    rows: list[dict[str, Any]] = []
    aggregates: dict[str, ScenarioAggregate] = {
        "solvent_baseline": solvent_baseline_aggregate
    }
    for reform_id in reforms:
        reform_sim = build_solvent_sim_from_state(
            state,
            extra_reform=reform_for_id(reform_id),
        )
        reform_aggregate = compute_scenario_aggregate_from_sim(reform_sim, year=year)
        aggregates[reform_id] = reform_aggregate
        rows.append(
            result_row_with_split(
                reform_id=reform_id,
                year=year,
                baseline=baseline,
                reform_aggregate=reform_aggregate,
            )
        )

    return {
        "year": int(year),
        "state": state,
        "metadata": {
            "balanced_fix_version": "v2-tr2026-endpoints-first",
            "heavy_sim_count": BALANCED_FIX_HEAVY_SIMS_PER_YEAR,
            "state": state.metadata_dict(),
            "cross_check": cross_check.to_dict(),
        },
        "rows": rows,
        "aggregates": aggregates,
    }
