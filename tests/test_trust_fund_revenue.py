"""
Tests for trust fund revenue calculation from SS benefit taxation.
"""
import pytest
from policyengine_us import Microsimulation
from src.trust_fund_revenue import calculate_trust_fund_revenue
from src.reforms import get_option2_reform


class TestTrustFundRevenue:
    """Test trust fund revenue calculations."""

    def test_trust_fund_revenue_is_positive_for_option2(self):
        """Trust fund revenue should be positive for Option 2."""
        revenue = calculate_trust_fund_revenue(
            reform=get_option2_reform(),
            year=2026
        )
        assert revenue > 0, "Trust fund revenue should be positive for Option 2"

    def test_trust_fund_revenue_is_substantial(self):
        """Trust fund revenue should be in reasonable range (billions)."""
        revenue = calculate_trust_fund_revenue(
            reform=get_option2_reform(),
            year=2026
        )
        # This is TOTAL trust fund revenue, should be ~$100-150B
        assert revenue > 50e9, f"Revenue should be > $50B, got ${revenue/1e9:.1f}B"
        assert revenue < 200e9, f"Revenue should be < $200B, got ${revenue/1e9:.1f}B"

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
