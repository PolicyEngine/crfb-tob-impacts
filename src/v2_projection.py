"""V2 long-horizon baseline construction.

Builds year-specific calibrated datasets with a different division of labor
than the v1 (``ss-payroll-tob``) stack:

- **Values carry economic growth.** Earnings are rescaled so SSA taxable
  payroll matches the Trustees target; Social Security benefits are rescaled
  so total OASDI benefits match Trustees cost. This removes the
  population-growth double count that occurs when aggregate-growth uprating
  series are combined with population-growing weights.
- **Weights carry demographics, lightly.** An entropy reweight matches the
  SSA Trustees age distribution, and a final light entropy pass matches the
  full target family (age, Social Security, taxable payroll, OASDI TOB,
  HI TOB) exactly. Because values are pre-scaled, the final pass needs only
  a small tilt, keeping the effective sample size high.
- **TOB targets are post-OBBBA.** The model law (policyengine-us) includes
  OBBBA, so datasets calibrate to the post-OBBBA taxation-of-benefits
  baseline (``data/ssa_tob_baseline_75year.csv``) rather than the pre-OBBBA
  current-law series used by the v1 datasets.

The entropy solver follows the positive entropy-balancing approach in
``policyengine-us-data`` ``datasets/cps/long_term/calibration.py`` at commit
5a357137 (the v1 production stack), restated here so the CRFB code bundle is
self-contained for launch-approval hashing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# 2026 Trustees Report targets (see data/tr2026_sources.manifest.json).
# TR2026 incorporates OBBBA in current law, so its taxation-of-benefits
# series replaces the TR2025 post-OBBBA bridge.
POPULATION_FILE = DATA_DIR / "SSPopJul_TR2026_interim.csv"
ECONOMIC_FILE = DATA_DIR / "social_security_aux_tr2026.csv"
TOB_FILE = DATA_DIR / "social_security_aux_tr2026.csv"

# Publication gates mirror docs/current/late-year-support-gates.md.
AGGREGATE_GATES = {
    "positive_weight_count": ("min", 1_000),
    "effective_sample_size": ("min", 300.0),
    "top_10_weight_share_pct": ("max", 15.0),
    "top_100_weight_share_pct": ("max", 45.0),
}
# Contributor gates run from 2075 (CRFB_SUPPORT_GATE_START_YEAR default).
CONTRIBUTOR_GATE_START_YEAR = 2075
CONTRIBUTOR_GATES = {
    "ss_total": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 25.0),
        "top_10_contribution_share_pct": ("max", 60.0),
        "top_100_contribution_share_pct": ("max", 95.0),
        "max_contribution_share_pct": ("max", 15.0),
    },
    "payroll_total": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 200.0),
        "top_10_contribution_share_pct": ("max", 20.0),
        "top_100_contribution_share_pct": ("max", 50.0),
        "max_contribution_share_pct": ("max", 5.0),
    },
    "oasdi_tob": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 50.0),
        "top_10_contribution_share_pct": ("max", 50.0),
        "top_100_contribution_share_pct": ("max", 95.0),
        "max_contribution_share_pct": ("max", 15.0),
    },
    "hi_tob": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 50.0),
        "top_10_contribution_share_pct": ("max", 50.0),
        "top_100_contribution_share_pct": ("max", 95.0),
        "max_contribution_share_pct": ("max", 15.0),
    },
}


# ---------------------------------------------------------------------------
# Target loaders
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_population_age_targets(year: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (ages 0..85, population totals) for ``year``.

    Source: SSA Trustees Social Security area population by single year of
    age (``SSPopJul_TR2024.csv``). Ages above 85 collapse into the 85+ slot.
    """
    table = pd.read_csv(POPULATION_FILE)
    rows = table[table.Year == year]
    if rows.empty:
        raise ValueError(f"No population projection for {year}.")
    capped_age = rows.Age.clip(upper=85)
    totals = rows.groupby(capped_age).Total.sum()
    ages = np.arange(86)
    return ages, totals.reindex(ages, fill_value=0).to_numpy(dtype=float)


def load_economic_targets(year: int) -> dict[str, float]:
    """Trustees 2025 OASDI cost and taxable payroll targets in dollars."""
    table = pd.read_csv(ECONOMIC_FILE).set_index("year")
    if year not in table.index:
        raise ValueError(f"No Trustees economic projection for {year}.")
    row = table.loc[year]
    return {
        "ss_total": float(row.oasdi_cost_in_billion_nominal_usd) * 1e9,
        "payroll_total": float(row.taxable_payroll_in_billion_nominal_usd)
        * 1e9,
    }


def load_tob_targets(year: int) -> dict[str, float]:
    """TR2026 current-law taxation-of-benefits targets in dollars."""
    table = pd.read_csv(TOB_FILE).set_index("year")
    if year not in table.index:
        raise ValueError(f"No TR2026 TOB target for {year}.")
    row = table.loc[year]
    return {
        "oasdi_tob": float(row.oasdi_tob_billions_nominal_usd) * 1e9,
        "hi_tob": float(row.hi_tob_billions_nominal_usd) * 1e9,
    }


def target_source_provenance() -> list[dict[str, str]]:
    return [
        {
            "role": "population_by_single_year_age",
            "file": str(POPULATION_FILE.relative_to(REPO_ROOT)),
            "sha256": _sha256(POPULATION_FILE),
            "source": "TR2026 V.A3 age-group totals applied to the TR2024 "
            "single-year-age shape (interim until SSA posts the TR2026 "
            "single-year file)",
        },
        {
            "role": "trustees_2026_economic",
            "file": str(ECONOMIC_FILE.relative_to(REPO_ROOT)),
            "sha256": _sha256(ECONOMIC_FILE),
            "source": "SSA 2026 Trustees Report: OASDI cost rate (IV.B1) "
            "times taxable payroll (VI.G1), intermediate assumptions",
        },
        {
            "role": "tr2026_current_law_tob",
            "file": str(TOB_FILE.relative_to(REPO_ROOT)),
            "sha256": _sha256(TOB_FILE),
            "source": "OASDI TOB: TR2026 IV.B2 percent of taxable payroll "
            "times VI.G1 payroll; HI TOB: CMS 2026 Medicare Trustees "
            "expanded tables. TR2026 current law includes OBBBA.",
        },
    ]


# ---------------------------------------------------------------------------
# Age matrix
# ---------------------------------------------------------------------------


def build_age_bins(bucket_size: int = 5, n_ages: int = 86) -> list[tuple[int, int]]:
    """Half-open [lo, hi) single-year-age bins; the last bin is 85+."""
    if bucket_size <= 1:
        return [(a, a + 1) for a in range(n_ages)]
    bins = [
        (start, min(start + bucket_size, n_ages - 1))
        for start in range(0, n_ages - 1, bucket_size)
    ]
    bins.append((n_ages - 1, n_ages))
    return bins


def build_household_age_bin_matrix(
    ages: np.ndarray,
    household_index: np.ndarray,
    n_households: int,
    bucket_size: int = 5,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Count household members per age bucket.

    ``household_index`` maps each person row to a household row index.
    """
    bins = build_age_bins(bucket_size)
    capped = np.minimum(np.asarray(ages, dtype=int), 85)
    bin_of_age = np.zeros(86, dtype=int)
    for bin_idx, (lo, hi) in enumerate(bins):
        bin_of_age[lo:hi] = bin_idx
    matrix = np.zeros((n_households, len(bins)))
    np.add.at(matrix, (household_index, bin_of_age[capped]), 1.0)
    return matrix, bins


def aggregate_age_targets(
    totals: np.ndarray, bins: list[tuple[int, int]]
) -> np.ndarray:
    return np.array([totals[lo:hi].sum() for lo, hi in bins], dtype=float)


# ---------------------------------------------------------------------------
# Entropy calibration
# ---------------------------------------------------------------------------


def calibrate_entropy_constraints(
    A: np.ndarray,
    targets: np.ndarray,
    baseline_weights: np.ndarray,
    max_iters: int = 200,
    tol: float = 1e-10,
) -> tuple[np.ndarray, dict]:
    """Strictly positive weights minimizing KL divergence from baseline
    subject to ``A.T @ w == targets``.

    Solves the dual with damped Newton iterations; weights are
    ``baseline * exp(A_scaled @ beta)`` and therefore positive.
    """
    A = np.asarray(A, dtype=float)
    targets = np.asarray(targets, dtype=float)
    baseline_weights = np.asarray(baseline_weights, dtype=float)
    if (targets <= 0).any():
        # All constraint columns in this pipeline are nonnegative
        # (member counts, benefits, payroll, TOB revenue), so a
        # nonpositive target can never be met with positive weights.
        raise RuntimeError(
            "Entropy calibration requires strictly positive targets; got "
            f"{targets[targets <= 0]}."
        )

    scales = np.maximum(
        np.maximum(np.abs(targets), np.abs(A.T @ baseline_weights)), 1.0
    )
    A_scaled = A / scales
    targets_scaled = targets / scales

    ridge = 1e-12

    def weights_for(beta_vec: np.ndarray) -> np.ndarray:
        eta = np.clip(A_scaled @ beta_vec, -700, 700)
        return baseline_weights * np.exp(eta)

    # Least-squares warm start (as in the v1 production solver).
    gram = A_scaled.T @ (baseline_weights[:, None] * A_scaled)
    gram += np.eye(gram.shape[0]) * ridge
    try:
        beta = np.linalg.solve(
            gram, targets_scaled - A_scaled.T @ baseline_weights
        )
    except np.linalg.LinAlgError:
        beta = np.zeros(A.shape[1])

    gradient_norm = np.inf
    for _ in range(max_iters):
        w = weights_for(beta)
        gradient = A_scaled.T @ w - targets_scaled
        gradient_norm = float(np.max(np.abs(gradient)))
        if gradient_norm < tol:
            break
        hessian = A_scaled.T @ (w[:, None] * A_scaled)
        hessian += np.eye(hessian.shape[0]) * ridge
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        # Backtracking line search on the dual objective.
        objective = float(w.sum() - targets_scaled @ beta)
        step_size = 1.0
        improved = False
        for _ in range(80):
            candidate = beta - step_size * step
            w_candidate = weights_for(candidate)
            candidate_objective = float(
                w_candidate.sum() - targets_scaled @ candidate
            )
            if candidate_objective < objective:
                beta = candidate
                improved = True
                break
            step_size *= 0.5
        if not improved:
            # No further numerical progress on the dual. Accept if the
            # constraints are already met to acceptance precision;
            # otherwise the problem is infeasible for positive weights.
            break

    w = weights_for(beta)
    achieved = A.T @ w
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_errors = np.abs(achieved - targets) / np.maximum(
            np.abs(targets), 1e-9
        )
    max_pct = float(np.max(pct_errors))
    if gradient_norm > 1e-6 or max_pct > 1e-4:
        raise RuntimeError(
            "Entropy calibration did not converge: max constraint error "
            f"{max_pct:.3%}, dual gradient norm {gradient_norm:.2e}."
        )
    info = {
        "max_constraint_pct_error": max_pct,
        "dual_gradient_norm": gradient_norm,
        "achieved": achieved,
    }
    return w, info


def entropy_weight_audit(
    weights: np.ndarray, baseline_weights: np.ndarray
) -> dict:
    weights = np.asarray(weights, dtype=float)
    baseline_weights = np.asarray(baseline_weights, dtype=float)
    positive = weights > 0
    sorted_weights = np.sort(weights)[::-1]
    total = float(weights.sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = np.where(
            baseline_weights > 0, weights / baseline_weights, np.nan
        )
    return {
        "weight_sum": total,
        "baseline_weight_sum": float(baseline_weights.sum()),
        "positive_weight_count": int(positive.sum()),
        "positive_weight_pct": float(100 * positive.mean()),
        "effective_sample_size": float(
            total**2 / float((weights**2).sum())
        ),
        "top_10_weight_share_pct": float(
            100 * sorted_weights[:10].sum() / total
        ),
        "top_100_weight_share_pct": float(
            100 * sorted_weights[:100].sum() / total
        ),
        "max_weight_ratio": float(np.nanmax(ratios)),
        "median_weight_ratio": float(np.nanmedian(ratios)),
    }


def contribution_audit(values: np.ndarray, weights: np.ndarray) -> dict:
    """Concentration of a weighted total across contributing households."""
    contributions = np.asarray(values, dtype=float) * np.asarray(
        weights, dtype=float
    )
    positive = contributions[contributions > 0]
    total = float(positive.sum())
    if total <= 0:
        return {
            "positive_contributor_count": 0,
            "contributor_effective_sample_size": 0.0,
            "top_10_contribution_share_pct": 100.0,
            "top_100_contribution_share_pct": 100.0,
            "max_contribution_share_pct": 100.0,
        }
    sorted_contributions = np.sort(positive)[::-1]
    return {
        "positive_contributor_count": int(positive.size),
        "contributor_effective_sample_size": float(
            total**2 / float((positive**2).sum())
        ),
        "top_10_contribution_share_pct": float(
            100 * sorted_contributions[:10].sum() / total
        ),
        "top_100_contribution_share_pct": float(
            100 * sorted_contributions[:100].sum() / total
        ),
        "max_contribution_share_pct": float(
            100 * sorted_contributions[0] / total
        ),
    }


def evaluate_publication_gates(
    aggregate_audit: dict,
    contributor_audits: dict[str, dict],
    *,
    apply_contributor_gates: bool = True,
) -> dict:
    """Apply the late-year support gates to audit metrics.

    Aggregate household gates always apply; contributor gates apply from
    ``CONTRIBUTOR_GATE_START_YEAR`` (pass ``apply_contributor_gates=False``
    for earlier years, mirroring the v1 runtime default).
    """
    failures = []

    def check(metrics: dict, gates: dict, prefix: str) -> None:
        for metric, (direction, bound) in gates.items():
            value = metrics.get(metric)
            if value is None:
                failures.append(f"{prefix}{metric}: missing")
                continue
            if direction == "min" and value < bound:
                failures.append(
                    f"{prefix}{metric}: {value:,.1f} below minimum {bound:,.1f}"
                )
            if direction == "max" and value > bound:
                failures.append(
                    f"{prefix}{metric}: {value:,.1f} above maximum {bound:,.1f}"
                )

    check(aggregate_audit, AGGREGATE_GATES, "")
    if apply_contributor_gates:
        for name, metrics in contributor_audits.items():
            gates = CONTRIBUTOR_GATES.get(name)
            if gates:
                check(metrics, gates, f"{name}.")
    return {"passed": not failures, "failures": failures}


# ---------------------------------------------------------------------------
# Earnings scale
# ---------------------------------------------------------------------------


def taxable_payroll_at_scale(
    alpha: float,
    gross_wages: np.ndarray,
    taxable_self_employment: np.ndarray,
    weights: np.ndarray,
    cap: float,
) -> float:
    """SSA taxable payroll if every earnings amount is multiplied by alpha.

    Mirrors policyengine-us: wages are capped at the wage base; taxable
    self-employment income uses the remaining cap room.
    """
    taxable_wages = np.minimum(alpha * gross_wages, cap)
    remaining_room = np.maximum(0.0, cap - taxable_wages)
    taxable_se = np.minimum(alpha * taxable_self_employment, remaining_room)
    return float(((taxable_wages + taxable_se) * weights).sum())


def solve_earnings_scale(
    gross_wages: np.ndarray,
    taxable_self_employment: np.ndarray,
    weights: np.ndarray,
    cap: float,
    payroll_target: float,
    tol: float = 1e-13,
) -> float:
    """Scalar alpha such that scaled taxable payroll equals the target."""
    args = (gross_wages, taxable_self_employment, weights, cap)
    low, high = 1e-6, 1.0
    while taxable_payroll_at_scale(high, *args) < payroll_target:
        high *= 2
        if high > 1e4:
            ceiling = taxable_payroll_at_scale(np.inf, *args)
            raise RuntimeError(
                "Taxable payroll target "
                f"${payroll_target/1e9:,.1f}B exceeds the cap-bound ceiling "
                f"${ceiling/1e9:,.1f}B."
            )
    for _ in range(200):
        mid = 0.5 * (low + high)
        if taxable_payroll_at_scale(mid, *args) < payroll_target:
            low = mid
        else:
            high = mid
        if high - low < tol * max(high, 1.0):
            break
    return 0.5 * (low + high)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
