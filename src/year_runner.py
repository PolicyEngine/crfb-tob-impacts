from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Any, Callable

from policyengine_core.reforms import Reform
from policyengine_us import Microsimulation

from reforms import (
    get_option10_dynamic_dict,
    get_option10_reform,
    get_option11_dynamic_dict,
    get_option11_reform,
    get_option12_dynamic_dict,
    get_option12_reform,
    get_option1_dynamic_dict,
    get_option1_reform,
    get_option2_dynamic_dict,
    get_option2_reform,
    get_option3_dynamic_dict,
    get_option3_reform,
    get_option4_dynamic_dict,
    get_option4_reform,
    get_option5_dynamic_dict,
    get_option5_reform,
    get_option6_dynamic_dict,
    get_option6_reform,
    get_option7_dynamic_dict,
    get_option7_reform,
    get_option8_dynamic_dict,
    get_option8_reform,
    get_option9_dynamic_dict,
    get_option9_reform,
)


STATIC_REFORM_FUNCTIONS = {
    "option1": get_option1_reform,
    "option2": get_option2_reform,
    "option3": get_option3_reform,
    "option4": get_option4_reform,
    "option5": get_option5_reform,
    "option6": get_option6_reform,
    "option7": get_option7_reform,
    "option8": get_option8_reform,
    "option9": get_option9_reform,
    "option10": get_option10_reform,
    "option11": get_option11_reform,
    "option12": get_option12_reform,
}

DYNAMIC_REFORM_DICT_FUNCTIONS = {
    "option1": get_option1_dynamic_dict,
    "option2": get_option2_dynamic_dict,
    "option3": get_option3_dynamic_dict,
    "option4": get_option4_dynamic_dict,
    "option5": get_option5_dynamic_dict,
    "option6": get_option6_dynamic_dict,
    "option7": get_option7_dynamic_dict,
    "option8": get_option8_dynamic_dict,
    "option9": get_option9_dynamic_dict,
    "option10": get_option10_dynamic_dict,
    "option11": get_option11_dynamic_dict,
    "option12": get_option12_dynamic_dict,
}

OPTION6_PHASE_IN_RATES = {
    2026: 0.1307,
    2027: 0.2614,
    2028: 0.3922,
    2029: 0.5229,
    2030: 0.6536,
    2031: 0.7843,
    2032: 0.9150,
}

BATCH_EMPLOYER_NET_REFORMS = frozenset({"option5", "option6", "option12"})
MODAL_EMPLOYER_NET_REFORMS = frozenset({"option5", "option6", "option12"})
MODAL_UNSUPPORTED_REFORMS = frozenset({"option13", "balanced_fix"})
SPECIAL_BASELINE_REFORMS = frozenset({"option13", "balanced_fix"})


@dataclass(frozen=True)
class BaselineResult:
    revenue: float
    tob_medicare_hi: float
    tob_oasdi: float
    tob_total: float


def get_reform_lookups(
    excluded_reforms: AbstractSet[str] = frozenset(),
) -> tuple[dict[str, Callable[[], Any]], dict[str, Callable[[], dict[str, Any]]]]:
    reform_functions = {
        reform_id: func
        for reform_id, func in STATIC_REFORM_FUNCTIONS.items()
        if reform_id not in excluded_reforms
    }
    dynamic_functions = {
        reform_id: func
        for reform_id, func in DYNAMIC_REFORM_DICT_FUNCTIONS.items()
        if reform_id not in excluded_reforms
    }
    return reform_functions, dynamic_functions


def load_baseline(year: int, dataset_name: str) -> BaselineResult:
    baseline_sim = Microsimulation(dataset=dataset_name)

    baseline_income_tax = baseline_sim.calculate(
        "income_tax", map_to="household", period=year
    )
    baseline_tob_medicare = baseline_sim.calculate(
        "tob_revenue_medicare_hi", map_to="household", period=year
    )
    baseline_tob_oasdi = baseline_sim.calculate(
        "tob_revenue_oasdi", map_to="household", period=year
    )
    baseline_tob_total = baseline_sim.calculate(
        "tob_revenue_total", map_to="household", period=year
    )

    result = BaselineResult(
        revenue=float(baseline_income_tax.sum()),
        tob_medicare_hi=float(baseline_tob_medicare.sum()),
        tob_oasdi=float(baseline_tob_oasdi.sum()),
        tob_total=float(baseline_tob_total.sum()),
    )

    del (
        baseline_sim,
        baseline_income_tax,
        baseline_tob_medicare,
        baseline_tob_oasdi,
        baseline_tob_total,
    )

    return result


def build_reform(
    reform_id: str,
    scoring_type: str,
    reform_functions: dict[str, Callable[[], Any]],
    dynamic_functions: dict[str, Callable[[], dict[str, Any]]],
) -> Any:
    if scoring_type == "static":
        reform_func = reform_functions.get(reform_id)
        if reform_func is None:
            raise KeyError(f"Unknown reform: {reform_id}")
        return reform_func()

    if scoring_type == "dynamic":
        dynamic_dict_func = dynamic_functions.get(reform_id)
        if dynamic_dict_func is None:
            raise KeyError(f"No dynamic dict for: {reform_id}")
        reform_params = dynamic_dict_func()
        return Reform.from_dict(reform_params, country_id="us")

    raise ValueError(f"Invalid scoring type: {scoring_type}")


def _default_net_impacts(
    tob_oasdi_impact: float,
    tob_medicare_impact: float,
    default_net_impact_mode: str,
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


def _calculate_option6_gains(
    year: int,
    employer_ss_revenue: float,
    employer_medicare_revenue: float,
) -> tuple[float, float]:
    if year >= 2033:
        return employer_ss_revenue, employer_medicare_revenue

    rate = OPTION6_PHASE_IN_RATES.get(year, 1.0)
    total_percentage_points = rate * 7.65
    total_gain = employer_ss_revenue + employer_medicare_revenue

    if total_percentage_points <= 6.2:
        return total_gain, 0.0

    oasdi_share = 6.2 / total_percentage_points
    return total_gain * oasdi_share, total_gain * (1 - oasdi_share)


def calculate_employer_net_impacts(
    reform_id: str,
    year: int,
    reform_sim: Microsimulation,
    reform_tob_oasdi_revenue: float,
    reform_tob_medicare_revenue: float,
    baseline: BaselineResult,
    employer_net_reforms: AbstractSet[str],
    default_net_impact_mode: str = "zero",
) -> dict[str, float]:
    impacts = _default_net_impacts(
        tob_oasdi_impact=reform_tob_oasdi_revenue - baseline.tob_oasdi,
        tob_medicare_impact=reform_tob_medicare_revenue - baseline.tob_medicare_hi,
        default_net_impact_mode=default_net_impact_mode,
    )

    if reform_id not in employer_net_reforms:
        return impacts

    emp_ss = reform_sim.calculate(
        "employer_ss_tax_income_tax_revenue",
        map_to="household",
        period=year,
    )
    emp_medicare = reform_sim.calculate(
        "employer_medicare_tax_income_tax_revenue",
        map_to="household",
        period=year,
    )

    employer_ss_revenue = float(emp_ss.sum())
    employer_medicare_revenue = float(emp_medicare.sum())

    if reform_id in {"option5", "option12"}:
        oasdi_gain = employer_ss_revenue
        hi_gain = employer_medicare_revenue
    else:
        oasdi_gain, hi_gain = _calculate_option6_gains(
            year,
            employer_ss_revenue,
            employer_medicare_revenue,
        )

    oasdi_loss = baseline.tob_oasdi - reform_tob_oasdi_revenue
    hi_loss = baseline.tob_medicare_hi - reform_tob_medicare_revenue

    return {
        "employer_ss_tax_revenue": employer_ss_revenue,
        "employer_medicare_tax_revenue": employer_medicare_revenue,
        "oasdi_gain": oasdi_gain,
        "hi_gain": hi_gain,
        "oasdi_loss": oasdi_loss,
        "hi_loss": hi_loss,
        "oasdi_net_impact": oasdi_gain - oasdi_loss,
        "hi_net_impact": hi_gain - hi_loss,
    }


def compute_reform_result(
    reform_id: str,
    year: int,
    scoring_type: str,
    dataset_name: str,
    baseline: BaselineResult,
    reform_functions: dict[str, Callable[[], Any]],
    dynamic_functions: dict[str, Callable[[], dict[str, Any]]],
    employer_net_reforms: AbstractSet[str],
    default_net_impact_mode: str = "zero",
) -> dict[str, float | int | str]:
    reform = build_reform(reform_id, scoring_type, reform_functions, dynamic_functions)
    reform_sim = Microsimulation(reform=reform, dataset=dataset_name)

    reform_income_tax = reform_sim.calculate("income_tax", map_to="household", period=year)
    reform_tob_medicare = reform_sim.calculate(
        "tob_revenue_medicare_hi", map_to="household", period=year
    )
    reform_tob_oasdi = reform_sim.calculate(
        "tob_revenue_oasdi", map_to="household", period=year
    )
    reform_tob_total = reform_sim.calculate(
        "tob_revenue_total", map_to="household", period=year
    )

    reform_revenue = float(reform_income_tax.sum())
    reform_tob_medicare_revenue = float(reform_tob_medicare.sum())
    reform_tob_oasdi_revenue = float(reform_tob_oasdi.sum())
    reform_tob_total_revenue = float(reform_tob_total.sum())

    revenue_impact = reform_revenue - baseline.revenue
    tob_medicare_impact = reform_tob_medicare_revenue - baseline.tob_medicare_hi
    tob_oasdi_impact = reform_tob_oasdi_revenue - baseline.tob_oasdi
    tob_total_impact = reform_tob_total_revenue - baseline.tob_total

    allocation_impacts = calculate_employer_net_impacts(
        reform_id=reform_id,
        year=year,
        reform_sim=reform_sim,
        reform_tob_oasdi_revenue=reform_tob_oasdi_revenue,
        reform_tob_medicare_revenue=reform_tob_medicare_revenue,
        baseline=baseline,
        employer_net_reforms=employer_net_reforms,
        default_net_impact_mode=default_net_impact_mode,
    )

    result = {
        "reform_name": reform_id,
        "year": year,
        "baseline_revenue": baseline.revenue,
        "reform_revenue": reform_revenue,
        "revenue_impact": revenue_impact,
        "baseline_tob_medicare_hi": baseline.tob_medicare_hi,
        "reform_tob_medicare_hi": reform_tob_medicare_revenue,
        "tob_medicare_hi_impact": tob_medicare_impact,
        "baseline_tob_oasdi": baseline.tob_oasdi,
        "reform_tob_oasdi": reform_tob_oasdi_revenue,
        "tob_oasdi_impact": tob_oasdi_impact,
        "baseline_tob_total": baseline.tob_total,
        "reform_tob_total": reform_tob_total_revenue,
        "tob_total_impact": tob_total_impact,
        "scoring_type": scoring_type,
        **allocation_impacts,
    }

    del (
        reform_sim,
        reform_income_tax,
        reform_tob_medicare,
        reform_tob_oasdi,
        reform_tob_total,
        reform,
    )

    return result
