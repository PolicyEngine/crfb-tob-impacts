"""Tests for impact calculator functions."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch
from src.impact_calculator import (
    calculate_fiscal_impact,
    compute_baselines,
    calculate_household_impact
)
from src.reforms import get_option1_reform


class TestFiscalImpact:
    """Test fiscal impact calculations."""

    def test_calculate_fiscal_impact_with_reform(self):
        """Test fiscal impact calculation with a reform."""
        # Create mock baseline
        baseline_income_tax = np.array([1000, 2000, 3000])

        # Mock the Microsimulation
        with patch('src.impact_calculator.Microsimulation') as MockMicrosim:
            # Setup mock reformed simulation
            mock_reformed = Mock()
            mock_reformed.calculate.return_value = np.array([900, 1900, 2900])
            MockMicrosim.return_value = mock_reformed

            # Calculate impact
            reform = Mock()
            impact = calculate_fiscal_impact(reform, 2026, baseline_income_tax)

            # Should be (baseline - reformed).sum() / 1e9
            # (1000+2000+3000) - (900+1900+2900) = 300
            # 300 / 1e9 = 0.0000003, rounded to 0.0
            assert impact == 0.0

    def test_calculate_fiscal_impact_no_reform(self):
        """Test fiscal impact calculation with no reform."""
        baseline_income_tax = np.array([1000, 2000, 3000])
        impact = calculate_fiscal_impact(None, 2026, baseline_income_tax)
        assert impact == 0.0

    def test_calculate_fiscal_impact_error_handling(self):
        """Test error handling in fiscal impact calculation."""
        baseline_income_tax = np.array([1000, 2000, 3000])

        with patch('src.impact_calculator.Microsimulation') as MockMicrosim:
            # Setup mock to raise an error
            MockMicrosim.side_effect = Exception("Test error")

            reform = Mock()
            impact = calculate_fiscal_impact(reform, 2026, baseline_income_tax)

            # Should return 0.0 on error
            assert impact == 0.0


class TestComputeBaselines:
    """Test baseline computation."""

    def test_compute_baselines(self):
        """Test computing baselines for multiple years."""
        years = [2026, 2027]

        with patch('src.impact_calculator.Microsimulation') as MockMicrosim:
            # Setup mock baseline simulation
            mock_baseline = Mock()
            mock_baseline.calculate.return_value = np.array([1000, 2000, 3000])
            MockMicrosim.return_value = mock_baseline

            baselines = compute_baselines(years)

            assert len(baselines) == 2
            assert 2026 in baselines
            assert 2027 in baselines
            assert isinstance(baselines[2026], np.ndarray)
            assert len(baselines[2026]) == 3


class TestHouseholdImpact:
    """Test household impact calculations."""

    def test_calculate_household_impact(self):
        """Test household impact calculation."""
        with patch('src.impact_calculator.Simulation') as MockSim:
            # Setup mock simulations
            mock_reform_sim = Mock()
            mock_reform_sim.calculate.return_value = np.array([50000, 60000, 70000])

            mock_baseline_sim = Mock()
            mock_baseline_sim.calculate.return_value = np.array([49000, 59000, 69000])

            # Make Simulation return different mocks based on reform parameter
            def simulation_side_effect(reform=None, situation=None):
                if reform is not None:
                    return mock_reform_sim
                else:
                    return mock_baseline_sim

            MockSim.side_effect = simulation_side_effect

            # Calculate impact
            reform = Mock()
            df = calculate_household_impact(
                reform,
                2026,
                employment_income_range=(0, 1000, 500)
            )

            # Check DataFrame structure
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 3  # 0, 500, 1000
            assert 'employment_income' in df.columns
            assert 'baseline_net_income' in df.columns
            assert 'reform_net_income' in df.columns
            assert 'change_in_net_income' in df.columns

            # Check that change is calculated correctly
            assert all(df['change_in_net_income'] == 1000)

    def test_calculate_household_impact_custom_params(self):
        """Test household impact with custom parameters."""
        with patch('src.impact_calculator.Simulation') as MockSim:
            mock_sim = Mock()
            mock_sim.calculate.return_value = np.array([50000])
            MockSim.return_value = mock_sim

            reform = Mock()
            df = calculate_household_impact(
                reform,
                2027,
                employment_income_range=(10000, 10000, 1000),
                social_security_benefits=25000,
                age=65,
                state="CA"
            )

            # Should have only one row (10000)
            assert len(df) == 1
            assert df.iloc[0]['employment_income'] == 10000