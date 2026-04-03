from src.trust_fund_allocation import split_revenue_impacts


def test_split_revenue_impacts_uses_baseline_shares_for_option3():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option3",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 1.0,
            "tob_medicare_hi_impact": 2.0,
            "oasdi_net_impact": 3.0,
            "hi_net_impact": 4.0,
        }
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 60.0
    assert hi_impact == 40.0


def test_split_revenue_impacts_respects_current_law_mode_for_option1():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option1",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 3.0,
            "hi_net_impact": 4.0,
        },
        allocation_mode="currentLaw",
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 30.0
    assert hi_impact == 70.0


def test_split_revenue_impacts_uses_direct_branching_for_option12():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option12",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 25.0,
            "hi_net_impact": 75.0,
        }
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 25.0
    assert hi_impact == 75.0


def test_split_revenue_impacts_uses_net_impacts_for_option5():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option5",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 15.0,
            "hi_net_impact": 25.0,
        }
    )

    assert revenue_impact == 40.0
    assert oasdi_impact == 15.0
    assert hi_impact == 25.0


def test_split_revenue_impacts_zeroes_trust_fund_impacts_for_option7():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option7",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 15.0,
            "hi_net_impact": 25.0,
        }
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 0.0
    assert hi_impact == 0.0


def test_split_revenue_impacts_falls_back_to_raw_tob_impacts_for_balanced_fix():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "balanced_fix",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 60.0,
            "baseline_tob_medicare_hi": 40.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 15.0,
            "hi_net_impact": 25.0,
        }
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 30.0
    assert hi_impact == 70.0


def test_split_revenue_impacts_handles_non_positive_baseline_total():
    revenue_impact, oasdi_impact, hi_impact = split_revenue_impacts(
        {
            "reform_name": "option3",
            "revenue_impact": 100.0,
            "baseline_tob_oasdi": 0.0,
            "baseline_tob_medicare_hi": 0.0,
            "tob_oasdi_impact": 30.0,
            "tob_medicare_hi_impact": 70.0,
            "oasdi_net_impact": 15.0,
            "hi_net_impact": 25.0,
        }
    )

    assert revenue_impact == 100.0
    assert oasdi_impact == 0.0
    assert hi_impact == 0.0
