"""
Tests for trust fund revenue calculation from SS benefit taxation.
"""
import pytest
from policyengine_us import Microsimulation
from src.trust_fund_revenue import calculate_trust_fund_revenue
from src.reforms import get_option2_reform


class TestTrustFundRevenue:
    """Test trust fund revenue calculations."""

    def test_trust_fund_revenue_change_is_positive_for_option2(self):
        """Trust fund revenue change should be positive for Option 2 vs baseline."""
        revenue_change = calculate_trust_fund_revenue(
            reform=get_option2_reform(),
            year=2026
        )
        assert revenue_change > 0, "Trust fund revenue change should be positive for Option 2"

    def test_trust_fund_revenue_change_is_substantial(self):
        """Trust fund revenue change should be in reasonable range (billions)."""
        revenue_change = calculate_trust_fund_revenue(
            reform=get_option2_reform(),
            year=2026
        )
        # Based on revenue impacts data, Option 2 generates ~$24B additional revenue
        assert revenue_change > 10e9, f"Revenue change should be > $10B, got ${revenue_change/1e9:.1f}B"
        assert revenue_change < 100e9, f"Revenue change should be < $100B, got ${revenue_change/1e9:.1f}B"

    def test_option2_vs_baseline_differ(self):
        """Income tax should differ between Option 2 and baseline."""
        year = 2026

        # Option 2 simulation
        option2_sim = Microsimulation(reform=get_option2_reform())
        income_tax_option2 = option2_sim.calculate("income_tax", map_to="household", period=year)

        # Baseline simulation
        baseline_sim = Microsimulation()
        income_tax_baseline = baseline_sim.calculate("income_tax", map_to="household", period=year)

        # Verify Option 2 has higher taxable SS than baseline
        taxable_ss_option2 = option2_sim.calculate("taxable_social_security", period=year)
        taxable_ss_baseline = baseline_sim.calculate("taxable_social_security", period=year)

        assert taxable_ss_option2.sum() > taxable_ss_baseline.sum(), \
            "Option 2 should have more taxable SS than baseline"

        assert income_tax_option2.sum() != income_tax_baseline.sum(), \
            "Income tax should differ between Option 2 and baseline"
        assert income_tax_option2.sum() > income_tax_baseline.sum(), \
            "Option 2 should have higher income tax than baseline"
