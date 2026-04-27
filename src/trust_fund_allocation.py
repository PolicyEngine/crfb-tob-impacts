from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping


@lru_cache(maxsize=1)
def load_allocation_rules() -> dict[str, set[str]]:
    return {
        "allocationEligibleOptions": {
            "option1",
            "option2",
            "option8",
            "option9",
            "option10",
        },
        "baselineShareOptions": {"option3", "option4", "option11"},
        "netImpactOptions": {"option5", "option6"},
        "directBranchingOptions": {"option12", "option13", "option14_stacked"},
        "generalRevenueOptions": {"option7"},
    }


def split_revenue_impacts(
    row: Mapping[str, Any],
    allocation_mode: str = "baselineShares",
) -> tuple[float, float, float]:
    rules = load_allocation_rules()
    reform_name = str(row["reform_name"])

    if reform_name in rules["generalRevenueOptions"]:
        revenue_impact = float(row["revenue_impact"])
        return revenue_impact, 0.0, 0.0

    if reform_name in rules["directBranchingOptions"]:
        oasdi_impact = float(row["oasdi_net_impact"])
        hi_impact = float(row["hi_net_impact"])
        return oasdi_impact + hi_impact, oasdi_impact, hi_impact

    uses_baseline_shares = reform_name in rules["baselineShareOptions"] or (
        allocation_mode == "baselineShares"
        and reform_name in rules["allocationEligibleOptions"]
    )
    if uses_baseline_shares:
        revenue_impact = float(row["revenue_impact"])
        baseline_oasdi = float(row["baseline_tob_oasdi"])
        baseline_hi = float(row["baseline_tob_medicare_hi"])
        baseline_total = baseline_oasdi + baseline_hi

        if baseline_total <= 0:
            return revenue_impact, 0.0, 0.0

        oasdi_share = baseline_oasdi / baseline_total
        oasdi_impact = revenue_impact * oasdi_share
        hi_impact = revenue_impact - oasdi_impact
        return revenue_impact, oasdi_impact, hi_impact

    if reform_name in rules["netImpactOptions"]:
        oasdi_impact = float(row["oasdi_net_impact"])
        hi_impact = float(row["hi_net_impact"])
        return oasdi_impact + hi_impact, oasdi_impact, hi_impact

    oasdi_impact = float(row["tob_oasdi_impact"])
    hi_impact = float(row["tob_medicare_hi_impact"])
    return oasdi_impact + hi_impact, oasdi_impact, hi_impact
