from __future__ import annotations
# ruff: noqa: E402

import argparse
import importlib.util
import importlib.metadata as package_metadata
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.tob_baseline import (
    GENERATED_BASELINE_MANIFEST_PATH,
    validate_tob_baseline_manifest,
)

DASHBOARD_DATA = REPO / "dashboard" / "public" / "data"
DASHBOARD_RESULTS = DASHBOARD_DATA / "results.csv"
POST_OBBBA_TOB_BASELINE = REPO / "data" / "ssa_tob_baseline_75year.csv"
POST_OBBBA_TOB_BASELINE_MANIFEST = GENERATED_BASELINE_MANIFEST_PATH
SSA_ECONOMIC_PROJECTIONS = DASHBOARD_DATA / "ssa_economic_projections.csv"
HI_TAXABLE_PAYROLL = DASHBOARD_DATA / "hi_taxable_payroll.csv"

OUTPUT_BASELINE_AGGREGATES = DASHBOARD_DATA / "baseline_aggregates.csv"
OUTPUT_TOB_BASELINE_MANIFEST = DASHBOARD_DATA / "post_obbba_tob_baseline_manifest.json"
OUTPUT_INDEXED_PARAMETERS = DASHBOARD_DATA / "baseline_indexed_parameters.csv"
OUTPUT_INDEXED_PARAMETER_SUMMARY = (
    DASHBOARD_DATA / "baseline_indexed_parameter_summary.csv"
)
OUTPUT_INDEXING_GROWTH = DASHBOARD_DATA / "baseline_indexing_growth.csv"
OUTPUT_CALIBRATION_TARGETS = DASHBOARD_DATA / "baseline_calibration_targets.csv"
OUTPUT_CALIBRATION_DIAGNOSTICS = (
    DASHBOARD_DATA / "baseline_calibration_diagnostics.csv"
)
OUTPUT_POLICY_PARAMETERS = DASHBOARD_DATA / "baseline_policy_parameters.csv"
OUTPUT_REFORM_PARAMETERS = DASHBOARD_DATA / "baseline_reform_parameters.csv"
OUTPUT_METADATA = DASHBOARD_DATA / "baseline_assumptions_metadata.json"

EXPECTED_STANDARD_REFORMS = {f"option{i}" for i in range(1, 13)}
SPOTLIGHT_YEARS = [2026, 2034, 2035, 2036, 2050, 2075, 2100]
TOB_ALIGNMENT_TOLERANCE = 1e-6
MONEY_CONSTRAINTS = {
    "ss_total",
    "payroll_total",
    "oasdi_tob",
    "hi_tob",
    "income_guard_ordinary_nonpayroll_income",
    "income_guard_preferential_investment_income",
}
YEAR_RANGE = range(2026, 2101)
RECONCILIATION_CONSTRAINTS = {
    "ss_total",
    "payroll_total",
    "oasdi_tob",
    "hi_tob",
}
CONSTRAINT_LABELS = {
    "ss_total": "Social Security benefits",
    "payroll_total": "OASDI taxable payroll",
    "oasdi_tob": "OASDI TOB revenue",
    "hi_tob": "HI TOB revenue",
    "income_guard_ordinary_nonpayroll_income": "Ordinary non-payroll income guard",
    "income_guard_preferential_investment_income": "Preferential investment income guard",
}
CONSTRAINT_GROUPS = {
    "ss_total": "Benefits",
    "payroll_total": "Payroll",
    "oasdi_tob": "Taxation of benefits",
    "hi_tob": "Taxation of benefits",
    "income_guard_ordinary_nonpayroll_income": "Income support",
    "income_guard_preferential_investment_income": "Income support",
}
AGGREGATE_FALLBACK_TARGETS = {
    "payroll_total": "oasdi_taxable_payroll",
    "oasdi_tob": "tob_oasdi",
    "hi_tob": "tob_hi",
}
DIAGNOSTIC_LABELS = {
    "federal_income_tax_pct_gdp": "Federal income tax / GDP",
    "tob_total_pct_oasdi_payroll": "Total TOB / OASDI payroll",
    "tob_oasdi_pct_oasdi_payroll": "OASDI TOB / OASDI payroll",
    "tob_hi_pct_hi_payroll": "HI TOB / HI payroll",
    "oasdi_taxable_payroll_pct_gdp": "OASDI taxable payroll / GDP",
    "hi_taxable_payroll_pct_gdp": "HI taxable payroll / GDP",
    "post_obbba_tob_delta": "Post-OBBBA TOB delta",
    "tob_oasdi_gap_to_post_obbba_target": "OASDI TOB gap to post-OBBBA target",
    "tob_hi_gap_to_post_obbba_target": "HI TOB gap to post-OBBBA target",
    "tob_total_gap_to_post_obbba_target": "Total TOB gap to post-OBBBA target",
    "oasdi_gap_pct": "OASDI trust-fund gap",
    "hi_gap_pct": "HI trust-fund gap",
    "hi_cost_rate": "HI cost rate",
    "hi_taxable_payroll": "HI taxable payroll",
    "hi_expenditures": "HI expenditures",
    "max_constraint_pct_error": "Max hard-target error",
    "age_max_pct_error": "Max age-target error",
    "effective_sample_size": "Effective sample size",
    "positive_weight_count": "Positive household count",
    "negative_weight_pct": "Negative weight share",
    "top_10_weight_share_pct": "Top 10 weight share",
    "top_100_weight_share_pct": "Top 100 weight share",
    "validation_passed": "Calibration validation passed",
}
SUPPORT_DIAGNOSTIC_KEYS = [
    "max_constraint_pct_error",
    "age_max_pct_error",
    "effective_sample_size",
    "positive_weight_count",
    "positive_weight_pct",
    "negative_weight_count",
    "negative_weight_pct",
    "baseline_weight_sum",
    "calibrated_weight_sum",
    "top_10_weight_share_pct",
    "top_100_weight_share_pct",
    "ss_total_positive_contributor_count",
    "ss_total_contributor_effective_sample_size",
    "payroll_total_positive_contributor_count",
    "payroll_total_contributor_effective_sample_size",
    "oasdi_tob_positive_contributor_count",
    "oasdi_tob_contributor_effective_sample_size",
    "hi_tob_positive_contributor_count",
    "hi_tob_contributor_effective_sample_size",
    "top_100_ss_total_contribution_share_pct",
    "top_100_payroll_total_contribution_share_pct",
    "top_100_oasdi_tob_contribution_share_pct",
    "top_100_hi_tob_contribution_share_pct",
    "validation_passed",
]

PARAMETER_GROUP_PREFIXES = [
    ("gov.irs.social_security.taxability.threshold", "Social Security thresholds"),
    ("gov.irs.social_security.taxability.rate", "Social Security taxability rates"),
    ("gov.irs.social_security.taxability.combined_income", "Combined income rule"),
    ("gov.irs.deductions.senior_deduction", "Senior deduction"),
    ("gov.contrib.crfb.ss_credit", "CRFB Social Security credit"),
    ("gov.contrib.crfb.senior_deduction_extension", "Senior deduction extension"),
    ("gov.contrib.crfb.tax_employer_payroll_tax", "Employer payroll inclusion"),
    ("gov.ssa.revenue.oasdi_share_of_gross_ss", "Trust-fund allocation"),
    ("gov.simulation.labor_supply_responses", "Labor-supply response"),
]


def _ensure_import_paths(policyengine_us_path: Path | None = None) -> None:
    src_path = REPO / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    if policyengine_us_path is None:
        import os

        env_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
        policyengine_us_path = Path(env_path).expanduser() if env_path else None

    if policyengine_us_path is None:
        return

    policyengine_us_path = policyengine_us_path.expanduser().resolve()
    if not policyengine_us_path.exists():
        raise FileNotFoundError(f"policyengine-us path does not exist: {policyengine_us_path}")
    path_str = str(policyengine_us_path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _load_tax_assumption_module():
    from tax_assumption_loader import (
        TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        TRUSTEES_CORE_THRESHOLDS_MODULE,
        _canonical_tax_assumption_module,
        resolve_tax_assumption_module,
    )

    try:
        module = _canonical_tax_assumption_module(
            TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION
        )
        return Path(getattr(module, "__file__", TRUSTEES_CORE_THRESHOLDS_MODULE)), module
    except ModuleNotFoundError as error:
        import os

        if not os.environ.get("CRFB_TAX_ASSUMPTION_MODULE"):
            raise error
        module_path = resolve_tax_assumption_module()
        spec = importlib.util.spec_from_file_location("tax_assumptions", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load tax assumption module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module_path, module


def _installed_package_provenance(distribution_name: str) -> dict[str, Any]:
    distribution = package_metadata.distribution(distribution_name)
    direct_url_text = distribution.read_text("direct_url.json")
    direct_url_present = direct_url_text is not None
    direct_url = json.loads(direct_url_text) if direct_url_text else {}
    return {
        "distribution": distribution_name,
        "version": distribution.version,
        "source": "direct_url" if direct_url_present else "registry",
        "direct_url_present": direct_url_present,
        "editable": bool((direct_url.get("dir_info") or {}).get("editable")),
    }


def _iter_updatable_parameters(root) -> list:
    if hasattr(root, "get_descendants"):
        candidates = [root, *root.get_descendants()]
    else:
        candidates = [root]
    return [
        parameter
        for parameter in candidates
        if parameter.__class__.__name__ == "Parameter"
        and _as_uprating_name(getattr(parameter, "metadata", {}).get("uprating"))
        == "gov.irs.uprating"
    ]


def _module_iter_updatable_parameters(module, root) -> list:
    if hasattr(module, "iter_updatable_parameters"):
        try:
            return list(
                module.iter_updatable_parameters(
                    root,
                    uprating_parameter="gov.irs.uprating",
                )
            )
        except TypeError:
            return list(module.iter_updatable_parameters(root))
    if hasattr(module, "_iter_updatable_parameters"):
        try:
            return list(
                module._iter_updatable_parameters(
                    root,
                    uprating_parameter="gov.irs.uprating",
                )
            )
        except TypeError:
            return list(module._iter_updatable_parameters(root))
    return _iter_updatable_parameters(root)


def _as_uprating_name(uprating: Any) -> str:
    if isinstance(uprating, dict):
        return str(uprating.get("parameter", ""))
    return str(uprating or "")


def _rounding_label(uprating: Any) -> str:
    if not isinstance(uprating, dict):
        return ""
    rounding = uprating.get("rounding")
    if not isinstance(rounding, dict):
        return ""
    rounding_type = rounding.get("type", "")
    interval = rounding.get("interval", "")
    return f"{rounding_type} to {interval}"


def _get_parameter_by_name(parameters, name: str):
    current = parameters
    for part in name.split("."):
        current = getattr(current, part)
    return current


def _group_roots(parameters) -> list[tuple[str, str, Any]]:
    return [
        (
            "ordinary_income_brackets",
            "Ordinary income tax brackets",
            parameters.gov.irs.income.bracket.thresholds,
        ),
        (
            "standard_deduction",
            "Standard deduction",
            parameters.gov.irs.deductions.standard.amount,
        ),
        (
            "aged_blind_standard_deduction",
            "Aged or blind standard deduction addition",
            parameters.gov.irs.deductions.standard.aged_or_blind.amount,
        ),
        (
            "capital_gains_thresholds",
            "Capital-gains thresholds",
            parameters.gov.irs.capital_gains.thresholds,
        ),
        (
            "amt_bracket",
            "AMT bracket threshold",
            parameters.gov.irs.income.amt.brackets,
        ),
        (
            "amt_exemption",
            "AMT exemption",
            parameters.gov.irs.income.amt.exemption.amount,
        ),
        (
            "amt_exemption_phaseout",
            "AMT exemption phase-out",
            parameters.gov.irs.income.amt.exemption.phase_out.start,
        ),
        (
            "amt_separate_limit",
            "AMT separate filing limit",
            parameters.gov.irs.income.amt.exemption.separate_limit,
        ),
    ]


def _short_parameter_label(parameter_name: str) -> str:
    replacements = [
        ("gov.irs.income.bracket.thresholds.", "Ordinary bracket "),
        ("gov.irs.deductions.standard.amount.", "Standard deduction "),
        (
            "gov.irs.deductions.standard.aged_or_blind.amount.",
            "Aged/blind addition ",
        ),
        ("gov.irs.capital_gains.thresholds.", "Capital gains bracket "),
        ("gov.irs.income.amt.brackets[1].threshold", "AMT bracket threshold"),
        ("gov.irs.income.amt.exemption.amount.", "AMT exemption "),
        (
            "gov.irs.income.amt.exemption.phase_out.start.",
            "AMT phase-out start ",
        ),
        (
            "gov.irs.income.amt.exemption.separate_limit",
            "AMT separate filing limit",
        ),
    ]
    label = parameter_name
    for old, new in replacements:
        if label.startswith(old):
            label = label.replace(old, new, 1)
            break
        if label == old:
            label = new
            break
    return label.replace("_", " ")


def _load_post_obbba_tob_baseline() -> pd.DataFrame:
    manifest = validate_tob_baseline_manifest(
        POST_OBBBA_TOB_BASELINE,
        POST_OBBBA_TOB_BASELINE_MANIFEST,
    )
    tob = pd.read_csv(POST_OBBBA_TOB_BASELINE)
    required = {
        "year",
        "tob_oasdi_billions",
        "tob_hi_billions",
        "tob_total_billions",
        "current_law_oasdi_billions",
        "current_law_hi_billions",
        "current_law_total_billions",
        "oasdi_nominal_delta_billions",
        "hi_method",
        "oasdi_source",
        "hi_source",
        "current_law_source",
        "notes",
    }
    missing = required - set(tob.columns)
    if missing:
        raise ValueError(
            f"Missing post-OBBBA TOB baseline columns in {POST_OBBBA_TOB_BASELINE}: "
            f"{sorted(missing)}"
        )

    output = tob.rename(
        columns={
            "tob_oasdi_billions": "tob_oasdi",
            "tob_hi_billions": "tob_hi",
            "tob_total_billions": "tob_total",
            "current_law_oasdi_billions": "current_law_tob_oasdi",
            "current_law_hi_billions": "current_law_tob_hi",
            "current_law_total_billions": "current_law_tob_total",
        }
    )[
        [
            "year",
            "tob_oasdi",
            "tob_hi",
            "tob_total",
            "current_law_tob_oasdi",
            "current_law_tob_hi",
            "current_law_tob_total",
            "oasdi_nominal_delta_billions",
            "hi_method",
            "oasdi_source",
            "hi_source",
            "current_law_source",
            "notes",
        ]
    ]
    output["scenario_id"] = str(manifest["scenario_id"])
    output["baseline_kind"] = str(manifest["baseline_kind"])
    output["baseline_sha256"] = str(manifest["baseline_sha256"])
    output["baseline_manifest"] = str(POST_OBBBA_TOB_BASELINE_MANIFEST.relative_to(REPO))
    return output


def _add_static_tob_alignment_diagnostics(baseline: pd.DataFrame) -> pd.DataFrame:
    output = baseline.copy()
    targets = {
        "target_tob_oasdi": "tob_oasdi",
        "target_tob_hi": "tob_hi",
        "target_tob_total": "tob_total",
    }
    for target_col, source_col in targets.items():
        output[target_col] = output[source_col]

    checks = [
        ("release_tob_oasdi", "target_tob_oasdi", "tob_oasdi"),
        ("release_tob_hi", "target_tob_hi", "tob_hi"),
        ("release_tob_total", "target_tob_total", "tob_total"),
    ]
    aligned = pd.Series(True, index=output.index)
    for release_col, target_col, public_col in checks:
        gap_col = f"{public_col}_gap_to_post_obbba_target"
        output[gap_col] = output[release_col] - output[target_col]
        aligned &= output[gap_col].abs() <= TOB_ALIGNMENT_TOLERANCE
        output[public_col] = output[release_col]

    output["post_obbba_tob_target_alignment"] = aligned.map(
        {True: "aligned", False: "raw_microsim_differs_from_target"}
    )
    return output


def build_baseline_aggregates(tax_assumption_name: str) -> pd.DataFrame:
    results = pd.read_csv(DASHBOARD_RESULTS)
    static = results[results["scoring_type"].eq("static")].copy()
    standard = static[static["reform_name"].isin(EXPECTED_STANDARD_REFORMS)].copy()
    missing_reforms = EXPECTED_STANDARD_REFORMS - set(standard["reform_name"])
    if missing_reforms:
        raise ValueError(f"Missing standard static reforms in {DASHBOARD_RESULTS}: {missing_reforms}")

    baseline_cols = [
        "baseline_revenue",
        "baseline_tob_oasdi",
        "baseline_tob_medicare_hi",
        "baseline_tob_total",
    ]
    variation = standard.groupby("year")[baseline_cols].nunique().max().max()
    if variation != 1:
        raise ValueError("Baseline columns are not identical across standard reforms.")

    baseline = (
        standard.sort_values(["year", "reform_name"])
        .drop_duplicates("year")
        [["year", *baseline_cols]]
        .rename(
            columns={
                "baseline_revenue": "federal_income_tax",
                "baseline_tob_oasdi": "release_tob_oasdi",
                "baseline_tob_medicare_hi": "release_tob_hi",
                "baseline_tob_total": "release_tob_total",
            }
        )
        .reset_index(drop=True)
    )
    tob_baseline = _load_post_obbba_tob_baseline()
    baseline = baseline.merge(tob_baseline, on="year", how="left", validate="one_to_one")
    missing_target_years = baseline.loc[baseline["tob_oasdi"].isna(), "year"].tolist()
    if missing_target_years:
        raise ValueError(
            "Post-OBBBA TOB baseline is missing dashboard years: "
            + ", ".join(map(str, missing_target_years))
        )
    baseline = _add_static_tob_alignment_diagnostics(baseline)

    economic = pd.read_csv(SSA_ECONOMIC_PROJECTIONS).rename(
        columns={"taxable_payroll": "oasdi_taxable_payroll"}
    )
    hi_payroll = pd.read_csv(HI_TAXABLE_PAYROLL)
    baseline = baseline.merge(economic, on="year", how="left").merge(
        hi_payroll,
        on="year",
        how="left",
    )

    baseline["tob_total_pct_oasdi_payroll"] = (
        baseline["tob_total"] / baseline["oasdi_taxable_payroll"] * 100
    )
    baseline["tob_oasdi_pct_oasdi_payroll"] = (
        baseline["tob_oasdi"] / baseline["oasdi_taxable_payroll"] * 100
    )
    baseline["tob_hi_pct_hi_payroll"] = (
        baseline["tob_hi"] / baseline["hi_taxable_payroll"] * 100
    )
    baseline["federal_income_tax_pct_gdp"] = (
        baseline["federal_income_tax"] / baseline["gdp"] * 100
    )
    baseline["post_obbba_tob_delta"] = (
        baseline["tob_total"] - baseline["current_law_tob_total"]
    )
    baseline["calibration_target"] = (
        "Direct full-H5 microsimulation aggregate; generated post-OBBBA TOB "
        "baseline retained as a reference target"
    )
    baseline["calibration_quality"] = (
        "No post-hoc TOB calibration is applied to dashboard results. OASDI and "
        "HI target gaps are reported separately for review."
    )
    baseline["tax_assumption"] = tax_assumption_name
    return baseline


def _build_trustees_parameters(policyengine_us_path: Path | None = None):
    _ensure_import_paths(policyengine_us_path)

    from policyengine_us import Microsimulation
    from tax_assumption_loader import (
        TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        load_tax_assumption_reform_by_name,
    )

    reform = load_tax_assumption_reform_by_name(
        TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        start_year=2035,
        end_year=2100,
    )
    return Microsimulation(
        reform=reform,
        start_instant="2035-01-01",
    ).tax_benefit_system.parameters


def build_indexed_parameter_tables(
    module,
    parameters=None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parameters = parameters or _build_trustees_parameters()

    parameter_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group_id, group_label, root in _group_roots(parameters):
        for parameter in _module_iter_updatable_parameters(module, root):
            if parameter.name in seen:
                continue
            seen.add(parameter.name)
            metadata = getattr(parameter, "metadata", {})
            uprating = metadata.get("uprating")
            for year in range(2026, 2101):
                parameter_rows.append(
                    {
                        "parameter_group": group_id,
                        "parameter_group_label": group_label,
                        "parameter_name": parameter.name,
                        "parameter_label": _short_parameter_label(parameter.name),
                        "uprating_parameter": _as_uprating_name(uprating),
                        "rounding": _rounding_label(uprating),
                        "year": year,
                        "value": float(parameter(f"{year}-01-01")),
                    }
                )

    long = pd.DataFrame(parameter_rows)

    summary_rows: list[dict[str, Any]] = []
    for parameter_name, group in long.groupby("parameter_name", sort=False):
        first = group.iloc[0]
        values = {
            int(row.year): float(row.value)
            for row in group.itertuples(index=False)
            if int(row.year) in SPOTLIGHT_YEARS
        }
        value_2026 = values[2026]
        value_2100 = values[2100]
        summary_rows.append(
            {
                "parameter_group": first["parameter_group"],
                "parameter_group_label": first["parameter_group_label"],
                "parameter_name": parameter_name,
                "parameter_label": first["parameter_label"],
                "uprating_parameter": first["uprating_parameter"],
                "rounding": first["rounding"],
                **{f"value_{year}": values[year] for year in SPOTLIGHT_YEARS},
                "growth_2026_to_2100_pct": (
                    (value_2100 / value_2026 - 1) * 100 if value_2026 else 0
                ),
            }
        )

    summary = pd.DataFrame(summary_rows)

    growth_rows = []
    default_uprating = _get_parameter_by_name(parameters, "gov.irs.uprating")
    nawi = _get_parameter_by_name(parameters, "gov.ssa.nawi")
    for year in range(2026, 2101):
        if year < 2035:
            growth_multiplier = float(default_uprating(f"{year}-01-01")) / float(
                default_uprating(f"{year - 1}-01-01")
            )
            source = "PolicyEngine default IRS uprating"
        else:
            growth_multiplier = float(nawi(f"{year - 1}-01-01")) / float(
                nawi(f"{year - 2}-01-01")
            )
            source = "SSA Trustees average-wage growth"
        growth_rows.append(
            {
                "year": year,
                "indexing_source": source,
                "growth_rate_pct": (growth_multiplier - 1) * 100,
            }
        )
    growth = pd.DataFrame(growth_rows)

    return long, summary, growth


def _metadata_paths(metadata_roots: Iterable[Path] | None) -> list[Path]:
    paths: list[Path] = []
    for root in metadata_roots or []:
        root = Path(root).expanduser()
        if root.is_file() and root.name.endswith(".h5.metadata.json"):
            paths.append(root)
        elif root.exists():
            paths.extend(sorted(root.rglob("*.h5.metadata.json")))
    return sorted(set(paths))


def _load_metadata(path: Path) -> dict[str, Any] | None:
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("year") is None:
        try:
            metadata["year"] = int(path.name.split(".")[0])
        except ValueError:
            return None
    metadata["_metadata_path"] = str(path)
    return metadata


def _metadata_quality_score(metadata: dict[str, Any]) -> tuple[int, float]:
    audit = metadata.get("calibration_audit", {})
    quality = str(audit.get("calibration_quality", "")).lower()
    quality_rank = {"exact": 3, "aggregate": 2, "approximate": 1}.get(quality, 0)
    error = float(audit.get("max_constraint_pct_error") or float("inf"))
    return quality_rank, -error


def _best_metadata_by_year(metadata_roots: Iterable[Path] | None) -> dict[int, dict[str, Any]]:
    by_year: dict[int, dict[str, Any]] = {}
    for path in _metadata_paths(metadata_roots):
        metadata = _load_metadata(path)
        if not metadata:
            continue
        year = int(metadata["year"])
        current = by_year.get(year)
        if current is None or _metadata_quality_score(metadata) > _metadata_quality_score(
            current
        ):
            by_year[year] = metadata
    return by_year


def _money_scale(constraint_name: str) -> float:
    return 1e9 if constraint_name in MONEY_CONSTRAINTS else 1.0


def _target_row(
    *,
    year: int,
    constraint_name: str,
    target: float | None,
    achieved: float | None,
    error: float | None,
    pct_error: float | None,
    source: str,
    classification: str,
    scoring_contract: str,
    dataset_path: str = "",
    target_source_name: str = "",
    target_source_sha256: str = "",
    tax_assumption_name: str = "",
) -> dict[str, Any]:
    scale = _money_scale(constraint_name)
    return {
        "year": year,
        "dataset_path": dataset_path,
        "target_source_name": target_source_name,
        "target_source_sha256": target_source_sha256,
        "tax_assumption_name": tax_assumption_name,
        "constraint_name": constraint_name,
        "constraint_label": CONSTRAINT_LABELS.get(
            constraint_name,
            constraint_name.replace("_", " ").title(),
        ),
        "constraint_group": CONSTRAINT_GROUPS.get(constraint_name, "Other"),
        "constraint_classification": classification,
        "scoring_contract": scoring_contract,
        "source": source,
        "target": None if target is None else float(target) / scale,
        "achieved": None if achieved is None else float(achieved) / scale,
        "error": None if error is None else float(error) / scale,
        "pct_error": 0.0 if pct_error is None else float(pct_error),
        "used_in_year_runner_reconciliation": constraint_name
        in RECONCILIATION_CONSTRAINTS,
        "unit": "billions of nominal dollars"
        if constraint_name in MONEY_CONSTRAINTS
        else "raw",
    }


def build_calibration_targets(
    baseline: pd.DataFrame,
    *,
    metadata_roots: Iterable[Path] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for metadata in _best_metadata_by_year(metadata_roots).values():
        year = int(metadata["year"])
        audit = metadata.get("calibration_audit", {})
        constraints = audit.get("constraints", {})
        provenance = audit.get("constraint_provenance", {})
        target_source = metadata.get("target_source", {}) or {}
        tax_assumption = metadata.get("tax_assumption", {}) or {}
        for constraint_name, values in constraints.items():
            if not isinstance(values, dict):
                continue
            constraint_provenance = provenance.get(constraint_name, {})
            row = _target_row(
                year=year,
                constraint_name=constraint_name,
                target=values.get("target"),
                achieved=values.get("achieved"),
                error=values.get("error"),
                pct_error=values.get("pct_error"),
                source=str(constraint_provenance.get("source", "")),
                classification=str(constraint_provenance.get("classification", "")),
                scoring_contract=str(
                    constraint_provenance.get("scoring_contract", "")
                ),
                dataset_path=str(metadata.get("_metadata_path", "")),
                target_source_name=str(target_source.get("name", "")),
                target_source_sha256=str(target_source.get("sha256", "")),
                tax_assumption_name=str(tax_assumption.get("name", "")),
            )
            rows.append(row)
            seen.add((year, constraint_name))

    for row in baseline.itertuples(index=False):
        year = int(row.year)
        for constraint_name, column_name in AGGREGATE_FALLBACK_TARGETS.items():
            if (year, constraint_name) in seen:
                continue
            value = float(getattr(row, column_name))
            rows.append(
                _target_row(
                    year=year,
                    constraint_name=constraint_name,
                    target=value * 1e9,
                    achieved=value * 1e9,
                    error=0.0,
                    pct_error=0.0,
                    source="dashboard_public_baseline_artifact",
                    classification="hard",
                    scoring_contract=(
                        "published aggregate target; detailed H5 calibration "
                        "metadata not available in this artifact"
                    ),
                    target_source_name=str(getattr(row, "scenario_id", "")),
                    target_source_sha256=str(getattr(row, "baseline_sha256", "")),
                    tax_assumption_name=str(getattr(row, "tax_assumption", "")),
                )
            )

    return pd.DataFrame(rows).sort_values(["year", "constraint_group", "constraint_name"])


def _diagnostic_row(
    *,
    year: int,
    diagnostic_id: str,
    value: Any,
    group: str,
    unit: str,
    source: str,
    dataset_path: str = "",
    status: str = "",
) -> dict[str, Any]:
    return {
        "year": year,
        "diagnostic_id": diagnostic_id,
        "diagnostic_label": DIAGNOSTIC_LABELS.get(
            diagnostic_id,
            diagnostic_id.replace("_", " ").title(),
        ),
        "diagnostic_group": group,
        "value": value,
        "unit": unit,
        "source": source,
        "dataset_path": dataset_path,
        "status": status,
    }


def build_calibration_diagnostics(
    baseline: pd.DataFrame,
    *,
    metadata_roots: Iterable[Path] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in baseline.itertuples(index=False):
        year = int(row.year)
        diagnostics = {
            "federal_income_tax_pct_gdp": row.federal_income_tax_pct_gdp,
            "tob_total_pct_oasdi_payroll": row.tob_total_pct_oasdi_payroll,
            "tob_oasdi_pct_oasdi_payroll": row.tob_oasdi_pct_oasdi_payroll,
            "tob_hi_pct_hi_payroll": row.tob_hi_pct_hi_payroll,
            "oasdi_taxable_payroll_pct_gdp": row.oasdi_taxable_payroll / row.gdp * 100,
            "hi_taxable_payroll_pct_gdp": row.hi_taxable_payroll / row.gdp * 100,
            "post_obbba_tob_delta": row.post_obbba_tob_delta,
            "tob_oasdi_gap_to_post_obbba_target": (
                row.tob_oasdi_gap_to_post_obbba_target
            ),
            "tob_hi_gap_to_post_obbba_target": (
                row.tob_hi_gap_to_post_obbba_target
            ),
            "tob_total_gap_to_post_obbba_target": (
                row.tob_total_gap_to_post_obbba_target
            ),
        }
        for diagnostic_id, value in diagnostics.items():
            rows.append(
                _diagnostic_row(
                    year=year,
                    diagnostic_id=diagnostic_id,
                    value=float(value),
                    group="Published baseline aggregate",
                    unit=(
                        "percent"
                        if diagnostic_id.endswith("_pct_gdp")
                        or "_pct_" in diagnostic_id
                        else "billions of nominal dollars"
                    ),
                    source="dashboard/public/data/baseline_aggregates.csv",
                )
            )

    trust_fund_gaps = REPO / "data" / "trust_fund_gaps.csv"
    if trust_fund_gaps.exists():
        gaps = pd.read_csv(trust_fund_gaps)
        for row in gaps.itertuples(index=False):
            if int(row.year) not in YEAR_RANGE:
                continue
            for diagnostic_id in [
                "oasdi_gap_pct",
                "hi_gap_pct",
                "hi_cost_rate",
            ]:
                if hasattr(row, diagnostic_id):
                    rows.append(
                        _diagnostic_row(
                            year=int(row.year),
                            diagnostic_id=diagnostic_id,
                            value=float(getattr(row, diagnostic_id)),
                            group="Trustees trust-fund diagnostic",
                            unit="percent",
                            source="data/trust_fund_gaps.csv",
                        )
                    )

    hi_expenditures = REPO / "data" / "hi_expenditures_tr2025.csv"
    if hi_expenditures.exists():
        hi = pd.read_csv(hi_expenditures)
        for row in hi.itertuples(index=False):
            if int(row.year) not in YEAR_RANGE:
                continue
            for diagnostic_id in ["hi_taxable_payroll", "hi_expenditures"]:
                if hasattr(row, diagnostic_id):
                    rows.append(
                        _diagnostic_row(
                            year=int(row.year),
                            diagnostic_id=diagnostic_id,
                            value=float(getattr(row, diagnostic_id)) / 1e9,
                            group="HI Trustees diagnostic",
                            unit="billions of nominal dollars",
                            source="data/hi_expenditures_tr2025.csv",
                        )
                    )

    for metadata in _best_metadata_by_year(metadata_roots).values():
        year = int(metadata["year"])
        audit = metadata.get("calibration_audit", {})
        dataset_path = str(metadata.get("_metadata_path", ""))
        for diagnostic_id in SUPPORT_DIAGNOSTIC_KEYS:
            if diagnostic_id not in audit:
                continue
            value = audit[diagnostic_id]
            if isinstance(value, bool):
                value = 1 if value else 0
                unit = "boolean"
            else:
                unit = (
                    "percent"
                    if diagnostic_id.endswith("_pct")
                    or "share_pct" in diagnostic_id
                    or "pct_error" in diagnostic_id
                    else "raw"
                )
            rows.append(
                _diagnostic_row(
                    year=year,
                    diagnostic_id=diagnostic_id,
                    value=value,
                    group="H5 calibration support",
                    unit=unit,
                    source="projected dataset metadata",
                    dataset_path=dataset_path,
                    status=str(audit.get("calibration_quality", "")),
                )
            )

    return pd.DataFrame(rows).sort_values(["diagnostic_group", "diagnostic_id", "year"])


def _parameter_group(parameter_name: str) -> str:
    for prefix, label in PARAMETER_GROUP_PREFIXES:
        if parameter_name.startswith(prefix):
            return label
    return "Other"


def _policy_role(parameter_name: str) -> str:
    if parameter_name.startswith("gov.simulation.labor_supply_responses"):
        return "behavioral_scoring_elasticity"
    if "social_security.taxability" in parameter_name:
        return "social_security_taxability"
    if "senior_deduction" in parameter_name:
        return "senior_deduction"
    if "ss_credit" in parameter_name:
        return "social_security_credit"
    if "tax_employer_payroll_tax" in parameter_name:
        return "employer_payroll_inclusion"
    if "oasdi_share_of_gross_ss" in parameter_name:
        return "trust_fund_allocation"
    return "policy_parameter"


def _period_matches_year(period: str, year: int) -> bool:
    if period == str(year):
        return True
    if period.startswith(str(year)) and "." not in period:
        return True
    if "." not in period:
        try:
            return int(period) == year
        except ValueError:
            return False
    start, _, end = period.partition(".")
    try:
        start_year = int(start[:4])
        end_year = int(end[:4])
    except ValueError:
        return False
    return start_year <= year <= end_year


def _schedule_value_for_year(schedule: dict[str, Any], year: int) -> Any:
    matched_value = None
    matched_start = -1
    for period, value in schedule.items():
        if not _period_matches_year(str(period), year):
            continue
        try:
            start_year = int(str(period)[:4])
        except ValueError:
            start_year = year
        if start_year >= matched_start:
            matched_start = start_year
            matched_value = value
    return matched_value


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if value is None:
        return "missing"
    return "string"


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parameter_value(parameters, parameter_name: str, year: int) -> Any:
    try:
        parameter = _get_parameter_by_name(parameters, parameter_name)
        return parameter(f"{year}-01-01")
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _static_reform_dict_functions():
    from src import reforms

    return {
        f"option{index}": getattr(reforms, f"get_option{index}_dict")
        for index in range(1, 13)
    }


def _conventional_reform_dict_functions():
    from src import reforms

    return {
        f"option{index}": getattr(reforms, f"get_option{index}_conventional_dict")
        for index in range(1, 13)
    }


def build_reform_parameter_tables(parameters) -> tuple[pd.DataFrame, pd.DataFrame]:
    reform_rows: list[dict[str, Any]] = []
    touched: dict[str, dict[str, set[str]]] = {}
    for scoring_type, functions in [
        ("static", _static_reform_dict_functions()),
        ("behavioral", _conventional_reform_dict_functions()),
    ]:
        for reform_name, function in functions.items():
            reform_dict = function()
            for parameter_name, schedule in reform_dict.items():
                if not isinstance(schedule, dict):
                    continue
                touched.setdefault(parameter_name, {"reforms": set(), "scoring": set()})
                touched[parameter_name]["reforms"].add(reform_name)
                touched[parameter_name]["scoring"].add(scoring_type)
                for period, value in schedule.items():
                    reform_rows.append(
                        {
                            "reform_name": reform_name,
                            "scoring_type": scoring_type,
                            "parameter_name": parameter_name,
                            "parameter_label": _short_parameter_label(parameter_name),
                            "parameter_group": _parameter_group(parameter_name),
                            "period": period,
                            "value": value,
                            "numeric_value": _numeric_value(value),
                            "value_type": _value_type(value),
                            "policy_role": _policy_role(parameter_name),
                            "affects_baseline": False,
                        }
                    )

    baseline_rows: list[dict[str, Any]] = []
    for parameter_name, metadata in sorted(touched.items()):
        for year in YEAR_RANGE:
            baseline_value = _parameter_value(parameters, parameter_name, year)
            baseline_rows.append(
                {
                    "year": year,
                    "parameter_name": parameter_name,
                    "parameter_label": _short_parameter_label(parameter_name),
                    "parameter_group": _parameter_group(parameter_name),
                    "baseline_value": baseline_value,
                    "baseline_numeric_value": _numeric_value(baseline_value),
                    "baseline_value_type": _value_type(baseline_value),
                    "touched_by_reforms": ",".join(sorted(metadata["reforms"])),
                    "touched_by_scoring_types": ",".join(sorted(metadata["scoring"])),
                    "policy_role": _policy_role(parameter_name),
                }
            )

    baseline_parameters = pd.DataFrame(baseline_rows).sort_values(
        ["parameter_group", "parameter_name", "year"]
    )
    reform_parameters = pd.DataFrame(reform_rows).sort_values(
        ["scoring_type", "reform_name", "parameter_group", "parameter_name", "period"]
    )
    return baseline_parameters, reform_parameters


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build public dashboard baseline assumption and audit artifacts."
    )
    parser.add_argument(
        "--metadata-root",
        type=Path,
        action="append",
        default=[],
        help=(
            "Projected dataset directory or .h5.metadata.json file to include in "
            "calibration target/support exports. May be passed more than once."
        ),
    )
    parser.add_argument(
        "--policyengine-us-path",
        type=Path,
        default=None,
        help=(
            "Optional explicit policyengine-us checkout/runtime path. If omitted, "
            "the installed policyengine-us package is used."
        ),
    )
    return parser.parse_args(argv)


def write_outputs(
    metadata_roots: Iterable[Path] | None = None,
    *,
    policyengine_us_path: Path | None = None,
) -> None:
    _ensure_import_paths(policyengine_us_path)
    module_path, module = _load_tax_assumption_module()
    policyengine_packages = {
        package: _installed_package_provenance(package)
        for package in ("policyengine", "policyengine-us", "policyengine-core")
    }
    assumption = getattr(module, "TRUSTEES_CORE_THRESHOLD_ASSUMPTION", {})
    tax_assumption_name = assumption.get("name", "trustees-2025-core-thresholds-v1")

    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)

    parameters = _build_trustees_parameters(policyengine_us_path)
    baseline = build_baseline_aggregates(tax_assumption_name)
    indexed_long, indexed_summary, growth = build_indexed_parameter_tables(
        module,
        parameters,
    )
    calibration_targets = build_calibration_targets(
        baseline,
        metadata_roots=metadata_roots,
    )
    calibration_diagnostics = build_calibration_diagnostics(
        baseline,
        metadata_roots=metadata_roots,
    )
    policy_parameters, reform_parameters = build_reform_parameter_tables(parameters)
    tob_manifest = validate_tob_baseline_manifest(
        POST_OBBBA_TOB_BASELINE,
        POST_OBBBA_TOB_BASELINE_MANIFEST,
    )

    baseline.to_csv(OUTPUT_BASELINE_AGGREGATES, index=False, float_format="%.9f")
    shutil.copy2(POST_OBBBA_TOB_BASELINE_MANIFEST, OUTPUT_TOB_BASELINE_MANIFEST)
    indexed_long.to_csv(OUTPUT_INDEXED_PARAMETERS, index=False, float_format="%.9f")
    indexed_summary.to_csv(
        OUTPUT_INDEXED_PARAMETER_SUMMARY,
        index=False,
        float_format="%.9f",
    )
    growth.to_csv(OUTPUT_INDEXING_GROWTH, index=False, float_format="%.9f")
    calibration_targets.to_csv(
        OUTPUT_CALIBRATION_TARGETS,
        index=False,
        float_format="%.9f",
    )
    calibration_diagnostics.to_csv(
        OUTPUT_CALIBRATION_DIAGNOSTICS,
        index=False,
        float_format="%.9f",
    )
    policy_parameters.to_csv(
        OUTPUT_POLICY_PARAMETERS,
        index=False,
        float_format="%.9f",
    )
    reform_parameters.to_csv(
        OUTPUT_REFORM_PARAMETERS,
        index=False,
        float_format="%.9f",
    )

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dashboard_results": str(DASHBOARD_RESULTS.relative_to(REPO)),
        "source_post_obbba_tob_baseline": str(POST_OBBBA_TOB_BASELINE.relative_to(REPO)),
        "source_post_obbba_tob_baseline_manifest": str(
            POST_OBBBA_TOB_BASELINE_MANIFEST.relative_to(REPO)
        ),
        "public_post_obbba_tob_baseline_manifest": str(
            OUTPUT_TOB_BASELINE_MANIFEST.relative_to(REPO)
        ),
        "post_obbba_tob_baseline_sha256": tob_manifest["baseline_sha256"],
        "scenario_id": tob_manifest["scenario_id"],
        "baseline_kind": tob_manifest["baseline_kind"],
        "not_law": tob_manifest["not_law"],
        "law_mode": tob_manifest["law_mode"],
        "hi_bridge_method": tob_manifest["bridge_methods"]["hi_method"],
        "source_economic_projections": str(SSA_ECONOMIC_PROJECTIONS.relative_to(REPO)),
        "source_hi_taxable_payroll": str(HI_TAXABLE_PAYROLL.relative_to(REPO)),
        "tax_assumption_module": str(module_path),
        "policyengine_version": policyengine_packages["policyengine"]["version"],
        "policyengine_us_version": policyengine_packages["policyengine-us"]["version"],
        "policyengine_core_version": policyengine_packages["policyengine-core"][
            "version"
        ],
        "policyengine_packages": policyengine_packages,
        "tax_assumption": assumption,
        "indexed_parameter_count": int(indexed_summary.shape[0]),
        "indexed_parameter_groups": sorted(
            indexed_summary["parameter_group_label"].unique().tolist()
        ),
        "calibration_target_count": int(calibration_targets.shape[0]),
        "calibration_diagnostic_count": int(calibration_diagnostics.shape[0]),
        "policy_parameter_count": int(
            policy_parameters["parameter_name"].nunique()
        ),
        "reform_parameter_count": int(reform_parameters.shape[0]),
        "calibration_metadata_roots": [
            str(Path(path).expanduser()) for path in metadata_roots or []
        ],
        "baseline_years": [
            int(baseline["year"].min()),
            int(baseline["year"].max()),
        ],
        "note": (
            "Income-tax and TOB baseline aggregates are read directly from the dashboard "
            "static release artifact. The generated post-OBBBA TOB baseline is retained "
            "as a reference target and exposed through gap diagnostics; it is not applied "
            "to results.csv. Indexed parameter paths are generated by applying the active "
            "Trustees core-threshold tax-assumption reform."
        ),
    }
    OUTPUT_METADATA.write_text(json.dumps(metadata, indent=2) + "\n")

    print(f"Wrote {OUTPUT_BASELINE_AGGREGATES} ({baseline.shape[0]} rows)")
    print(f"Wrote {OUTPUT_TOB_BASELINE_MANIFEST}")
    print(f"Wrote {OUTPUT_INDEXED_PARAMETERS} ({indexed_long.shape[0]} rows)")
    print(f"Wrote {OUTPUT_INDEXED_PARAMETER_SUMMARY} ({indexed_summary.shape[0]} rows)")
    print(f"Wrote {OUTPUT_INDEXING_GROWTH} ({growth.shape[0]} rows)")
    print(f"Wrote {OUTPUT_CALIBRATION_TARGETS} ({calibration_targets.shape[0]} rows)")
    print(
        f"Wrote {OUTPUT_CALIBRATION_DIAGNOSTICS} "
        f"({calibration_diagnostics.shape[0]} rows)"
    )
    print(f"Wrote {OUTPUT_POLICY_PARAMETERS} ({policy_parameters.shape[0]} rows)")
    print(f"Wrote {OUTPUT_REFORM_PARAMETERS} ({reform_parameters.shape[0]} rows)")
    print(f"Wrote {OUTPUT_METADATA}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_outputs(args.metadata_root, policyengine_us_path=args.policyengine_us_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
