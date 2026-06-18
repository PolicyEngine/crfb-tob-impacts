"""Tests for the baseline projection pipeline (demographic reweight +
value scaling + light final calibration)."""

import numpy as np
import pandas as pd
import pytest

import src.projection as projection
from src.projection import (
    CONTRIBUTOR_GATES,
    build_household_age_bin_matrix,
    calibrate_entropy_constraints,
    entropy_weight_audit,
    evaluate_publication_gates,
    load_economic_targets,
    load_population_age_targets,
    load_tob_targets,
    solve_earnings_scale,
    target_source_provenance,
)


# ---------------------------------------------------------------------------
# Target loaders
# ---------------------------------------------------------------------------


def test_population_age_targets_2060():
    ages, totals = load_population_age_targets(2060)
    assert len(ages) == 86
    assert ages[0] == 0 and ages[-1] == 85
    total = totals.sum()
    # TR2026 intermediate population (lower fertility and immigration
    # than TR2024): 376.7M in 2060.
    assert 370e6 < total < 385e6
    share_65_plus = totals[ages >= 65].sum() / total
    assert 0.21 < share_65_plus < 0.26


def test_economic_targets_2026():
    targets = load_economic_targets(2026)
    # TR2026 intermediate: 15.37% cost rate on $11,043B taxable payroll.
    assert targets["ss_total"] == pytest.approx(1_697.3091e9, rel=1e-6)
    assert targets["payroll_total"] == pytest.approx(11_043e9)


def test_tob_targets_tr2026_2026():
    targets = load_tob_targets(2026)
    # TR2026 current law includes OBBBA: IV.B2 puts OASDI TOB at 0.56% of
    # payroll; the CMS 2026 Medicare tables put HI TOB at $46.97B.
    assert targets["oasdi_tob"] == pytest.approx(61.8408e9, rel=1e-6)
    assert targets["hi_tob"] == pytest.approx(46.966e9, rel=1e-3)


def test_tob_targets_cover_every_fifth_year():
    for year in [2026, 2030] + list(range(2035, 2101, 5)):
        targets = load_tob_targets(year)
        assert targets["oasdi_tob"] > 0
        assert targets["hi_tob"] > 0


def test_target_source_provenance_records_hashes():
    provenance = target_source_provenance()
    names = {entry["role"] for entry in provenance}
    assert {
        "population_by_single_year_age",
        "trustees_2026_economic",
        "tr2026_current_law_tob",
    } <= names
    for entry in provenance:
        assert len(entry["sha256"]) == 64


# ---------------------------------------------------------------------------
# Age matrix
# ---------------------------------------------------------------------------


def test_age_bin_matrix_counts_household_members():
    ages = np.array([34, 36, 2, 71, 68])
    household_index = np.array([0, 0, 0, 1, 1])
    matrix, bins = build_household_age_bin_matrix(
        ages, household_index, n_households=2, bucket_size=5
    )
    assert matrix.shape == (2, len(bins))
    assert matrix.sum() == 5
    assert matrix[0].sum() == 3
    assert matrix[1].sum() == 2
    # 65-69 bucket holds the 68-year-old; 70-74 holds the 71-year-old.
    labels = {f"{lo}-{hi - 1}": idx for idx, (lo, hi) in enumerate(bins)}
    assert matrix[1, labels["65-69"]] == 1
    assert matrix[1, labels["70-74"]] == 1


# ---------------------------------------------------------------------------
# Entropy calibration
# ---------------------------------------------------------------------------


def _toy_problem():
    rng = np.random.default_rng(7)
    n = 4_000
    base = rng.uniform(50, 150, n)
    age_groups = rng.integers(0, 4, n)
    A_age = np.zeros((n, 4))
    A_age[np.arange(n), age_groups] = 1.0
    income = rng.lognormal(10, 1.2, n)
    A = np.column_stack([A_age, income])
    achieved = A.T @ base
    targets = achieved * np.array([1.04, 0.97, 1.08, 1.01, 1.06])
    return A, targets, base


def test_entropy_hits_targets_and_stays_positive():
    A, targets, base = _toy_problem()
    weights, info = calibrate_entropy_constraints(A, targets, base)
    achieved = A.T @ weights
    np.testing.assert_allclose(achieved, targets, rtol=1e-6)
    assert (weights > 0).all()
    assert info["max_constraint_pct_error"] < 1e-4


def test_entropy_light_adjustment_keeps_high_ess():
    A, targets, base = _toy_problem()
    weights, _ = calibrate_entropy_constraints(A, targets, base)
    ess_base = base.sum() ** 2 / (base**2).sum()
    ess_new = weights.sum() ** 2 / (weights**2).sum()
    # Small target perturbations should not collapse the effective sample.
    assert ess_new > 0.7 * ess_base


def test_entropy_audit_reports_concentration():
    A, targets, base = _toy_problem()
    weights, _ = calibrate_entropy_constraints(A, targets, base)
    audit = entropy_weight_audit(weights, base)
    assert audit["positive_weight_count"] == len(weights)
    assert 0 < audit["effective_sample_size"] <= len(weights)
    assert 0 < audit["top_10_weight_share_pct"] < 100
    assert audit["max_weight_ratio"] >= 1.0


def test_entropy_raises_on_infeasible_targets():
    A, targets, base = _toy_problem()
    bad = targets.copy()
    bad[-1] = -5.0  # negative total income is unreachable with w > 0
    with pytest.raises(RuntimeError):
        calibrate_entropy_constraints(A, bad, base)


# ---------------------------------------------------------------------------
# Earnings scale solve
# ---------------------------------------------------------------------------


def test_earnings_scale_recovers_known_factor_below_cap():
    rng = np.random.default_rng(3)
    n = 2_000
    wages = rng.uniform(10_000, 80_000, n)
    se = np.zeros(n)
    weights = np.full(n, 100.0)
    cap = 1e9  # never binds
    base_total = float((wages * weights).sum())
    alpha = solve_earnings_scale(
        gross_wages=wages,
        taxable_self_employment=se,
        weights=weights,
        cap=cap,
        payroll_target=1.23 * base_total,
    )
    assert alpha == pytest.approx(1.23, rel=1e-6)


def test_earnings_scale_accounts_for_cap():
    wages = np.array([100_000.0, 400_000.0])
    se = np.array([0.0, 0.0])
    weights = np.array([1.0, 1.0])
    cap = 200_000.0
    # base taxable payroll = 100k + 200k = 300k.
    # With alpha=2: min(200k,200k) + min(800k->cap) = 400k.
    alpha = solve_earnings_scale(
        gross_wages=wages,
        taxable_self_employment=se,
        weights=weights,
        cap=cap,
        payroll_target=400_000.0,
    )
    taxable = np.minimum(alpha * wages, cap)
    assert taxable.sum() == pytest.approx(400_000.0, rel=1e-9)


def test_earnings_scale_se_income_uses_remaining_cap_room():
    wages = np.array([150_000.0])
    se = np.array([100_000.0])
    weights = np.array([1.0])
    cap = 200_000.0
    # alpha=1: 150k wages + min(100k, 50k room) = 200k.
    # Target 210k requires alpha just above 1; with alpha=1.4:
    # wages min(210k,200k)=200k, room 0 -> 200k. Infeasible above 200k+...
    # so cap-aware solver must find target inside reachable range.
    alpha = solve_earnings_scale(
        gross_wages=wages,
        taxable_self_employment=se,
        weights=weights,
        cap=cap,
        payroll_target=180_000.0,
    )
    taxable = min(alpha * 150_000.0, cap) + min(
        alpha * 100_000.0, max(0.0, cap - min(alpha * 150_000.0, cap))
    )
    assert taxable == pytest.approx(180_000.0, rel=1e-6)


def test_earnings_scale_raises_when_target_unreachable():
    wages = np.array([150_000.0])
    se = np.array([0.0])
    weights = np.array([1.0])
    with pytest.raises(RuntimeError):
        solve_earnings_scale(
            gross_wages=wages,
            taxable_self_employment=se,
            weights=weights,
            cap=200_000.0,
            payroll_target=300_000.0,  # above the 200k cap ceiling
        )


# ---------------------------------------------------------------------------
# Publication gates
# ---------------------------------------------------------------------------


def test_publication_gates_pass_for_healthy_audit():
    audit = {
        "positive_weight_count": 30_000,
        "effective_sample_size": 5_000.0,
        "top_10_weight_share_pct": 2.0,
        "top_100_weight_share_pct": 10.0,
    }
    contributor_audits = {
        "ss_total": {
            "positive_contributor_count": 8_000,
            "contributor_effective_sample_size": 900.0,
            "top_10_contribution_share_pct": 10.0,
            "top_100_contribution_share_pct": 40.0,
            "max_contribution_share_pct": 2.0,
        }
    }
    result = evaluate_publication_gates(audit, contributor_audits)
    assert result["passed"] is True
    assert result["failures"] == []


def test_publication_gates_fail_on_concentration():
    audit = {
        "positive_weight_count": 900,
        "effective_sample_size": 100.0,
        "top_10_weight_share_pct": 40.0,
        "top_100_weight_share_pct": 80.0,
    }
    result = evaluate_publication_gates(audit, {})
    assert result["passed"] is False
    assert len(result["failures"]) >= 3


def _healthy_aggregate_audit() -> dict:
    return {
        "positive_weight_count": 30_000,
        "effective_sample_size": 5_000.0,
        "top_10_weight_share_pct": 2.0,
        "top_100_weight_share_pct": 10.0,
    }


def _hi_tob_contributor_audit(cess: float) -> dict:
    # Healthy on every hi_tob contributor sub-gate except the effective sample
    # size, the dimension under test.
    return {
        "hi_tob": {
            "positive_contributor_count": 16_000,
            "contributor_effective_sample_size": cess,
            "top_10_contribution_share_pct": 25.0,
            "top_100_contribution_share_pct": 60.0,
            "max_contribution_share_pct": 5.0,
        }
    }


def test_contributor_gates_apply_by_default():
    # No late-year carve-out: contributor gates are enforced by default for
    # every year, so a sub-threshold contributor audit is caught without any
    # year-based opt-in (the inconsistency that let 2045 escape is gone).
    result = evaluate_publication_gates(
        _healthy_aggregate_audit(),
        _hi_tob_contributor_audit(30.0),
    )
    assert result["passed"] is False
    assert any(
        "hi_tob" in failure and "contributor_effective_sample_size" in failure
        for failure in result["failures"]
    )


def test_tob_contributor_floor_is_35():
    # Both benefit-taxation contributor metrics share the lowered floor.
    assert not hasattr(projection, "CONTRIBUTOR_GATE_START_YEAR")
    assert CONTRIBUTOR_GATES["hi_tob"]["contributor_effective_sample_size"] == (
        "min",
        35.0,
    )
    assert CONTRIBUTOR_GATES["oasdi_tob"]["contributor_effective_sample_size"] == (
        "min",
        35.0,
    )


def test_hi_tob_contributor_passes_in_35_to_50_band():
    # The far-horizon hi_tob effective sample size of 46.7 (the 2090 case) sits
    # in the noisy 35-50 band and must pass the lowered floor.
    result = evaluate_publication_gates(
        _healthy_aggregate_audit(),
        _hi_tob_contributor_audit(46.7),
        apply_contributor_gates=True,
    )
    assert result["passed"] is True, result["failures"]


def test_hi_tob_contributor_still_fails_below_35():
    # Genuine concentration below the floor still fails.
    result = evaluate_publication_gates(
        _healthy_aggregate_audit(),
        _hi_tob_contributor_audit(30.0),
        apply_contributor_gates=True,
    )
    assert result["passed"] is False
    assert any(
        "hi_tob" in failure and "contributor_effective_sample_size" in failure
        for failure in result["failures"]
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------


def test_repair_zeroes_corrupt_miscellaneous_income():

    from src.pipeline import repair_corrupt_inputs

    year = 2026
    df = pd.DataFrame(
        {
            f"miscellaneous_income__{year}": [500.0, 795_294_848.0, 0.0],
            f"employment_income_before_lsr__{year}": [50_000.0, 60_000.0, 0.0],
        }
    )
    log = repair_corrupt_inputs(df, year)
    assert log["miscellaneous_income"]["records_zeroed"] == 1
    assert log["miscellaneous_income"]["amount_zeroed"] == 795_294_848.0
    assert df[f"miscellaneous_income__{year}"].tolist() == [500.0, 0.0, 0.0]
    # Plausible values and other variables are untouched.
    assert df[f"employment_income_before_lsr__{year}"].sum() == 110_000.0


def test_growth_cap_call_site_present():
    # Regression: a formatting-mismatched patch once dropped the call site
    # while the function and its metadata reference both existed, crashing
    # every build at metadata assembly.
    import inspect

    from src import pipeline

    source = inspect.getsource(pipeline.build_year)
    assert "cap_longrun_income_growth(df, sim, year)" in source
    assert '"longrun_growth_caps": growth_caps' in inspect.getsource(pipeline)
