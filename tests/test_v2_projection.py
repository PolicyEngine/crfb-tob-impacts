"""Tests for the v2 baseline projection pipeline (demographic reweight +
value scaling + light final calibration)."""

import numpy as np
import pandas as pd
import pytest

from src.v2_projection import (
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
    assert 390e6 < total < 415e6
    share_65_plus = totals[ages >= 65].sum() / total
    assert 0.20 < share_65_plus < 0.26


def test_economic_targets_2026():
    targets = load_economic_targets(2026)
    assert targets["ss_total"] == pytest.approx(1_701.334e9)
    assert targets["payroll_total"] == pytest.approx(11_129e9)


def test_tob_targets_post_obbba_2026():
    targets = load_tob_targets(2026)
    assert targets["oasdi_tob"] == pytest.approx(60.5901e9)
    assert targets["hi_tob"] == pytest.approx(41.1868539030e9)


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
        "trustees_2025_economic",
        "post_obbba_tob_baseline",
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


# ---------------------------------------------------------------------------
# Donor-clone support
# ---------------------------------------------------------------------------


def _toy_frame(year=2100):
    import pandas as pd

    rows = []
    for hh in range(6):
        for member in range(2):
            person_id = hh * 10 + member
            rows.append(
                {
                    f"person_id__{year}": person_id,
                    f"household_id__{year}": hh,
                    f"person_household_id__{year}": hh,
                    f"tax_unit_id__{year}": hh,
                    f"person_tax_unit_id__{year}": hh,
                    f"family_id__{year}": hh,
                    f"person_family_id__{year}": hh,
                    f"spm_unit_id__{year}": hh,
                    f"person_spm_unit_id__{year}": hh,
                    f"marital_unit_id__{year}": hh,
                    f"person_marital_unit_id__{year}": hh,
                    f"age__{year}": 70,
                    f"household_weight__{year}": 100.0,
                    f"qualified_dividend_income__{year}": 1_000.0 * hh,
                    f"social_security_retirement__{year}": 20_000.0,
                }
            )
    return pd.DataFrame(rows)


def test_donor_clones_rekey_ids_and_scale_priors():
    import numpy as np

    from src.v2_pipeline import (
        DONOR_CLONE_PRIOR_SCALE,
        DONOR_CLONES_PER_HOUSEHOLD,
        _append_donor_clones,
    )

    year = 2100
    df = _toy_frame(year)
    household_ids = np.arange(6)
    person_household_index = df[f"person_household_id__{year}"].to_numpy()
    weights = np.full(6, 100.0)
    tob = np.array([0.0, 0.0, 5.0, 10.0, 50.0, 100.0])

    augmented, info = _append_donor_clones(
        df,
        year,
        tob_by_household=tob,
        household_ids=household_ids,
        person_household_index=person_household_index,
        weights=weights,
        other_income_columns=[f"qualified_dividend_income__{year}"],
        ss_columns=[f"social_security_retirement__{year}"],
    )
    clone_households = info["clone_household_count"]
    assert clone_households == info["donor_household_count"] * (
        DONOR_CLONES_PER_HOUSEHOLD
    )
    # All ids remain unique after re-keying.
    for column in augmented.columns:
        if column.startswith("person_id__"):
            assert augmented[column].is_unique
    hh_col = augmented[f"household_id__{year}"]
    assert hh_col.nunique() == 6 + clone_households
    # Clone priors are scaled down.
    clone_rows = augmented.iloc[len(df):]
    assert (
        clone_rows[f"household_weight__{year}"]
        == 100.0 * DONOR_CLONE_PRIOR_SCALE
    ).all()
    # Jitter changed other income but kept it positive.
    base_dividends = df[f"qualified_dividend_income__{year}"].iloc[-1]
    clone_dividends = clone_rows[f"qualified_dividend_income__{year}"]
    assert (clone_dividends >= 0).all()
    assert clone_dividends.nunique() > 1


def test_donor_clones_are_deterministic():
    import numpy as np

    from src.v2_pipeline import _append_donor_clones

    year = 2100
    kwargs = dict(
        tob_by_household=np.array([0.0, 0.0, 5.0, 10.0, 50.0, 100.0]),
        household_ids=np.arange(6),
        weights=np.full(6, 100.0),
        other_income_columns=[f"qualified_dividend_income__{year}"],
        ss_columns=[f"social_security_retirement__{year}"],
    )
    df = _toy_frame(year)
    person_household_index = df[f"person_household_id__{year}"].to_numpy()
    first, _ = _append_donor_clones(
        df, year, person_household_index=person_household_index, **kwargs
    )
    second, _ = _append_donor_clones(
        df, year, person_household_index=person_household_index, **kwargs
    )
    import pandas as pd

    pd.testing.assert_frame_equal(first, second)
