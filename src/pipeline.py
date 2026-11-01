"""Year-dataset builder for the baseline (see src/projection.py).

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

import ast
import gc
import inspect
import json
import textwrap
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from src.projection import (
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
    H5_ECONOMIC_ASSUMPTION_ATTR,
    TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
    compose_reforms,
    economic_assumption_provenance,  # noqa: F401 - re-exported for the build script
    load_canonical_tax_assumption_reform,
    load_economic_assumption_reform,  # noqa: F401 - re-exported for the build script
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

# Every scaling and growth-cap list names stored inputs: the leaves the year
# frame carries. PolicyEngine US 2.x turned several names the 1.x lists used
# into formulas or adds-aggregates, which the frame never carries (see
# _pseudo_input_variables). Each such name maps to the stored leaves below,
# and every leaf of one name takes the same factor.
PRE_2X_NAME_LEAVES = {
    "partnership_se_income": ("partnership_self_employment_net_earnings",),
    "long_term_capital_gains": ("long_term_capital_gains_before_response",),
    "taxable_pension_income": (
        "taxable_public_pension_income",
        "taxable_private_pension_income",
    ),
    "tax_exempt_pension_income": (
        "tax_exempt_public_pension_income",
        "tax_exempt_private_pension_income",
    ),
    "partnership_s_corp_income": ("partnership_income", "s_corp_income"),
    "social_security_retirement": ("social_security_retirement_reported",),
    "social_security_disability": ("social_security_disability_reported",),
    "social_security_survivors": ("social_security_survivors_reported",),
    "social_security_dependents": ("social_security_dependents_reported",),
}

# Earnings-type inputs rescaled by the payroll factor alpha. Wage rates move
# with earnings so the implied hours stay fixed.
EARNINGS_SCALE_CANDIDATES = (
    "employment_income_before_lsr",
    "self_employment_income_before_lsr",
    "sstb_self_employment_income_before_lsr",
    "partnership_self_employment_net_earnings",
    "farm_operations_income",
    "hourly_wage",
)

# PolicyEngine US 2.x computes the four benefit variables by formula from
# these stored reported inputs.
SOCIAL_SECURITY_SCALE_CANDIDATES = (
    "social_security_retirement_reported",
    "social_security_disability_reported",
    "social_security_survivors_reported",
    "social_security_dependents_reported",
)

# Non-earnings, non-Social-Security income of beneficiary households,
# rescaled by gamma so modeled taxation of benefits reaches the Trustees
# target at the value level (instead of through weight tilting).
OTHER_INCOME_SCALE_CANDIDATES = (
    "taxable_interest_income",
    "tax_exempt_interest_income",
    "qualified_dividend_income",
    "non_qualified_dividend_income",
    "long_term_capital_gains_before_response",
    "short_term_capital_gains",
    "non_sch_d_capital_gains",
    "taxable_ira_distributions",
    "taxable_sep_distributions",
    "taxable_401k_distributions",
    "taxable_403b_distributions",
    "keogh_distributions",
    "taxable_public_pension_income",
    "taxable_private_pension_income",
    "tax_exempt_public_pension_income",
    "tax_exempt_private_pension_income",
    "rental_income",
    "farm_rent_income",
    "estate_income",
    "partnership_income",
    "s_corp_income",
    "miscellaneous_income",
)

# These stored sources retain engine uprating, but receive no alpha, beta or
# gamma calibration factor. Every exception is explicit so new stored gross
# income cannot silently fall outside the calibration policy.
UNSCALED_GROSS_INCOME_SOURCES = {
    "salt_refund_income": "A refund of state tax, rather than a current income flow.",
    "alimony_income": "A transfer between former spouses, not newly generated income.",
    "unemployment_compensation": (
        "An insurance benefit; neither earnings nor retirement/investment income."
    ),
    "weeks_unemployed": (
        "A duration input determining unemployment benefits, not an income amount."
    ),
    "disability_benefits": (
        "An insurance benefit; neither earnings nor retirement/investment income."
    ),
    "tax_exempt_disability_benefits": (
        "The excluded portion of disability insurance, not an additional income flow."
    ),
    "divorce_year": "An alimony taxability selector, not an income amount.",
    "age": "An eligibility and contribution-limit selector, not income.",
    "is_full_time_college_student": (
        "A dependent-status selector for Social Security taxability, not income."
    ),
    "is_related_to_head_or_spouse": (
        "A filing-status selector for Social Security taxability, not income."
    ),
    "is_separated": (
        "A filing-status selector for Social Security taxability, not income."
    ),
    "is_surviving_spouse": (
        "A filing-status selector for Social Security taxability, not income."
    ),
    "tax_unit_role_input": (
        "Assigns income to a filer or dependent; it is not an income amount."
    ),
    "traditional_401k_contributions_desired": (
        "A retirement deferral reducing taxable wages, not an additional gross flow."
    ),
    "roth_401k_contributions_desired": (
        "A retirement deferral used to allocate contribution limits, not gross income."
    ),
}

# Inputs a scaling or cap list names that the base may not store. Each is a
# PolicyEngine US input with no formula, so an absent column means the engine
# reads its default of zero and there is nothing to scale; build_year checks
# that against the engine. Any other name that fails to resolve raises.
KNOWN_ABSENT_INPUTS = {
    "taxable_public_pension_income": (
        "populace_us_2024 stores only taxable_private_pension_income, with no "
        "public-pension column"
    ),
    "tax_exempt_public_pension_income": (
        "populace_us_2024 stores only tax_exempt_private_pension_income, with "
        "no public-pension column"
    ),
}

# Gamma is a bounded calibration nudge, not a free knob: at 1.25 it can
# close modest TOB gaps, but larger values distort the income side (the
# 2026 diagnostic run with gamma 1.62 pushed AGI far above GDP). The
# final calibration absorbs any residual.
GAMMA_MAX = 1.25
GAMMA_TOLERANCE = 0.02
GAMMA_MAX_PROBES = 4
HOUSEHOLD_VECTOR_VARIABLES = (
    "social_security",
    "taxable_earnings_for_social_security",
    "social_security_taxable_self_employment_income",
    "tob_revenue_oasdi",
    "tob_revenue_medicare_hi",
    "income_tax",
    "adjusted_gross_income",
)

# Income-side guard groups (mirroring the v1 production calibration):
# the final calibration must not change these aggregate income totals,
# so weight tilts cannot inflate other income to reach the TOB target.
# Components are engine variables, calculated (not read from the frame), so
# adds-aggregates such as partnership_s_corp_income belong here; a name the
# engine lacks raises. Its partnership_income and s_corp_income leaves stay
# out so each source is counted once.
# partnership_self_employment_net_earnings stays out:
# PolicyEngine US documents it as "not an additional gross income source
# separate from partnership_income", which partnership_s_corp_income covers.
INCOME_GUARD_GROUPS = {
    # long_term_capital_gains_on_collectibles stays out: PolicyEngine US
    # documents it as a memo item that long-term capital gains already
    # include, so adding it would count collectibles gains twice.
    # qualified_bdc_income and qualified_reit_and_ptp_income are QBID memo
    # inputs within dividends, and farm_income is a Schedule J averaging
    # input. None is a gov.irs.gross_income.sources entry.
    "preferential_investment_income": (
        "long_term_capital_gains_before_response",
        "qualified_dividend_income",
    ),
    "ordinary_nonpayroll_income": (
        "short_term_capital_gains",
        "non_sch_d_capital_gains",
        "non_qualified_dividend_income",
        "taxable_interest_income",
        "tax_exempt_interest_income",
        "partnership_s_corp_income",
        "estate_income",
        "rental_income",
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
    ),
}
# Guards apply to every year: without them the final calibration can
# close taxation-of-benefits residuals by upweighting households heavy in
# concentrated income types (the 2026 diagnostic showed miscellaneous and
# partnership income doubling through the weight tilt alone).
INCOME_GUARD_START_YEAR = 2026

AGE_BUCKET_SIZE = 5

# Data repair at materialization. The published enhanced CPS stores
# corrupt miscellaneous_income values: dozens of person records pinned at
# exactly $795,294,848 (an imputation top-code artifact), summing to
# $9.3T weighted against a real-world total near $100B. Uprated across
# the 75-year horizon, these records
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
# cumulative growth is capped at the TR2026 nominal-GDP path. Category
# growth is the national total's growth: PolicyEngine US 2.x uprates each
# input by its total divided by population (household weights carry
# population growth), so the cap reads the total that per-capita series
# derives from.
GROWTH_CAP_BASE_YEAR = 2034
GROWTH_CAP_VARIABLES = (
    "taxable_interest_income",
    "tax_exempt_interest_income",
    "qualified_dividend_income",
    "non_qualified_dividend_income",
    "long_term_capital_gains_before_response",
    "short_term_capital_gains",
    "non_sch_d_capital_gains",
    "taxable_ira_distributions",
    "taxable_sep_distributions",
    "taxable_401k_distributions",
    "taxable_403b_distributions",
    "keogh_distributions",
    "taxable_public_pension_income",
    "taxable_private_pension_income",
    "tax_exempt_public_pension_income",
    "tax_exempt_private_pension_income",
    "rental_income",
    "farm_rent_income",
    "estate_income",
    "partnership_income",
    "s_corp_income",
    "miscellaneous_income",
    "qualified_bdc_income",
    "qualified_reit_and_ptp_income",
)


def _log(message: str) -> None:
    print(message, flush=True)


# ---------------------------------------------------------------------------
# Name resolution: every scaling and cap name resolves to a frame column or
# raises
# ---------------------------------------------------------------------------

SCALE_LISTS = {
    "EARNINGS_SCALE_CANDIDATES": EARNINGS_SCALE_CANDIDATES,
    "SOCIAL_SECURITY_SCALE_CANDIDATES": SOCIAL_SECURITY_SCALE_CANDIDATES,
    "OTHER_INCOME_SCALE_CANDIDATES": OTHER_INCOME_SCALE_CANDIDATES,
}


def assert_scale_lists_disjoint(lists: dict[str, tuple[str, ...]] = SCALE_LISTS):
    """Raise if a name repeats within a list or appears in two scale lists.

    Alpha, beta and gamma multiply their lists one after another, so a name
    in two lists (or twice in one) would be scaled twice.
    """
    owner: dict[str, str] = {}
    for list_name, names in lists.items():
        for name in names:
            if name in owner:
                raise ValueError(
                    f"{name} appears in both {owner[name]} and {list_name}; "
                    "it would be scaled twice."
                )
            owner[name] = list_name


def _check_known_absent_input(name: str, variables) -> None:
    variable = variables.get(name)
    if variable is None:
        raise ValueError(
            f"{name} is on KNOWN_ABSENT_INPUTS but the engine has no such variable."
        )
    if getattr(variable, "formulas", None) or getattr(variable, "adds", None):
        raise ValueError(
            f"{name} is on KNOWN_ABSENT_INPUTS but the engine computes it, so "
            "an absent column does not mean zero; scale its stored leaves."
        )


def resolve_frame_columns(
    df: pd.DataFrame,
    names,
    year: int,
    *,
    list_name: str,
    variables=None,
) -> tuple[list[str], dict[str, str]]:
    """Map each name to its ``{name}__{year}`` column in the year frame.

    Returns (columns, absent): ``absent`` holds the names left out because
    they sit on KNOWN_ABSENT_INPUTS, with the reason. Any other name without
    a column raises, naming every such name. With ``variables`` (the engine's
    variable registry), each absent name must be an engine input without a
    formula, so leaving it out cannot drop computed income.
    """
    columns: list[str] = []
    absent: dict[str, str] = {}
    missing: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"{list_name} names {name} twice.")
        seen.add(name)
        column = f"{name}__{year}"
        if column in df.columns:
            columns.append(column)
        elif name in KNOWN_ABSENT_INPUTS:
            if variables is not None:
                _check_known_absent_input(name, variables)
            absent[name] = KNOWN_ABSENT_INPUTS[name]
        else:
            missing.append(name)
    if missing:
        details = []
        for name in missing:
            leaves = PRE_2X_NAME_LEAVES.get(name)
            details.append(
                f"{name} (PolicyEngine US 2.x stores it as {', '.join(leaves)})"
                if leaves
                else name
            )
        raise ValueError(
            f"{list_name}: no year-{year} frame column for "
            + "; ".join(details)
            + ". Add each to the list's stored leaves or, if the base "
            "genuinely lacks it, to KNOWN_ABSENT_INPUTS with the reason."
        )
    return columns, absent


def gross_income_stored_inputs(df: pd.DataFrame, sim, year: int) -> set[str]:
    """Find stored inputs behind the engine's gross-income source list.

    Follow adds aggregates and named variable references in the active formula,
    stopping when a stored column overrides a formula. The traversal also sees
    stored taxability selectors, which need an explicit unscaled reason.
    """
    system = sim.tax_benefit_system
    variables, parameters = system.variables, system.parameters
    instant = f"{year}-01-01"
    sources = parameters.get_child("gov.irs.gross_income.sources")(instant)
    stored = {column.rsplit("__", 1)[0] for column in df.columns}
    reached: set[str] = set()
    seen: set[str] = set()

    def visit(name):
        if name in seen:
            return
        seen.add(name)
        if name in stored:
            reached.add(name)
            return
        variable = variables.get(name)
        if variable is None:
            # Adds can include a parameter amount (for example the Alaska
            # dividend), which supplies no stored input to classify.
            if "." in name:
                parameters.get_child(name)(instant)
                return
            raise ValueError(
                f"Gross-income source graph names unknown variable {name}."
            )
        adds = getattr(variable, "adds", None)
        if isinstance(adds, str):
            adds = parameters.get_child(adds)(instant)
        dependencies = set(adds or ())
        formulas = getattr(variable, "formulas", None) or {}
        if hasattr(variable, "get_formula"):
            formula = variable.get_formula(str(year))
        else:
            active = sorted(date for date in formulas if str(date) <= instant)
            formula = formulas[active[-1]] if active else None
        if formula is not None:
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(formula)))
            except (OSError, TypeError, SyntaxError) as error:
                raise ValueError(
                    f"Cannot inspect gross-income formula inputs for {name}."
                ) from error
            # Include names assigned to local lists before add(...), as well
            # as the usual direct person("input", period) calls.
            dependencies.update(
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in variables
            )
        for dependency in sorted(dependencies):
            visit(dependency)

    for source in sources:
        visit(source)
    return reached


def assert_gross_income_sources_classified(df: pd.DataFrame, sim, year: int) -> None:
    """Require a scaling policy or an explicit exception for every stored source."""
    scaled = {name for names in SCALE_LISTS.values() for name in names}
    missing = sorted(
        gross_income_stored_inputs(df, sim, year)
        - scaled
        - UNSCALED_GROSS_INCOME_SOURCES.keys()
    )
    if missing:
        raise ValueError(
            "Stored gross-income inputs have no scaling policy: "
            + ", ".join(missing)
            + ". Add them to a scaling list or UNSCALED_GROSS_INCOME_SOURCES "
            "with an explicit reason."
        )


def reject_pre_2x_names_in_frame(df: pd.DataFrame, year: int) -> None:
    """Raise if the frame stores a name the lists replaced with its leaves.

    A stored value overrides the engine's formula or adds-aggregate for that
    name, so scaling its leaves would leave the value the engine uses
    unscaled.
    """
    stored = sorted(
        name for name in PRE_2X_NAME_LEAVES if f"{name}__{year}" in df.columns
    )
    if stored:
        raise ValueError(
            f"The year-{year} frame stores {stored}; each would override the "
            "value computed from the scaled leaves "
            f"{[PRE_2X_NAME_LEAVES[name] for name in stored]}."
        )


def scale_frame_columns(
    df: pd.DataFrame,
    columns: list[str],
    factor: float,
    *,
    rows: np.ndarray | None = None,
) -> None:
    """Multiply ``columns`` by ``factor`` in place, on ``rows`` only if given.

    Row-wise scaling goes a column at a time. Above a million cells pandas
    hands a frame's product to numexpr, which promotes float32 to float64, and
    ``.loc`` then refuses to write the result back.
    """
    if rows is None:
        df[columns] = df[columns] * factor
        return
    for column in columns:
        values = df[column].to_numpy(copy=True)
        values[rows] *= float(factor)
        df[column] = values


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
    entity_ids = np.asarray(
        sim.calculate(f"{entity_key}_id", period=year, map_to=entity_key).values
    )
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


def growth_cap_uprating_parameter(variable_name: str, variables) -> str:
    """The parameter that uprates ``variable_name``; raises if there is none.

    A capped variable without an uprating parameter has no category growth to
    compare with GDP, so skipping it would leave its growth uncapped silently.
    """
    variable = variables.get(variable_name)
    if variable is None:
        raise ValueError(f"GROWTH_CAP_VARIABLES: the engine has no {variable_name}.")
    uprating = getattr(variable, "uprating", None)
    if not uprating:
        raise ValueError(
            f"GROWTH_CAP_VARIABLES: {variable_name} has no uprating parameter, "
            "so its growth cannot be compared with GDP. Name the parameter "
            "that grows it or drop it from the list."
        )
    return uprating


def growth_cap_total_parameter(uprating: str, parameters) -> str:
    """The national-total series whose growth the cap compares with GDP.

    PolicyEngine US 2.x points each dollar input at ``<total>_per_capita``,
    the total divided by population, and records the total in the series'
    ``derived_from`` metadata. Comparing that per-capita growth with total GDP
    growth would let a category's total outgrow GDP by population growth, so
    the cap reads the total. A series that is not derived per capita (as on
    1.x) is itself the total. A ``_per_capita`` series with no recorded total
    raises.
    """
    parameter = parameters.get_child(uprating)
    metadata = getattr(parameter, "metadata", None) or {}
    derived_from = metadata.get("derived_from")
    if derived_from:
        return derived_from
    if uprating.endswith("_per_capita"):
        raise ValueError(
            f"{uprating} is a per-capita series with no derived_from total, so "
            "its category growth cannot be compared with GDP."
        )
    return uprating


def cap_longrun_income_growth(
    df: pd.DataFrame, sim, year: int, audit: dict | None = None
) -> dict:
    """Cap each category's post-2034 cumulative growth at nominal GDP.

    Every name in GROWTH_CAP_VARIABLES must resolve to a frame column (or sit
    on KNOWN_ABSENT_INPUTS) and carry an uprating parameter, in every year;
    otherwise this raises. Category growth is the growth of the national
    total behind each variable's uprating series (see
    growth_cap_total_parameter); a category growing faster than GDP has its
    values scaled so its growth matches GDP's. Returns {variable: factor} for
    the categories that were scaled down; ``audit``, if given, receives each
    capped-list variable's parameters, growth and factor.
    """
    variables = sim.tax_benefit_system.variables
    columns, _ = resolve_frame_columns(
        df,
        GROWTH_CAP_VARIABLES,
        year,
        list_name="GROWTH_CAP_VARIABLES",
        variables=variables,
    )
    parameters = sim.tax_benefit_system.parameters
    sources = {}
    for column in columns:
        uprating = growth_cap_uprating_parameter(column.rsplit("__", 1)[0], variables)
        sources[column] = (uprating, growth_cap_total_parameter(uprating, parameters))
    if year <= GROWTH_CAP_BASE_YEAR:
        return {}
    gdp_growth = _tr2026_gdp_growth(GROWTH_CAP_BASE_YEAR, year)
    factors: dict[str, float] = {}
    for column, (uprating, total) in sources.items():
        variable_name = column.rsplit("__", 1)[0]
        parameter = parameters.get_child(total)
        category_growth = float(
            parameter(f"{year}-01-01") / parameter(f"{GROWTH_CAP_BASE_YEAR}-01-01")
        )
        factor = min(1.0, gdp_growth / category_growth)
        if audit is not None:
            audit[variable_name] = {
                "uprating_parameter": uprating,
                "growth_parameter": total,
                "category_growth": category_growth,
                "gdp_growth": gdp_growth,
                "factor": factor,
            }
        if category_growth <= gdp_growth:
            continue
        scale_frame_columns(df, [column], factor)
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

    projection_failures = []
    for column in [c for c in df.columns if f"__{base_period}" in c]:
        var_name = column.replace(f"__{base_period}", "")
        new_column = f"{var_name}__{year}"
        if var_name in ("household_weight", "person_weight"):
            continue
        if var_name == "person_id":
            # Its formula numbers rows in any year without a stored value,
            # while group ids have no formula and carry forward. Claim-age
            # draws key on person_id, so every year keeps the source ids.
            df = df.rename(columns={column: new_column})
            continue
        try:
            df[new_column] = _project_variable_to_person_rows(
                sim, df, var_name=var_name, year=year, base_period=base_period
            )
            if new_column != column:
                df = df.drop(columns=[column])
        except Exception as error:  # noqa: BLE001 - aggregate projection failures
            projection_failures.append(f"{var_name}: {error}")
    if projection_failures:
        raise ValueError(
            f"Cannot materialize inputs for {year}: " + "; ".join(projection_failures)
        )

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
    weight_columns = [f"person_weight__{base_period}", f"person_weight__{year}"]
    if base_period != year:
        weight_columns.append(f"household_weight__{base_period}")
    df = df.drop(columns=weight_columns, errors="ignore")
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


def write_year_h5(
    df: pd.DataFrame, year: int, output_path: Path, *, reform=None
) -> None:
    """Materialize the input dataframe into a runnable PolicyEngine H5."""
    sim = _sim_from_frame(df, year, reform)

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
    del sim
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


def _household_vectors(path, year: int, reform) -> dict[str, np.ndarray]:
    """Household-level target vectors from a year file."""
    from src.engine import household_vectors

    values = household_vectors(path, year, HOUSEHOLD_VECTOR_VARIABLES, reform=reform)
    return {
        "ss_total": values["social_security"],
        "payroll_total": values["taxable_earnings_for_social_security"]
        + values["social_security_taxable_self_employment_income"],
        "oasdi_tob": values["tob_revenue_oasdi"],
        "hi_tob": values["tob_revenue_medicare_hi"],
        "income_tax": values["income_tax"],
        "agi": values["adjusted_gross_income"],
    }


def _sim_from_frame(df: pd.DataFrame, year: int, reform):
    """In-memory simulation over the current frame (no file round-trip)."""
    from policyengine_core.data.dataset import Dataset

    from src.engine import frame_microsimulation

    return frame_microsimulation(Dataset.from_dataframe(df, year), reform=reform)


def _solve_other_income_gamma(
    df: pd.DataFrame,
    year: int,
    output_path: Path,
    economic_assumption_reform,
    reform,
    other_income_columns: list[str],
    beneficiary_person_mask: np.ndarray,
    demographic_weights: np.ndarray,
    person_household_index: np.ndarray,
    tob_targets: dict[str, float],
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
    # The suffix keeps a probe out of every "*.h5" scan of the output folder.
    probe_path = output_path.with_suffix(".gamma-probe")

    def total_tob_at(gamma: float) -> float:
        probe_df = df.copy()
        scale_frame_columns(
            probe_df, other_income_columns, gamma, rows=beneficiary_person_mask
        )
        try:
            write_year_h5(probe_df, year, probe_path, reform=economic_assumption_reform)
            del probe_df
            vectors = _household_vectors(probe_path, year, reform)
        finally:
            probe_path.unlink(missing_ok=True)
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


def _income_guard_vectors(sim, year: int) -> dict[str, np.ndarray]:
    """Household-level income-guard group vectors from a simulation.

    Raises if the engine lacks any component, naming each one. A group whose
    total is zero everywhere cannot take a positive calibration target, so it
    is left out and logged.
    """
    variables = sim.tax_benefit_system.variables
    unknown = sorted(
        {
            component
            for components in INCOME_GUARD_GROUPS.values()
            for component in components
            if component not in variables
        }
    )
    if unknown:
        raise ValueError(
            f"INCOME_GUARD_GROUPS names variables the engine lacks: {unknown}."
        )
    groups = {}
    for group_name, components in INCOME_GUARD_GROUPS.items():
        total = None
        for component in components:
            values = np.asarray(
                sim.calculate(component, period=year, map_to="household").values,
                dtype=float,
            )
            total = values if total is None else total + values
        if total is not None and np.abs(total).sum() > 1e-6:
            groups[f"income_guard_{group_name}"] = total
        else:
            _log(f"  [income guards] {group_name} is zero; not constrained")
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


# ---------------------------------------------------------------------------
# Economic assumption reform
# ---------------------------------------------------------------------------
# compose_reforms, load_economic_assumption_reform and
# economic_assumption_provenance live in src.tax_assumption_loader, so the
# scorers can load the reform a dataset recorded without importing the builder.


def _reform_label(reform) -> str:
    if isinstance(reform, tuple):
        return " + ".join(_reform_label(item) for item in reform)
    if isinstance(reform, type):
        return f"{reform.__module__}:{reform.__qualname__}"
    return type(reform).__name__


def _contribution_cap(sim, year: int) -> float:
    parameters = sim.tax_benefit_system.parameters(f"{year}-01-01")
    return float(parameters.gov.irs.payroll.social_security.cap)


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
    economic_assumption_reform=None,
    economic_assumption_metadata: dict | None = None,
) -> dict:
    """Build one calibrated year dataset; returns the sentinel record.

    ``economic_assumption_reform`` (off by default) applies to every
    simulation in the build. Stage A stores only the base year, and Core ages
    inputs to ``year`` on the reformed parameters. The reform applies alone in
    the H5 writer and ahead of the tax assumption in the gamma probes and
    artifact validation. ``economic_assumption_metadata`` records its provenance
    in both the H5 and the metadata sidecar.
    """
    from src.engine import dataset_microsimulation, stage_a_microsimulation

    assert_scale_lists_disjoint()
    start_time = time.monotonic()
    output_dir = Path(output_dir)
    output_path = output_dir / f"{year}.h5"
    economic_assumption = {
        "active": economic_assumption_reform is not None,
        "applies_before": "tax_assumption",
        "reform": (
            _reform_label(economic_assumption_reform)
            if economic_assumption_reform is not None
            else None
        ),
        **(economic_assumption_metadata or {}),
    }
    if economic_assumption_reform is not None:
        economic_assumption.update(
            inputs_aged_under_assumption=True, input_aging_end_year=year
        )
    _log(f"\n===== building {year} =====")

    economic_targets = load_economic_targets(year)
    tob_targets = load_tob_targets(year)
    ages_axis, population_totals = load_population_age_targets(year)
    bins = build_age_bins(AGE_BUCKET_SIZE)
    age_targets = aggregate_age_targets(population_totals, bins)

    # ----- Stage A: materialize -----
    # The input frame must be extracted before any other calculation:
    # calculated caches would otherwise leak into the frame as stored
    # outputs and shadow their formulas downstream. The certified populace base
    # is the default; an explicit local base_dataset path (a candidate build not
    # yet certified) is loaded as an unmanaged dataset, for sentinels.
    sim = stage_a_microsimulation(base_dataset, reform=economic_assumption_reform)
    df = materialize_year_frame(sim, year)
    reject_pre_2x_names_in_frame(df, year)
    assert_gross_income_sources_classified(df, sim, year)
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
    growth_cap_audit: dict = {}
    growth_caps = cap_longrun_income_growth(df, sim, year, audit=growth_cap_audit)
    if growth_caps:
        capped = ", ".join(
            f"{name} x{factor:.2f}" for name, factor in growth_caps.items()
        )
        _log(f"  [growth cap] post-2034 growth capped at GDP: {capped}")
    scale_columns: dict[str, list[str]] = {}
    absent_inputs: dict[str, str] = {}
    for list_name, names in SCALE_LISTS.items():
        columns, absent = resolve_frame_columns(
            df,
            names,
            year,
            list_name=list_name,
            variables=sim.tax_benefit_system.variables,
        )
        scale_columns[list_name] = columns
        absent_inputs.update(absent)
    # The cap read sees the economic assumption reform. The tax assumption
    # reform cannot move it (it rewrites only parameters uprated by
    # gov.irs.uprating; the cap follows gov.ssa.nawi), and Stage C2 checks
    # that against the fully composed reform.
    cap = _contribution_cap(sim, year)
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
    ss_columns = scale_columns["SOCIAL_SECURITY_SCALE_CANDIDATES"]
    ss_person_total = df[ss_columns].sum(axis=1).to_numpy()
    ss_current = float((ss_person_total * person_demo_weights).sum())
    if ss_current <= 0:
        raise RuntimeError(
            f"Social Security columns {ss_columns} sum to {ss_current:,.0f}; "
            "the benefit scale needs a positive base."
        )
    beta = economic_targets["ss_total"] / ss_current

    earnings_columns = scale_columns["EARNINGS_SCALE_CANDIDATES"]
    scale_frame_columns(df, earnings_columns, alpha)
    scale_frame_columns(df, ss_columns, beta)
    _log(
        f"  [stage C] earnings scale alpha={alpha:.4f}, "
        f"benefits scale beta={beta:.4f} "
        f"({len(earnings_columns)} earnings cols, {len(ss_columns)} SS cols)"
    )

    df[f"household_weight__{year}"] = demographic_weights[person_household_index]

    # ----- Stage C-gamma: other income of beneficiary households -----
    reform = compose_reforms(economic_assumption_reform, _tax_assumption_reform(year))
    other_income_columns = scale_columns["OTHER_INCOME_SCALE_CANDIDATES"]
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
        output_path,
        economic_assumption_reform,
        reform,
        other_income_columns,
        beneficiary_person_mask,
        demographic_weights,
        person_household_index,
        tob_targets,
    )
    scale_frame_columns(df, other_income_columns, gamma, rows=beneficiary_person_mask)
    _log(
        f"  [stage C-gamma] other-income scale gamma={gamma:.4f} "
        f"({len(other_income_columns)} columns, "
        f"{int(beneficiary_person_mask.sum()):,} beneficiary-household "
        "person rows)"
    )

    start_weights = demographic_weights

    write_year_h5(df, year, output_path, reform=economic_assumption_reform)

    with h5py.File(output_path, "r+") as handle:
        handle.attrs[H5_ECONOMIC_ASSUMPTION_ATTR] = json.dumps(economic_assumption)

    # ----- Stage C2: artifact-true validation -----
    vectors = _household_vectors(output_path, year, reform)
    sim2 = dataset_microsimulation(str(output_path), reform=reform)
    composed_cap = _contribution_cap(sim2, year)
    if composed_cap != cap:
        raise RuntimeError(
            f"The contribution cap is ${cap:,.0f} in Stage A but "
            f"${composed_cap:,.0f} under the composed reform; alpha was solved "
            "against the wrong cap."
        )
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

    gates = evaluate_publication_gates(audit_d, contributor_audits)
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
        "gates_passed": gates["passed"],
        "economic_assumption_reform": economic_assumption["reform"],
    }

    metadata = {
        "contract_version": 2,
        "method": "demographic-reweight-value-scaling",
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
        "input_repairs": repair_log,
        "enum_sanitization": enum_log,
        "longrun_growth_caps": growth_caps,
        "longrun_growth_cap_audit": growth_cap_audit,
        "value_scaling": {
            "alpha_earnings_scale": alpha,
            "beta_benefits_scale": beta,
            "gamma_other_income_scale": gamma,
            "gamma_probes": gamma_probes,
            "earnings_columns": earnings_columns,
            "social_security_columns": ss_columns,
            "other_income_columns": other_income_columns,
            "absent_inputs_left_unscaled": absent_inputs,
            "payroll_cap": cap,
            "beneficiary_person_rows": int(beneficiary_person_mask.sum()),
        },
        "profile": {
            "name": "demo-values",
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
        "economic_assumption": economic_assumption,
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
