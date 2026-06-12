"""Year-dataset builder for the v2 baseline (see src/v2_projection.py).

Stage flow per year:

A. Materialize the latest enhanced CPS at the target year in a fresh
   simulation (PolicyEngine uprating supplies value growth).
B. Lightly reweight households to the SSA Trustees age distribution
   (entropy, 5-year buckets).
C. Rescale values to Trustees aggregates: earnings so SSA taxable payroll
   matches, Social Security benefits so OASDI cost matches. Write the H5.
D. Validate against the written artifact (with the Trustees long-run tax
   assumption active from 2035) and run the final light entropy calibration
   on the full target family: age, Social Security, taxable payroll,
   post-OBBBA OASDI TOB, post-OBBBA HI TOB. Update weights in place.

Every stage emits sentinel diagnostics; the year fails closed if the final
calibration misses targets or publication gates fail.
"""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from src.v2_projection import (
    aggregate_age_targets,
    build_age_bins,
    build_household_age_bin_matrix,
    calibrate_entropy_constraints,
    contribution_audit,
    entropy_weight_audit,
    evaluate_publication_gates,
    load_economic_targets,
    load_population_age_targets,
    load_tob_targets,
    solve_earnings_scale,
    target_source_provenance,
    write_json,
)
from src.tax_assumption_loader import (
    TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
    load_canonical_tax_assumption_reform,
)

TAX_ASSUMPTION_START_YEAR = 2035
TAX_ASSUMPTION_END_YEAR = 2100

PERSON_LEVEL_IDENTITY_INPUTS = (
    "person_id",
    "household_id",
    "person_household_id",
    "family_id",
    "person_family_id",
    "tax_unit_id",
    "person_tax_unit_id",
    "spm_unit_id",
    "person_spm_unit_id",
    "marital_unit_id",
    "person_marital_unit_id",
)

# Earnings-type inputs rescaled by the payroll factor alpha. Wage rates move
# with earnings so the implied hours stay fixed.
EARNINGS_SCALE_CANDIDATES = (
    "employment_income_before_lsr",
    "self_employment_income_before_lsr",
    "sstb_self_employment_income_before_lsr",
    "partnership_se_income",
    "farm_operations_income",
    "hourly_wage",
)

SOCIAL_SECURITY_SCALE_CANDIDATES = (
    "social_security_retirement",
    "social_security_disability",
    "social_security_survivors",
    "social_security_dependents",
)

# Non-earnings, non-Social-Security income of beneficiary households,
# rescaled by gamma so modeled taxation of benefits reaches the Trustees
# target at the value level (instead of through weight tilting).
OTHER_INCOME_SCALE_CANDIDATES = (
    "taxable_interest_income",
    "tax_exempt_interest_income",
    "qualified_dividend_income",
    "non_qualified_dividend_income",
    "long_term_capital_gains",
    "short_term_capital_gains",
    "non_sch_d_capital_gains",
    "taxable_ira_distributions",
    "taxable_pension_income",
    "tax_exempt_pension_income",
    "rental_income",
    "farm_rent_income",
    "estate_income",
    "partnership_s_corp_income",
    "miscellaneous_income",
)

# Gamma is a bounded calibration nudge, not a free knob: at 1.25 it can
# close modest TOB gaps, but larger values distort the income side (the
# 2026 diagnostic run with gamma 1.62 pushed AGI far above GDP). The
# final calibration and donor support absorb any residual.
GAMMA_MAX = 1.25
GAMMA_TOLERANCE = 0.02
GAMMA_MAX_PROBES = 4

# Income-side guard groups (mirroring the v1 production calibration):
# the final calibration must not change these aggregate income totals,
# so weight tilts cannot inflate other income to reach the TOB target.
INCOME_GUARD_GROUPS = {
    "preferential_investment_income": (
        "long_term_capital_gains_before_response",
        "long_term_capital_gains_on_collectibles",
        "qualified_dividend_income",
    ),
    "ordinary_nonpayroll_income": (
        "short_term_capital_gains",
        "non_sch_d_capital_gains",
        "non_qualified_dividend_income",
        "taxable_interest_income",
        "tax_exempt_interest_income",
        "partnership_s_corp_income",
        "partnership_se_income",
        "estate_income",
        "rental_income",
        "farm_income",
        "farm_operations_income",
        "farm_rent_income",
        "miscellaneous_income",
        "salt_refund_income",
        "taxable_401k_distributions",
        "taxable_403b_distributions",
        "taxable_ira_distributions",
        "taxable_private_pension_income",
        "taxable_sep_distributions",
        "tax_exempt_ira_distributions",
        "tax_exempt_private_pension_income",
        "qualified_bdc_income",
        "qualified_reit_and_ptp_income",
    ),
}
# Guards apply to every year: without them the final calibration can
# close taxation-of-benefits residuals by upweighting households heavy in
# concentrated income types (the 2026 diagnostic showed miscellaneous and
# partnership income doubling through the weight tilt alone).
INCOME_GUARD_START_YEAR = 2026

# Donor-clone late-year support: clone the strongest real
# taxation-of-benefits contributor households with deterministic income
# jitter so the final calibration has dense support where the 2024 sample
# is thin. Disabled by default: a clone-free 2100 build on the populace
# base passes every publication gate (TOB contributor ESS 152 OASDI /
# 127 HI against the >=50 gate), so the published datasets carry only
# real survey households. The machinery is retained for bases that
# cannot support the far horizon bare; set the start year to re-enable.
DONOR_CLONE_START_YEAR = 9999
DONOR_CLONE_TOP_HOUSEHOLDS = 4_000
DONOR_CLONES_PER_HOUSEHOLD = 8
DONOR_CLONE_PRIOR_SCALE = 0.10
DONOR_CLONE_OTHER_INCOME_SIGMA = 0.35
DONOR_CLONE_BENEFIT_SIGMA = 0.18

AGE_BUCKET_SIZE = 5

# Data repair at materialization. The published enhanced CPS stores
# corrupt miscellaneous_income values: dozens of person records pinned at
# exactly $795,294,848 (an imputation top-code artifact), summing to
# $9.3T weighted against a real-world total near $100B. Uprated across
# the 75-year horizon and amplified by donor cloning, these records
# poison the income side and the TOB contributor pool. Values above the
# threshold are unambiguously corrupt and are zeroed; the repair is
# logged and stamped into metadata. Upstream fix tracked in
# policyengine-us-data.
INPUT_REPAIR_CAPS = {
    "miscellaneous_income": 10_000_000.0,
}

# Long-run growth harmonization: the SOI uprating extensions packaged in
# policyengine-us grow several income categories faster than the economy
# forever (qualified dividends at about 5% per year against TR2026
# nominal GDP near 3.5%), so AGI outruns GDP at far horizons. Through
# 2034 the CBO-vintage growth stands; from 2035 each category's
# cumulative growth is capped at the TR2026 nominal-GDP path.
GROWTH_CAP_BASE_YEAR = 2034
GROWTH_CAP_VARIABLES = (
    "taxable_interest_income",
    "tax_exempt_interest_income",
    "qualified_dividend_income",
    "non_qualified_dividend_income",
    "long_term_capital_gains",
    "short_term_capital_gains",
    "non_sch_d_capital_gains",
    "taxable_ira_distributions",
    "taxable_pension_income",
    "tax_exempt_pension_income",
    "rental_income",
    "farm_rent_income",
    "estate_income",
    "partnership_s_corp_income",
    "miscellaneous_income",
    "qualified_bdc_income",
    "qualified_reit_and_ptp_income",
)


def _log(message: str) -> None:
    print(message, flush=True)


# ---------------------------------------------------------------------------
# Stage A: materialize the base dataset at the target year
# ---------------------------------------------------------------------------


def _person_level_values(sim, variable, *, period):
    try:
        series = sim.calculate(variable, period=period, map_to="person")
    except Exception:
        series = sim.calculate(variable, period=period)
    if hasattr(series, "values"):
        return np.asarray(series.values)
    return np.asarray(series)


def _ensure_person_level_identity_inputs(df, sim, *, base_period):
    output = df
    person_rows = len(output)
    for variable in PERSON_LEVEL_IDENTITY_INPUTS:
        column = f"{variable}__{base_period}"
        if column in output.columns:
            continue
        values = _person_level_values(sim, variable, period=base_period)
        if len(values) != person_rows:
            raise ValueError(
                f"{variable} mapped to {len(values)} rows; expected {person_rows}."
            )
        output[column] = values
    return output


def _pseudo_input_variables(sim) -> set[str]:
    """Stored adds-aggregates that must not ship in the year frame.

    An aggregate is dropped when every component can supply its value —
    either the component is itself a stored input (populace ships
    ``social_security`` alongside its four components) or it is
    formula-backed (the enhanced CPS ships ``employment_income`` whose
    behavioral-response component recomputes). Keeping the aggregate
    would shadow the adds formula and freeze stale values.
    """
    tbs = sim.tax_benefit_system
    stored = set(sim.input_variables)
    pseudo = set()
    for var_name in stored:
        variable = tbs.variables.get(var_name)
        adds = getattr(variable, "adds", None) if variable else None
        if not adds or not isinstance(adds, list):
            continue
        covered = True
        for component in adds:
            component_variable = tbs.variables.get(component)
            if component_variable is None:
                covered = False
                break
            if component in stored or len(getattr(component_variable, "formulas", {})):
                continue
            covered = False
            break
        if covered:
            pseudo.add(var_name)
    return pseudo


def _entity_membership_column(entity_key, *, base_period, year, columns):
    bases = (
        ["person_id"]
        if entity_key == "person"
        else [f"person_{entity_key}_id", f"{entity_key}_id"]
    )
    for base in bases:
        for candidate in (f"{base}__{base_period}", f"{base}__{year}"):
            if candidate in columns:
                return candidate
    return None


def _project_variable_to_person_rows(sim, df, *, var_name, year, base_period):
    values = np.asarray(sim.calculate(var_name, period=year).values)
    if len(values) == len(df):
        return values
    variable = sim.tax_benefit_system.variables.get(var_name)
    entity_key = getattr(getattr(variable, "entity", None), "key", None)
    if entity_key is None:
        raise ValueError(f"Cannot determine entity for {var_name}.")
    membership_column = _entity_membership_column(
        entity_key, base_period=base_period, year=year, columns=df.columns
    )
    if membership_column is None:
        raise ValueError(f"No membership column for {var_name} ({entity_key}).")
    entity_ids = np.asarray(sim.calculate(f"{entity_key}_id", map_to=entity_key).values)
    if len(entity_ids) != len(values):
        raise ValueError(f"Cannot align {var_name} on {entity_key}.")
    aligned = df[membership_column].map(dict(zip(entity_ids, values)))
    if aligned.isna().any():
        raise ValueError(f"{var_name}: unmapped person rows.")
    return np.asarray(aligned.values)


def _tr2026_gdp_growth(from_year: int, to_year: int) -> float:
    table = pd.read_csv(
        Path(__file__).resolve().parent.parent
        / "data"
        / "social_security_aux_tr2026.csv"
    ).set_index("year")
    return float(
        table.loc[to_year, "gdp_in_billion_nominal_usd"]
        / table.loc[from_year, "gdp_in_billion_nominal_usd"]
    )


def cap_longrun_income_growth(df: pd.DataFrame, sim, year: int) -> dict:
    """Cap each category's post-2034 cumulative growth at nominal GDP.

    Returns {variable: factor} for the categories that were scaled down.
    """
    if year <= GROWTH_CAP_BASE_YEAR:
        return {}
    gdp_growth = _tr2026_gdp_growth(GROWTH_CAP_BASE_YEAR, year)
    parameters = sim.tax_benefit_system.parameters
    factors: dict[str, float] = {}
    for variable_name in GROWTH_CAP_VARIABLES:
        variable = sim.tax_benefit_system.variables.get(variable_name)
        uprating = getattr(variable, "uprating", None) if variable else None
        column = f"{variable_name}__{year}"
        if uprating is None or column not in df.columns:
            continue
        parameter = parameters.get_child(uprating)
        category_growth = float(
            parameter(f"{year}-01-01") / parameter(f"{GROWTH_CAP_BASE_YEAR}-01-01")
        )
        if category_growth <= gdp_growth:
            continue
        factor = gdp_growth / category_growth
        df[column] = df[column] * factor
        factors[variable_name] = factor
    return factors


def sanitize_enum_inputs(df: pd.DataFrame, sim, year: int) -> dict:
    """Coerce enum values the model cannot encode to each variable's
    default (populace stores 'unknown' race codes that the strict
    ``set_input`` round-trip rejects). Returns {variable: records_coerced}.
    """
    log: dict = {}
    for column in df.columns:
        variable_name = column.rsplit("__", 1)[0]
        variable = sim.tax_benefit_system.variables.get(variable_name)
        possible = getattr(variable, "possible_values", None) if variable else None
        if possible is None:
            continue
        if df[column].dtype != object and not pd.api.types.is_string_dtype(df[column]):
            continue
        valid = {entry.name for entry in possible}
        values = df[column].astype(str)
        invalid = ~values.isin(valid)
        if invalid.any():
            default = getattr(variable, "default_value", None)
            default_name = default.name if hasattr(default, "name") else list(valid)[0]
            df.loc[invalid, column] = default_name
            log[variable_name] = int(invalid.sum())
    return log


def repair_corrupt_inputs(df: pd.DataFrame, year: int) -> dict:
    """Zero out unambiguously corrupt input values; returns the repair log."""
    log: dict = {}
    for variable, cap in INPUT_REPAIR_CAPS.items():
        column = f"{variable}__{year}"
        if column not in df.columns:
            continue
        values = df[column].to_numpy()
        corrupt = values > cap
        if corrupt.any():
            log[variable] = {
                "cap": cap,
                "records_zeroed": int(corrupt.sum()),
                "amount_zeroed": float(values[corrupt].sum()),
            }
            df.loc[corrupt, column] = 0.0
    return log


def materialize_year_frame(sim, year: int) -> pd.DataFrame:
    """Person-row input dataframe with every input variable at ``year``."""
    base_period = int(sim.default_calculation_period)
    df = sim.to_input_dataframe()
    # Some bases (populace) ship pre-uprated columns for many periods;
    # keep only the base period so this pipeline is the single uprating
    # authority and out-year columns cannot bypass the value stages.
    base_columns = [c for c in df.columns if c.endswith(f"__{base_period}")]
    if len(base_columns) < len(df.columns):
        df = df[base_columns].copy()
    df = _ensure_person_level_identity_inputs(df, sim, base_period=base_period)

    pseudo = _pseudo_input_variables(sim)
    drop = [
        f"{var}__{base_period}"
        for var in pseudo
        if f"{var}__{base_period}" in df.columns
    ]
    if drop:
        df = df.drop(columns=drop)

    fallback_renames = []
    for column in [c for c in df.columns if f"__{base_period}" in c]:
        var_name = column.replace(f"__{base_period}", "")
        new_column = f"{var_name}__{year}"
        if var_name in ("household_weight", "person_weight"):
            continue
        try:
            df[new_column] = _project_variable_to_person_rows(
                sim, df, var_name=var_name, year=year, base_period=base_period
            )
            df = df.drop(columns=[column])
        except Exception as error:
            fallback_renames.append(f"{var_name}: {error}")
            df = df.rename(columns={column: new_column})
    if fallback_renames:
        _log(
            f"  [materialize {year}] carried base-year values for "
            f"{len(fallback_renames)} variables"
        )
        for line in fallback_renames[:5]:
            print(f"    {line}", file=sys.stderr)

    # Household weights at the target year (includes uprated population
    # level); person weights derive from household weights at runtime.
    household_weights = sim.calculate(
        "household_id", period=year, map_to="household"
    ).weights
    household_ids = sim.calculate(
        "household_id", period=year, map_to="household"
    ).values
    hh_to_weight = dict(zip(household_ids, np.asarray(household_weights)))
    df[f"household_weight__{year}"] = df[f"person_household_id__{year}"].map(
        hh_to_weight
    )
    df = df.drop(
        columns=[
            f"household_weight__{base_period}",
            f"person_weight__{base_period}",
            f"person_weight__{year}",
        ],
        errors="ignore",
    )
    return df


def household_structure(df: pd.DataFrame, year: int):
    """Household ids, person->household row index, ages, base weights."""
    person_household_id = df[f"person_household_id__{year}"].to_numpy()
    household_ids = np.unique(person_household_id)
    hh_index = {hh: i for i, hh in enumerate(household_ids)}
    person_household_index = np.fromiter(
        (hh_index[hh] for hh in person_household_id),
        dtype=int,
        count=len(person_household_id),
    )
    ages = df[f"age__{year}"].to_numpy()
    weights = (
        pd.DataFrame(
            {
                "hh": person_household_id,
                "w": df[f"household_weight__{year}"].to_numpy(),
            }
        )
        .groupby("hh")
        .w.first()
        .reindex(household_ids)
        .to_numpy()
    )
    return household_ids, person_household_index, ages, weights


# ---------------------------------------------------------------------------
# H5 writing
# ---------------------------------------------------------------------------


def write_year_h5(df: pd.DataFrame, year: int, output_path: Path) -> None:
    """Materialize the input dataframe into a runnable PolicyEngine H5."""
    from policyengine_core.data.dataset import Dataset
    from policyengine_us import Microsimulation

    dataset = Dataset.from_dataframe(df, year)
    sim = Microsimulation()
    sim.dataset = dataset
    sim.build_from_dataset()

    # Dump only the variables the frame intends to ship. Anything else in
    # a holder (defaults, derived caches) would shadow its formula when the
    # dataset is simulated.
    intended = {column.rsplit("__", 1)[0] for column in df.columns}
    data = {}
    for variable in sim.tax_benefit_system.variables:
        if variable not in intended:
            continue
        holder = sim.get_holder(variable)
        known_periods = holder.get_known_periods()
        if not known_periods:
            continue
        data[variable] = {}
        for period in known_periods:
            values = np.array(holder.get_array(period))
            if values.dtype == np.object_:
                try:
                    values = values.astype("S")
                except (TypeError, ValueError):
                    continue
            data[variable][period] = values

    leaked = {
        name
        for name in data
        if name.endswith("_behavioral_response")
        or name
        in (
            "employment_income",
            "irs_employment_income",
            "payroll_tax_gross_wages",
            "taxable_self_employment_income",
            "taxable_earnings_for_social_security",
            "social_security",
            "tob_revenue_oasdi",
            "tob_revenue_medicare_hi",
            "income_tax",
        )
    }
    if leaked:
        raise RuntimeError(
            f"Derived variables leaked into the year frame: {sorted(leaked)}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output_path, "w") as handle:
        for variable, periods in data.items():
            group = handle.create_group(variable)
            for period, values in periods.items():
                group.create_dataset(str(period), data=values)
    del sim, dataset
    gc.collect()


def update_h5_household_weights(
    output_path: Path, year: int, household_weights: np.ndarray
) -> None:
    with h5py.File(output_path, "r+") as handle:
        key = f"household_weight/{year}"
        if key not in handle:
            raise RuntimeError(f"{output_path} lacks {key}.")
        stored = handle[key]
        if stored.shape != household_weights.shape:
            raise RuntimeError(
                f"household_weight shape {stored.shape} != {household_weights.shape}"
            )
        stored[...] = household_weights


# ---------------------------------------------------------------------------
# Year build
# ---------------------------------------------------------------------------


def _household_vectors(sim, year: int):
    """Household-level target vectors from a simulation."""

    def hh(variable):
        return np.asarray(
            sim.calculate(variable, period=year, map_to="household").values
        )

    payroll = hh("taxable_earnings_for_social_security") + hh(
        "social_security_taxable_self_employment_income"
    )
    return {
        "ss_total": hh("social_security"),
        "payroll_total": payroll,
        "oasdi_tob": hh("tob_revenue_oasdi"),
        "hi_tob": hh("tob_revenue_medicare_hi"),
        "income_tax": hh("income_tax"),
        "agi": hh("adjusted_gross_income"),
    }


def _sim_from_frame(
    df: pd.DataFrame, year: int, reform, scaffold_dataset: str | None = None
):
    """In-memory simulation over the current frame (no file round-trip).

    The constructor needs some dataset to scaffold entities before the
    frame replaces it; ``scaffold_dataset`` (normally the build's base
    dataset file) avoids resolving the HuggingFace default, which is both
    slower and a network dependency.
    """
    from policyengine_core.data.dataset import Dataset
    from policyengine_us import Microsimulation

    dataset = Dataset.from_dataframe(df, year)
    kwargs = {"dataset": scaffold_dataset} if scaffold_dataset else {}
    if reform is not None:
        kwargs["reform"] = reform
    sim = Microsimulation(**kwargs)
    sim.dataset = dataset
    sim.build_from_dataset()
    return sim


def _solve_other_income_gamma(
    df: pd.DataFrame,
    year: int,
    reform,
    other_income_columns: list[str],
    beneficiary_person_mask: np.ndarray,
    demographic_weights: np.ndarray,
    person_household_index: np.ndarray,
    tob_targets: dict[str, float],
    scaffold_dataset: str | None = None,
) -> tuple[float, list[dict]]:
    """Scale beneficiary households' other income toward the Trustees
    taxation-of-benefits target.

    Best-effort: at far horizons benefit inclusion saturates at 85% and
    bracket positions move slowly, so total TOB becomes nearly inelastic
    to other income. When probes show that, the solver stops at the best
    bounded gamma and the final entropy calibration closes the rest.

    Returns (gamma, probe history). The frame is NOT modified.
    """
    target_total = tob_targets["oasdi_tob"] + tob_targets["hi_tob"]
    probes: list[dict] = []

    def total_tob_at(gamma: float) -> float:
        probe_df = df.copy()
        scaled = probe_df.loc[beneficiary_person_mask, other_income_columns] * gamma
        probe_df.loc[beneficiary_person_mask, other_income_columns] = scaled
        sim = _sim_from_frame(probe_df, year, reform, scaffold_dataset)
        vectors = _household_vectors(sim, year)
        del sim
        gc.collect()
        total = float((vectors["oasdi_tob"] + vectors["hi_tob"]) @ demographic_weights)
        probes.append({"gamma": gamma, "total_tob": total})
        _log(
            f"    [gamma probe] gamma={gamma:.3f} -> total TOB "
            f"${total / 1e9:,.1f}B vs target ${target_total / 1e9:,.1f}B "
            f"({total / target_total - 1:+.1%})"
        )
        return total

    gamma = 1.0
    total = total_tob_at(gamma)
    if abs(total / target_total - 1) <= GAMMA_TOLERANCE:
        return gamma, probes

    elasticity = 1.5  # prior; refined after the second probe
    for _ in range(GAMMA_MAX_PROBES):
        ratio = target_total / total
        gamma_next = gamma * ratio ** (1 / elasticity)
        gamma_next = min(max(gamma_next, 1 / GAMMA_MAX), GAMMA_MAX)
        total_next = total_tob_at(gamma_next)
        implied = None
        if total_next > 0 and total > 0 and gamma_next != gamma:
            implied = float(np.log(total_next / total) / np.log(gamma_next / gamma))
            if 0.2 < implied < 6:
                elasticity = implied
        gamma, total = gamma_next, total_next
        if abs(total / target_total - 1) <= GAMMA_TOLERANCE:
            return gamma, probes
        if gamma in (GAMMA_MAX, 1 / GAMMA_MAX):
            break
        if implied is not None and implied < 0.2:
            # TOB is effectively saturated; more probes cannot help.
            break

    best = min(probes, key=lambda p: abs(p["total_tob"] / target_total - 1))
    _log(
        f"    [gamma] best-effort gamma={best['gamma']:.3f} leaves TOB gap "
        f"{best['total_tob'] / target_total - 1:+.1%}; final calibration "
        "closes the remainder"
    )
    return best["gamma"], probes


def _id_columns(df: pd.DataFrame, year: int) -> list[str]:
    return [
        f"{variable}__{year}"
        for variable in PERSON_LEVEL_IDENTITY_INPUTS
        if f"{variable}__{year}" in df.columns
    ]


def _append_donor_clones(
    df: pd.DataFrame,
    year: int,
    *,
    tob_by_household: np.ndarray,
    household_ids: np.ndarray,
    person_household_index: np.ndarray,
    weights: np.ndarray,
    other_income_columns: list[str],
    ss_columns: list[str],
) -> tuple[pd.DataFrame, dict]:
    """Append jittered clones of the strongest real TOB contributor
    households so late-year calibration has dense support.

    Clones keep entity structure (all ids re-keyed), receive deterministic
    lognormal jitter on other income and benefits, and carry small prior
    weights; the final calibration decides how much of each clone to use.
    """
    contributions = tob_by_household * weights
    donor_count = min(DONOR_CLONE_TOP_HOUSEHOLDS, int((contributions > 0).sum()))
    donor_rows = np.argsort(contributions)[::-1][:donor_count]
    donor_household_ids = set(household_ids[donor_rows])

    id_cols = _id_columns(df, year)
    df = df.copy()
    for column in id_cols:
        df[column] = df[column].astype(np.int64)

    donor_mask = np.isin(
        df[f"person_household_id__{year}"].to_numpy(), list(donor_household_ids)
    )
    donor_frame = df.loc[donor_mask]
    donor_person_household = donor_frame[f"person_household_id__{year}"].to_numpy()

    # Compact per-column re-keying: clone ids start just above each id
    # column's existing maximum. Power-of-ten offsets would exceed int32
    # range and float32 precision inside policyengine-core.
    column_max = {column: int(df[column].max()) for column in id_cols}
    column_codes = {}
    column_unique_counts = {}
    for column in id_cols:
        codes, uniques = pd.factorize(donor_frame[column], sort=True)
        column_codes[column] = codes
        column_unique_counts[column] = len(uniques)

    clone_person_rows = np.flatnonzero(donor_mask)
    clone_frames = []
    for copy_index in range(1, DONOR_CLONES_PER_HOUSEHOLD + 1):
        clone = donor_frame.copy()
        for column in id_cols:
            clone[column] = (
                column_max[column]
                + 1
                + (copy_index - 1) * column_unique_counts[column]
                + column_codes[column]
            )
        rng = np.random.default_rng(year * 100 + copy_index)
        per_household_other = {
            hh: factor
            for hh, factor in zip(
                sorted(donor_household_ids),
                np.exp(
                    rng.normal(
                        -0.5 * DONOR_CLONE_OTHER_INCOME_SIGMA**2,
                        DONOR_CLONE_OTHER_INCOME_SIGMA,
                        len(donor_household_ids),
                    )
                ),
            )
        }
        per_household_benefit = {
            hh: factor
            for hh, factor in zip(
                sorted(donor_household_ids),
                np.exp(
                    rng.normal(
                        -0.5 * DONOR_CLONE_BENEFIT_SIGMA**2,
                        DONOR_CLONE_BENEFIT_SIGMA,
                        len(donor_household_ids),
                    )
                ),
            )
        }
        other_factor = np.array(
            [per_household_other[hh] for hh in donor_person_household]
        )
        benefit_factor = np.array(
            [per_household_benefit[hh] for hh in donor_person_household]
        )
        clone[other_income_columns] = clone[other_income_columns].mul(
            other_factor, axis=0
        )
        clone[ss_columns] = clone[ss_columns].mul(benefit_factor, axis=0)
        clone[f"household_weight__{year}"] = (
            clone[f"household_weight__{year}"] * DONOR_CLONE_PRIOR_SCALE
        )
        clone_frames.append(clone)

    augmented = pd.concat([df] + clone_frames, ignore_index=True)
    info = {
        "name": "v2-donor-clone-v1",
        "donor_household_count": donor_count,
        "clones_per_household": DONOR_CLONES_PER_HOUSEHOLD,
        "clone_household_count": donor_count * DONOR_CLONES_PER_HOUSEHOLD,
        "prior_weight_scale": DONOR_CLONE_PRIOR_SCALE,
        "other_income_jitter_sigma": DONOR_CLONE_OTHER_INCOME_SIGMA,
        "benefit_jitter_sigma": DONOR_CLONE_BENEFIT_SIGMA,
        "clone_person_rows": int(donor_mask.sum()) * DONOR_CLONES_PER_HOUSEHOLD,
        "donor_person_row_indices": clone_person_rows,
    }
    return augmented, info


def _income_guard_vectors(sim, year: int) -> dict[str, np.ndarray]:
    """Household-level income-guard group vectors from a simulation."""
    groups = {}
    for group_name, components in INCOME_GUARD_GROUPS.items():
        total = None
        for component in components:
            if component not in sim.tax_benefit_system.variables:
                continue
            values = np.asarray(
                sim.calculate(component, period=year, map_to="household").values,
                dtype=float,
            )
            total = values if total is None else total + values
        if total is not None and np.abs(total).sum() > 1e-6:
            groups[f"income_guard_{group_name}"] = total
    return groups


def _gdp_for_year(year: int) -> float:
    table = pd.read_csv(
        Path(__file__).resolve().parent.parent
        / "data"
        / "social_security_aux_tr2026.csv"
    ).set_index("year")
    return float(table.loc[year, "gdp_in_billion_nominal_usd"]) * 1e9


def _tax_assumption_reform(year: int):
    if year < TAX_ASSUMPTION_START_YEAR:
        return None
    return load_canonical_tax_assumption_reform(
        TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        start_year=TAX_ASSUMPTION_START_YEAR,
        end_year=TAX_ASSUMPTION_END_YEAR,
    )


def _gap_table(label: str, achieved: dict, targets: dict) -> None:
    _log(f"  [{label}]")
    for name, target in targets.items():
        value = achieved[name]
        _log(
            f"    {name:>14}: ${value / 1e9:>10,.1f}B vs "
            f"${target / 1e9:>10,.1f}B ({value / target - 1:+.2%})"
        )


def build_year(
    year: int,
    base_dataset: str,
    output_dir: Path,
    *,
    base_dataset_label: str | None = None,
    policyengine_us_version: str | None = None,
) -> dict:
    """Build one calibrated year dataset; returns the sentinel record."""
    from policyengine_us import Microsimulation

    start_time = time.monotonic()
    output_dir = Path(output_dir)
    output_path = output_dir / f"{year}.h5"
    _log(f"\n===== building {year} =====")

    economic_targets = load_economic_targets(year)
    tob_targets = load_tob_targets(year)
    ages_axis, population_totals = load_population_age_targets(year)
    bins = build_age_bins(AGE_BUCKET_SIZE)
    age_targets = aggregate_age_targets(population_totals, bins)

    # ----- Stage A: materialize -----
    # The input frame must be extracted before any other calculation:
    # calculated caches would otherwise leak into the frame as stored
    # outputs and shadow their formulas downstream.
    sim = Microsimulation(dataset=base_dataset)
    df = materialize_year_frame(sim, year)
    enum_log = sanitize_enum_inputs(df, sim, year)
    for variable, count in enum_log.items():
        _log(f"  [sanitize] {variable}: coerced {count:,} invalid enum values")
    repair_log = repair_corrupt_inputs(df, year)
    for variable, repair in repair_log.items():
        _log(
            f"  [repair] {variable}: zeroed {repair['records_zeroed']:,} "
            f"records above ${repair['cap']:,.0f} "
            f"(${repair['amount_zeroed'] / 1e9:,.1f}B unweighted)"
        )
    growth_caps = cap_longrun_income_growth(df, sim, year)
    if growth_caps:
        capped = ", ".join(
            f"{name} x{factor:.2f}" for name, factor in growth_caps.items()
        )
        _log(f"  [growth cap] post-2034 growth capped at GDP: {capped}")
    cap = float(
        sim.tax_benefit_system.parameters(
            f"{year}-01-01"
        ).gov.irs.payroll.social_security.cap
    )
    gross_wages = np.asarray(
        sim.calculate("payroll_tax_gross_wages", period=year).values
    )
    taxable_se = np.asarray(
        sim.calculate("taxable_self_employment_income", period=year).values
    )
    del sim
    gc.collect()

    household_ids, person_household_index, ages, base_weights = household_structure(
        df, year
    )
    n_households = len(household_ids)
    age_matrix, _ = build_household_age_bin_matrix(
        ages, person_household_index, n_households, AGE_BUCKET_SIZE
    )

    raw_population = float(base_weights @ age_matrix.sum(axis=1))
    raw_share_65 = float(base_weights @ age_matrix[:, 13:].sum(axis=1)) / raw_population
    target_share_65 = float(age_targets[13:].sum() / age_targets.sum())
    _log(
        f"  [stage A] population {raw_population / 1e6:,.1f}M vs target "
        f"{age_targets.sum() / 1e6:,.1f}M; 65+ share {raw_share_65:.1%} vs "
        f"target {target_share_65:.1%}"
    )

    # ----- Stage B: demographic reweight -----
    demographic_weights, _ = calibrate_entropy_constraints(
        age_matrix, age_targets, base_weights
    )
    audit_b = entropy_weight_audit(demographic_weights, base_weights)
    _log(
        f"  [stage B] age calibrated: ESS {audit_b['effective_sample_size']:,.0f}, "
        f"positive {audit_b['positive_weight_count']:,}/{n_households:,}, "
        f"median ratio {audit_b['median_weight_ratio']:.2f}"
    )

    # ----- Stage C: value scaling -----
    person_demo_weights = demographic_weights[person_household_index]
    alpha = solve_earnings_scale(
        gross_wages=gross_wages,
        taxable_self_employment=taxable_se,
        weights=person_demo_weights,
        cap=cap,
        payroll_target=economic_targets["payroll_total"],
    )
    ss_columns = [
        f"{var}__{year}"
        for var in SOCIAL_SECURITY_SCALE_CANDIDATES
        if f"{var}__{year}" in df.columns
    ]
    ss_person_total = df[ss_columns].sum(axis=1).to_numpy()
    ss_current = float((ss_person_total * person_demo_weights).sum())
    beta = economic_targets["ss_total"] / ss_current

    earnings_columns = [
        f"{var}__{year}"
        for var in EARNINGS_SCALE_CANDIDATES
        if f"{var}__{year}" in df.columns
    ]
    df[earnings_columns] = df[earnings_columns] * alpha
    df[ss_columns] = df[ss_columns] * beta
    _log(
        f"  [stage C] earnings scale alpha={alpha:.4f}, "
        f"benefits scale beta={beta:.4f} "
        f"({len(earnings_columns)} earnings cols, {len(ss_columns)} SS cols)"
    )

    df[f"household_weight__{year}"] = demographic_weights[person_household_index]

    # ----- Stage C-gamma: other income of beneficiary households -----
    reform = _tax_assumption_reform(year)
    other_income_columns = [
        f"{var}__{year}"
        for var in OTHER_INCOME_SCALE_CANDIDATES
        if f"{var}__{year}" in df.columns
    ]
    household_has_ss = (
        np.bincount(
            person_household_index,
            weights=ss_person_total,
            minlength=n_households,
        )
        > 0
    )
    beneficiary_person_mask = household_has_ss[person_household_index]
    gamma, gamma_probes = _solve_other_income_gamma(
        df,
        year,
        reform,
        other_income_columns,
        beneficiary_person_mask,
        demographic_weights,
        person_household_index,
        tob_targets,
        scaffold_dataset=base_dataset,
    )
    df.loc[beneficiary_person_mask, other_income_columns] = (
        df.loc[beneficiary_person_mask, other_income_columns] * gamma
    )
    _log(
        f"  [stage C-gamma] other-income scale gamma={gamma:.4f} "
        f"({len(other_income_columns)} columns, "
        f"{int(beneficiary_person_mask.sum()):,} beneficiary-household "
        "person rows)"
    )

    # ----- Stage C3: donor-clone support (late years) -----
    support_augmentation = None
    if year >= DONOR_CLONE_START_YEAR:
        probe_sim = _sim_from_frame(df, year, reform, base_dataset)
        probe_vectors = _household_vectors(probe_sim, year)
        del probe_sim
        gc.collect()
        df, support_augmentation = _append_donor_clones(
            df,
            year,
            tob_by_household=probe_vectors["oasdi_tob"] + probe_vectors["hi_tob"],
            household_ids=household_ids,
            person_household_index=person_household_index,
            weights=demographic_weights,
            other_income_columns=other_income_columns,
            ss_columns=ss_columns,
        )
        household_ids, person_household_index, ages, start_weights = (
            household_structure(df, year)
        )
        n_households = len(household_ids)
        age_matrix, _ = build_household_age_bin_matrix(
            ages, person_household_index, n_households, AGE_BUCKET_SIZE
        )
        _log(
            f"  [stage C3] appended "
            f"{support_augmentation['clone_household_count']:,} donor "
            f"clones from {support_augmentation['donor_household_count']:,} "
            "real contributor households"
        )

        # Clones add earnings and benefit mass; re-solve the value scales
        # on the augmented frame so totals stay pinned to the targets.
        donor_rows = support_augmentation.pop("donor_person_row_indices")
        copies = support_augmentation["clones_per_household"]
        gw_aug = np.concatenate(
            [alpha * gross_wages] + [alpha * gross_wages[donor_rows]] * copies
        )
        tse_aug = np.concatenate(
            [alpha * taxable_se] + [alpha * taxable_se[donor_rows]] * copies
        )
        person_weights_aug = start_weights[person_household_index]
        alpha_correction = solve_earnings_scale(
            gross_wages=gw_aug,
            taxable_self_employment=tse_aug,
            weights=person_weights_aug,
            cap=cap,
            payroll_target=economic_targets["payroll_total"],
        )
        df[earnings_columns] = df[earnings_columns] * alpha_correction
        alpha *= alpha_correction
        ss_aug_total = float(
            (df[ss_columns].sum(axis=1).to_numpy() * person_weights_aug).sum()
        )
        beta_correction = economic_targets["ss_total"] / ss_aug_total
        df[ss_columns] = df[ss_columns] * beta_correction
        beta *= beta_correction
        # Clones also add other-income mass that nothing else re-pins
        # (the pre-clone runs showed AGI jumping ~30 points of GDP at the
        # donor start year). Normalize each other-income category back to
        # its pre-clone weighted total so clones provide support without
        # changing value aggregates.
        base_rows = len(gross_wages)
        pre_clone_other = (
            df[other_income_columns]
            .iloc[:base_rows]
            .mul(person_weights_aug[:base_rows], axis=0)
            .sum()
            .sum()
        )
        post_clone_other = (
            df[other_income_columns].mul(person_weights_aug, axis=0).sum().sum()
        )
        other_income_correction = (
            pre_clone_other / post_clone_other if post_clone_other else 1.0
        )
        df[other_income_columns] = df[other_income_columns] * other_income_correction
        support_augmentation["alpha_correction"] = alpha_correction
        support_augmentation["beta_correction"] = beta_correction
        support_augmentation["other_income_correction"] = other_income_correction
        _log(
            f"  [stage C3] post-clone rescale: alpha x{alpha_correction:.4f}, "
            f"beta x{beta_correction:.4f}, other income "
            f"x{other_income_correction:.4f}"
        )
    else:
        start_weights = demographic_weights

    write_year_h5(df, year, output_path)

    # ----- Stage C2: artifact-true validation -----
    sim2 = Microsimulation(dataset=str(output_path), reform=reform)
    vectors = _household_vectors(sim2, year)
    sim2_household_ids = np.asarray(
        sim2.calculate("household_id", period=year, map_to="household").values
    )
    if not np.array_equal(sim2_household_ids, household_ids):
        raise RuntimeError("Household order changed between stages.")
    guard_vectors = (
        _income_guard_vectors(sim2, year) if year >= INCOME_GUARD_START_YEAR else {}
    )
    del sim2
    gc.collect()

    achieved_scaled = {
        name: float(vectors[name] @ start_weights)
        for name in ("ss_total", "payroll_total", "oasdi_tob", "hi_tob")
    }
    all_targets = {**economic_targets, **tob_targets}
    _gap_table(
        "stage C2: post-scaling, pre-final-calibration", achieved_scaled, all_targets
    )

    payroll_gap = (
        achieved_scaled["payroll_total"] / economic_targets["payroll_total"] - 1
    )
    if abs(payroll_gap) > 0.02:
        raise RuntimeError(
            f"Earnings scaling missed payroll by {payroll_gap:+.2%}; "
            "the scaled-variable set needs review."
        )

    # ----- Stage D: final light calibration -----
    guard_targets = {
        name: float(values @ start_weights) for name, values in guard_vectors.items()
    }
    if guard_targets:
        _log(
            "  [income guards] "
            + ", ".join(
                f"{name.removeprefix('income_guard_')} ${target / 1e9:,.0f}B"
                for name, target in guard_targets.items()
            )
        )
    constraint_matrix = np.column_stack(
        [
            age_matrix,
            vectors["ss_total"],
            vectors["payroll_total"],
            vectors["oasdi_tob"],
            vectors["hi_tob"],
        ]
        + list(guard_vectors.values())
    )
    constraint_targets = np.concatenate(
        [
            age_targets,
            [
                economic_targets["ss_total"],
                economic_targets["payroll_total"],
                tob_targets["oasdi_tob"],
                tob_targets["hi_tob"],
            ],
            list(guard_targets.values()),
        ]
    )
    final_weights, solve_info = calibrate_entropy_constraints(
        constraint_matrix, constraint_targets, start_weights
    )
    audit_d = entropy_weight_audit(final_weights, start_weights)
    contributor_audits = {
        name: contribution_audit(vectors[name], final_weights)
        for name in ("ss_total", "payroll_total", "oasdi_tob", "hi_tob")
    }
    achieved_final = {
        name: float(vectors[name] @ final_weights)
        for name in ("ss_total", "payroll_total", "oasdi_tob", "hi_tob")
    }
    _gap_table("stage D: final calibration", achieved_final, all_targets)
    gdp = _gdp_for_year(year)
    agi_total = float(vectors["agi"] @ final_weights)
    income_tax_total_check = float(vectors["income_tax"] @ final_weights)
    _log(
        f"  [income side] AGI ${agi_total / 1e12:,.1f}T "
        f"({agi_total / gdp:.0%} of GDP), income tax "
        f"${income_tax_total_check / 1e12:,.1f}T "
        f"({income_tax_total_check / gdp:.0%} of GDP)"
    )
    if agi_total / gdp > 1.0:
        _log(
            "    WARNING: AGI exceeds GDP; the income side is not "
            "plausible. Inspect gamma and the calibration tilt."
        )
    _log(
        f"  [stage D] ESS {audit_d['effective_sample_size']:,.0f}, positive "
        f"{audit_d['positive_weight_count']:,}/{n_households:,}, top-10 share "
        f"{audit_d['top_10_weight_share_pct']:.1f}%, max ratio vs start "
        f"{audit_d['max_weight_ratio']:.2f}"
    )
    for name, audit in contributor_audits.items():
        _log(
            f"    {name}: contributors {audit['positive_contributor_count']:,}, "
            f"contributor ESS {audit['contributor_effective_sample_size']:,.0f}, "
            f"top-10 {audit['top_10_contribution_share_pct']:.0f}%"
        )

    from src.v2_projection import CONTRIBUTOR_GATE_START_YEAR

    gates = evaluate_publication_gates(
        audit_d,
        contributor_audits,
        apply_contributor_gates=year >= CONTRIBUTOR_GATE_START_YEAR,
    )
    if not gates["passed"]:
        for failure in gates["failures"]:
            _log(f"    GATE FAILURE: {failure}")
        raise RuntimeError(f"{year}: publication gates failed.")

    update_h5_household_weights(output_path, year, final_weights)

    income_tax_total = float(vectors["income_tax"] @ final_weights)
    elapsed = time.monotonic() - start_time

    sentinel = {
        "year": year,
        "alpha_earnings_scale": alpha,
        "beta_benefits_scale": beta,
        "gamma_other_income_scale": gamma,
        "population_raw": raw_population,
        "population_target": float(age_targets.sum()),
        "share_65_plus_raw": raw_share_65,
        "share_65_plus_target": target_share_65,
        "income_tax_total": income_tax_total,
        "max_constraint_pct_error": solve_info["max_constraint_pct_error"],
        "duration_seconds": elapsed,
        "duration_clock": "time.monotonic",
        **{f"{k}_achieved": v for k, v in achieved_final.items()},
        **{f"{k}_target": v for k, v in all_targets.items()},
        **{f"prescale_{k}": v for k, v in achieved_scaled.items()},
        **{f"stage_b_{k}": v for k, v in audit_b.items()},
        **{f"final_{k}": v for k, v in audit_d.items()},
        **{
            f"{name}_{metric}": value
            for name, audit in contributor_audits.items()
            for metric, value in audit.items()
        },
        "donor_clone_household_count": (
            support_augmentation["clone_household_count"] if support_augmentation else 0
        ),
        "gates_passed": gates["passed"],
    }

    metadata = {
        "contract_version": 2,
        "method": "v2-demographic-reweight-value-scaling",
        "year": year,
        "base_dataset_path": base_dataset_label or str(base_dataset),
        "calibration_audit": {
            "calibration_quality": "exact",
            "method_used": "entropy",
            "max_constraint_pct_error": solve_info["max_constraint_pct_error"],
            **{f"stage_b_{k}": v for k, v in audit_b.items()},
            **audit_d,
            "constraints": {
                name: {
                    "target": all_targets[name],
                    "achieved": achieved_final[name],
                    "pct_error": achieved_final[name] / all_targets[name] - 1,
                }
                for name in achieved_final
            }
            | {
                name: {
                    "target": target,
                    "achieved": float(guard_vectors[name] @ final_weights),
                }
                for name, target in guard_targets.items()
            },
            "contributors": contributor_audits,
            "validation_passed": True,
            "validation_issues": [],
        },
        "support_augmentation": support_augmentation,
        "input_repairs": repair_log,
        "enum_sanitization": enum_log,
        "longrun_growth_caps": growth_caps,
        "value_scaling": {
            "alpha_earnings_scale": alpha,
            "beta_benefits_scale": beta,
            "gamma_other_income_scale": gamma,
            "gamma_probes": gamma_probes,
            "earnings_columns": earnings_columns,
            "social_security_columns": ss_columns,
            "other_income_columns": other_income_columns,
            "beneficiary_person_rows": int(beneficiary_person_mask.sum()),
        },
        "profile": {
            "name": "v2-demo-values",
            "description": (
                "Light demographic entropy reweight to Trustees age "
                "distribution, value rescaling to Trustees taxable payroll "
                "and OASDI cost, final light entropy calibration to age, "
                "Social Security, taxable payroll, and post-OBBBA TOB."
            ),
            "age_bucket_size": AGE_BUCKET_SIZE,
            "calibration_method": "entropy",
        },
        "policyengine_us": {"version": policyengine_us_version},
        "target_source": {
            "name": "post_obbba_tob_75y",
            "baseline_kind": "calibration_target",
            "not_law": True,
            "files": target_source_provenance(),
        },
        "tax_assumption": {
            "name": TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
            "start_year": TAX_ASSUMPTION_START_YEAR,
            "end_year": TAX_ASSUMPTION_END_YEAR,
            "active": year >= TAX_ASSUMPTION_START_YEAR,
            "description": (
                "Social Security benefit-tax thresholds fixed in nominal "
                "dollars; IRS uprating follows the NAWI wage path from 2035."
            ),
        },
        "sentinel": sentinel,
    }
    write_json(Path(f"{output_path}.metadata.json"), metadata)
    _log(f"  wrote {output_path} ({elapsed:,.0f}s)")
    return sentinel
