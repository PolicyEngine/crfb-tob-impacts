import ast
import json
from pathlib import Path
import subprocess

import pandas as pd
import pytest
from packaging.version import Version

from src.tob_baseline import (
    GENERATED_BASELINE_MANIFEST_PATH,
    GENERATED_BASELINE_PATH,
    validate_tob_baseline_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "public" / "data"
DASHBOARD_OUT = REPO_ROOT / "dashboard" / "out" / "data"
VERCEL_SITE = REPO_ROOT / ".vercel-site"
RESULTS_METADATA = REPO_ROOT / "results.csv.metadata.json"
DASHBOARD_RESULTS = DASHBOARD_DATA / "results.csv"
DASHBOARD_BASELINE_METADATA = DASHBOARD_DATA / "baseline_assumptions_metadata.json"
PUBLIC_BASELINE_MANIFEST = DASHBOARD_DATA / "post_obbba_tob_baseline_manifest.json"
MIN_WAGE_INDEXED_THRESHOLD_GROWTH_PCT = 800.0
CORE_WAGE_INDEXED_TAX_PARAMETERS = {
    "gov.irs.deductions.standard.amount.SINGLE": "standard deduction",
    "gov.irs.income.bracket.thresholds.1.SINGLE": "first ordinary bracket",
    "gov.irs.income.bracket.thresholds.6.SINGLE": "top ordinary bracket",
    "gov.irs.income.amt.exemption.amount.SINGLE": "AMT exemption",
}
RELEASE_RESULT_ARTIFACTS = [
    REPO_ROOT / "results.csv",
    DASHBOARD_RESULTS,
]
ALLOWED_CSV_ARTIFACTS = {
    "dashboard/public/data/baseline_aggregates.csv",
    "dashboard/public/data/baseline_calibration_diagnostics.csv",
    "dashboard/public/data/baseline_calibration_targets.csv",
    "dashboard/public/data/baseline_indexed_parameter_summary.csv",
    "dashboard/public/data/baseline_indexed_parameters.csv",
    "dashboard/public/data/baseline_indexing_growth.csv",
    "dashboard/public/data/baseline_policy_parameters.csv",
    "dashboard/public/data/baseline_reform_parameters.csv",
    "dashboard/public/data/balanced_fix_results.csv",
    "dashboard/public/data/hi_taxable_payroll.csv",
    "dashboard/public/data/live_baseline_results.csv",
    "dashboard/public/data/live_reform_status.csv",
    "dashboard/public/data/results.csv",
    "dashboard/public/data/ssa_economic_projections.csv",
    "dashboard/public/data/effective_interest_rates.csv",
    "data/sources/tr2026/hi_effective_interest_rates_tr2026_iv_a4.csv",
    "dashboard/public/data/v2_baseline_diagnostics.csv",
    "data/SSPopJul_TR2024.csv",
    "data/SSPopJul_TR2026_interim.csv",
    "data/hi_expenditures_tr2025.csv",
    "data/hi_expenditures_tr2026.csv",
    "data/oasdi_oact_20250805_nominal_delta.csv",
    "data/social_security_aux_tr2025.csv",
    "data/social_security_aux_tr2026.csv",
    "data/sources/tr2026/HI Cost and Income Rates.csv",
    "data/sources/tr2026/Medicare Sources of Non-Interest Income as a Percentage of Total Income and as a Percentage of Gross Domestic Product.csv",
    "data/ssa_economic_projections.csv",
    "data/ssa_tob_baseline_75year.csv",
    "data/tob_current_law_tr2025.csv",
    "data/trust_fund_gaps.csv",
    "results.csv",
    "results/modal_runs_production/balanced_fix_results.csv",
    "results/modal_runs_production/behavioral_endpoint_cells.csv",
    "results/modal_runs_production/static_cells.csv",
}
BASELINE_AUDIT_PUBLIC_FILES = [
    DASHBOARD_DATA / "baseline_aggregates.csv",
    DASHBOARD_DATA / "baseline_indexed_parameters.csv",
    DASHBOARD_DATA / "baseline_indexed_parameter_summary.csv",
    DASHBOARD_DATA / "baseline_indexing_growth.csv",
    DASHBOARD_DATA / "baseline_calibration_targets.csv",
    DASHBOARD_DATA / "baseline_calibration_diagnostics.csv",
    DASHBOARD_DATA / "baseline_policy_parameters.csv",
    DASHBOARD_DATA / "baseline_reform_parameters.csv",
    DASHBOARD_DATA / "baseline_assumptions_metadata.json",
    PUBLIC_BASELINE_MANIFEST,
]


def load_post_obbba_manifest() -> dict:
    return validate_tob_baseline_manifest(
        GENERATED_BASELINE_PATH,
        GENERATED_BASELINE_MANIFEST_PATH,
    )


def load_dashboard_results(scoring_type: str | None = None) -> pd.DataFrame:
    results = pd.read_csv(DASHBOARD_RESULTS)
    if scoring_type is None:
        return results
    return results[results["scoring_type"].eq(scoring_type)].reset_index(drop=True)


def load_post_obbba_tob_target() -> pd.DataFrame:
    return pd.read_csv(REPO_ROOT / "data" / "ssa_tob_baseline_75year.csv").rename(
        columns={
            "tob_oasdi_billions": "target_tob_oasdi",
            "tob_hi_billions": "target_tob_medicare_hi",
            "tob_total_billions": "target_tob_total",
        }
    )[["year", "target_tob_oasdi", "target_tob_medicare_hi", "target_tob_total"]]


def assert_post_obbba_tob_target_is_diagnostic_only(results: pd.DataFrame) -> None:
    baseline = load_post_obbba_tob_target()
    merged = results.merge(baseline, on="year", how="left", validate="many_to_one")
    missing_years = merged.loc[
        merged["target_tob_oasdi"].isna(),
        "year",
    ].drop_duplicates()
    assert missing_years.empty

    current_law_reforms = {f"option{i}" for i in range(1, 13)}
    reform = merged["reform_name"].astype(str)
    mask = reform.isin(current_law_reforms)
    comparisons = [
        ("baseline_tob_oasdi", "target_tob_oasdi"),
        ("baseline_tob_medicare_hi", "target_tob_medicare_hi"),
        ("baseline_tob_total", "target_tob_total"),
    ]
    saw_target_gap = False
    for result_col, target_col in comparisons:
        diff = (merged.loc[mask, result_col] - merged.loc[mask, target_col]).abs()
        saw_target_gap |= float(diff.max()) > 1e-6
    assert saw_target_gap


def assert_release_artifact_matches_raw_full_h5(path: Path) -> None:
    results = pd.read_csv(path)
    raw = pd.read_csv(RESULTS / "modal_runs_production" / "static_cells.csv")
    raw["baseline_revenue_raw_billions"] = raw["baseline_revenue"] / 1e9
    raw["baseline_tob_total_raw_billions"] = raw["baseline_tob_total"] / 1e9
    exact = results[results["full_h5_result_type"].eq("exact_full_h5")].merge(
        raw[
            [
                "reform_name",
                "year",
                "baseline_revenue_raw_billions",
                "baseline_tob_total_raw_billions",
            ]
        ],
        on=["reform_name", "year"],
        how="inner",
        validate="one_to_one",
    )
    assert len(exact) == len(raw)
    assert (
        exact["baseline_revenue"] - exact["baseline_revenue_raw_billions"]
    ).abs().max() < 1e-6
    assert (
        exact["baseline_tob_total"] - exact["baseline_tob_total_raw_billions"]
    ).abs().max() < 1e-6


def test_budget_window_infill_exact_rows_are_published():
    static = load_dashboard_results("static")
    exact = static[static["full_h5_result_type"].eq("exact_full_h5")]

    common_infill_years = {2028, 2029}
    for reform_name in sorted(static["reform_name"].unique()):
        reform_exact_years = set(
            exact.loc[exact["reform_name"].eq(reform_name), "year"].astype(int)
        )
        assert common_infill_years <= reform_exact_years

    option6_exact_years = set(
        exact.loc[exact["reform_name"].eq("option6"), "year"].astype(int)
    )
    assert {2032, 2033} <= option6_exact_years

    option7_2029 = exact[
        exact["reform_name"].eq("option7") & exact["year"].eq(2029)
    ].iloc[0]
    assert abs(option7_2029["revenue_impact"]) < 1e-5


def assert_income_tax_baseline_is_direct_microsim(path: Path) -> None:
    assert_release_artifact_matches_raw_full_h5(path)


def test_release_artifacts_keep_post_obbba_tob_as_diagnostic_target_only():
    dashboard_static = load_dashboard_results("static")
    dashboard_behavioral = load_dashboard_results("behavioral")

    assert load_dashboard_results("conventional").empty
    for results in [dashboard_static, dashboard_behavioral]:
        assert_post_obbba_tob_target_is_diagnostic_only(results)


def test_release_baseline_income_tax_comes_from_raw_full_h5():
    baseline = pd.read_csv(DASHBOARD_DATA / "baseline_aggregates.csv")
    static = load_dashboard_results("static")
    option1 = static[static["reform_name"].eq("option1")][["year", "baseline_revenue"]]
    merged = baseline.merge(option1, on="year", validate="one_to_one")

    assert (
        merged["federal_income_tax"] - merged["baseline_revenue"]
    ).abs().max() < 1e-6
    # Federal income tax sits in a realistic band of GDP on the populace
    # baseline (roughly 8-11%); v1's 25%+ reflected its over-calibration.
    income_tax_pct_gdp = baseline["federal_income_tax_pct_gdp"]
    assert float(income_tax_pct_gdp.max()) < 15.0
    assert float(income_tax_pct_gdp.min()) > 7.0

    target = load_post_obbba_tob_target().rename(
        columns={"target_tob_total": "target_tob_total_from_csv"}
    )
    baseline = baseline.merge(
        target[["year", "target_tob_total_from_csv"]],
        on="year",
        validate="one_to_one",
    )
    assert (
        baseline["target_tob_total"] - baseline["target_tob_total_from_csv"]
    ).abs().max() < 1e-6
    assert (
        baseline["tob_total"]
        - baseline["target_tob_total"]
        - baseline["tob_total_gap_to_post_obbba_target"]
    ).abs().max() < 1e-6

    for path in RELEASE_RESULT_ARTIFACTS:
        assert_income_tax_baseline_is_direct_microsim(path)


def test_release_baseline_aggregates_use_public_hi_payroll_denominator():
    baseline = pd.read_csv(DASHBOARD_DATA / "baseline_aggregates.csv")
    hi_payroll = pd.read_csv(DASHBOARD_DATA / "hi_taxable_payroll.csv")
    diagnostics = pd.read_csv(DASHBOARD_DATA / "baseline_calibration_diagnostics.csv")

    merged = baseline[["year", "hi_taxable_payroll"]].merge(
        hi_payroll,
        on="year",
        suffixes=("_baseline", "_public"),
        validate="one_to_one",
    )
    assert (
        merged["hi_taxable_payroll_baseline"] - merged["hi_taxable_payroll_public"]
    ).abs().max() < 1e-6

    expected_pct = baseline["tob_hi"] / baseline["hi_taxable_payroll"] * 100
    diagnostic_pct = diagnostics[
        diagnostics["diagnostic_id"].eq("tob_hi_pct_hi_payroll")
    ][["year", "value"]]
    checked = (
        baseline[["year"]]
        .assign(expected_pct=expected_pct)
        .merge(
            diagnostic_pct,
            on="year",
            validate="one_to_one",
        )
    )
    assert (checked["expected_pct"] - checked["value"]).abs().max() < 1e-9


def test_csv_release_surface_contains_only_current_full_h5_artifacts_and_inputs():
    roots = [
        REPO_ROOT / "data",
        REPO_ROOT / "dashboard" / "public" / "data",
        REPO_ROOT / "results",
    ]
    tracked_csvs = subprocess.run(
        ["git", "ls-files", "*.csv"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    discovered = {
        path
        for path in tracked_csvs
        if (REPO_ROOT / path).exists()
        and (
            Path(path).parent == Path(".")
            or any((REPO_ROOT / path).is_relative_to(root) for root in roots)
        )
    }

    stale = discovered - ALLOWED_CSV_ARTIFACTS
    missing = ALLOWED_CSV_ARTIFACTS - discovered
    assert not stale, f"Unexpected stale CSV artifacts: {sorted(stale)}"
    assert not missing, f"Expected current CSV artifacts missing: {sorted(missing)}"


def test_current_public_results_have_current_release_provenance():
    current_results = [
        DASHBOARD_RESULTS,
        REPO_ROOT / "results.csv",
    ]
    forbidden_fragments = [
        "20260522",
        "5a35713",
        "selected_panel",
        "existing_selected_panel_results",
    ]

    for path in current_results:
        text = path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            assert fragment not in text, f"{fragment!r} leaked into {path}"

    results = load_dashboard_results()
    assert set(results["baseline_source"].dropna()) == {
        "v2pop_tr2026_baseline_h5",
        "v2pop_tr2026_static_full_h5_display",
    }
    behavioral = results[results["scoring_type"].eq("behavioral")]
    interpolated = behavioral[
        behavioral["full_h5_result_type"].eq(
            "linear_interpolation_between_behavioral_endpoint_ratios"
        )
    ]
    assert set(interpolated["run_prefix"]) == {
        "behavioral_endpoint_ratio_interpolation_20260612"
    }


def test_balanced_fix_public_results_are_additive_and_reconciled():
    public_path = DASHBOARD_DATA / "balanced_fix_results.csv"
    production_path = RESULTS / "modal_runs_production" / "balanced_fix_results.csv"

    assert public_path.exists()
    assert production_path.exists()
    assert public_path.read_text(encoding="utf-8") == production_path.read_text(
        encoding="utf-8"
    )

    balanced = pd.read_csv(public_path)
    current = load_dashboard_results()

    assert "ss_solvent" not in set(current.get("baseline_scenario", []))
    assert set(balanced["baseline_scenario"]) == {"ss_solvent"}
    assert set(balanced["reform_name"]) == {
        "option1",
        "option2",
        "option8",
        "option12",
    }
    assert set(balanced["scoring_type"]) == {"static"}

    by_reform = balanced.groupby("reform_name")["year"].agg(["min", "max", "count"])
    assert by_reform["min"].eq(2035).all()
    assert by_reform["max"].eq(2100).all()
    assert by_reform["count"].eq(66).all()

    exact = balanced[
        balanced["balanced_fix_result_type"].eq("exact_solvent_baseline_full_h5")
    ]
    assert set(exact["year"]) == {2035, 2050, 2065, 2075, 2100}
    assert exact.groupby("reform_name")["year"].nunique().eq(5).all()

    split_total = (
        balanced["solvent_oasdi_impact"]
        + balanced["solvent_medicare_hi_impact"]
        + balanced["solvent_general_fund_impact"]
    )
    assert (split_total - balanced["revenue_impact"]).abs().max() < 1e-8


def test_dashboard_exposes_balanced_fix_as_baseline_scenario_not_allocation_mode():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    data_loader = (
        REPO_ROOT / "dashboard" / "src" / "lib" / "dashboard-data.ts"
    ).read_text(encoding="utf-8")

    assert "Baseline scenario" in shell
    assert '"ssSolvent"' in shell
    assert 'baselineScenario === "currentLaw"' in shell
    assert "type BaselineScenario" in data_loader
    assert '"/data/balanced_fix_results.csv"' in data_loader
    assert "solvent_general_fund_impact" in data_loader


def test_current_publication_scripts_do_not_default_to_legacy_20260522_inputs():
    guarded_scripts = [
        REPO_ROOT / "scripts" / "publish_full_h5_static_dashboard_results.py",
        REPO_ROOT / "scripts" / "publish_behavioral_endpoint_dashboard_results.py",
        REPO_ROOT / "scripts" / "publish_dashboard_results.py",
        REPO_ROOT / "scripts" / "build_release_package.py",
    ]
    for path in guarded_scripts:
        text = path.read_text(encoding="utf-8")
        assert "20260522" not in text
        assert "5a35713" not in text
        assert "selected_panel_display_20260522" not in text


def test_tob_explainer_context_uses_microseries_aggregates_only():
    source = (REPO_ROOT / "scripts" / "build_tob_explainer_data.py").read_text(
        encoding="utf-8"
    )
    forbidden_fragments = [
        "import numpy",
        "np.asarray",
        ".values",
        ".weights",
        "weights[",
        'calculate("household_weight"',
        'calc("household_weight"',
    ]
    for forbidden in forbidden_fragments:
        assert forbidden not in source


def test_public_parameter_csv_uses_behavioral_not_conventional_labeling():
    reform_parameters = pd.read_csv(DASHBOARD_DATA / "baseline_reform_parameters.csv")
    scoring_types = set(reform_parameters["scoring_type"])
    policy_roles = set(reform_parameters["policy_role"])

    assert "behavioral" in scoring_types
    assert "conventional" not in scoring_types
    assert "behavioral_scoring_elasticity" in policy_roles
    assert "conventional_scoring_elasticity" not in policy_roles


def test_public_dashboard_hides_income_tax_diagnostic_card():
    source = (
        REPO_ROOT
        / "dashboard"
        / "src"
        / "components"
        / "baseline-assumptions-section.tsx"
    ).read_text(encoding="utf-8")

    assert "Income-tax diagnostic" not in source
    assert "Federal income tax / GDP comes directly" not in source
    assert "IncomeTaxPlausibilityChart" not in source


def test_public_dashboard_hides_2026_baseline_tob_cards():
    dashboard_shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    baseline_section = (
        REPO_ROOT
        / "dashboard"
        / "src"
        / "components"
        / "baseline-assumptions-section.tsx"
    ).read_text(encoding="utf-8")

    assert "2026 baseline TOB" not in dashboard_shell
    assert "2026 TOB baseline" not in baseline_section


def test_baseline_assumption_public_audit_files_exist_and_cover_core_contract():
    for path in BASELINE_AUDIT_PUBLIC_FILES:
        assert path.exists(), f"Missing dashboard baseline audit artifact: {path.name}"

    targets = pd.read_csv(DASHBOARD_DATA / "baseline_calibration_targets.csv")
    diagnostics = pd.read_csv(DASHBOARD_DATA / "baseline_calibration_diagnostics.csv")
    policy_parameters = pd.read_csv(DASHBOARD_DATA / "baseline_policy_parameters.csv")
    reform_parameters = pd.read_csv(DASHBOARD_DATA / "baseline_reform_parameters.csv")

    assert {
        "payroll_total",
        "oasdi_tob",
        "hi_tob",
    }.issubset(set(targets["constraint_name"]))
    assert targets["used_in_year_runner_reconciliation"].astype(bool).any()
    assert (
        diagnostics["diagnostic_id"]
        .isin(["federal_income_tax_pct_gdp", "effective_sample_size"])
        .any()
    )
    assert "gov.irs.social_security.taxability.threshold.base.main.SINGLE" in set(
        policy_parameters["parameter_name"]
    )
    assert "gov.irs.social_security.taxability.threshold.base.main.SINGLE" in set(
        reform_parameters["parameter_name"]
    )
    assert "static" in set(reform_parameters["scoring_type"])


def test_income_tax_direct_microsim_guard_rejects_adulterated_exact_rows(tmp_path):
    good = load_dashboard_results("static")
    bad_results = tmp_path / "bad_results.csv"
    bad = good.copy()
    mask = (
        bad["full_h5_result_type"].eq("exact_full_h5")
        & bad["reform_name"].eq("option1")
        & bad["year"].eq(2026)
    )
    bad.loc[mask, "baseline_revenue"] -= 1000.0
    bad.to_csv(bad_results, index=False)

    with pytest.raises(AssertionError):
        assert_income_tax_baseline_is_direct_microsim(bad_results)


def test_baseline_assumption_artifact_exposes_wage_indexed_tax_thresholds():
    parameters = pd.read_csv(DASHBOARD_DATA / "baseline_indexed_parameter_summary.csv")
    parameter_names = set(parameters["parameter_name"])

    missing = sorted(set(CORE_WAGE_INDEXED_TAX_PARAMETERS) - parameter_names)
    assert not missing, f"Missing core wage-indexed tax parameters: {missing}"

    core_parameters = parameters[
        parameters["parameter_name"].isin(CORE_WAGE_INDEXED_TAX_PARAMETERS)
    ]
    for row in core_parameters.itertuples(index=False):
        assert row.value_2035 > row.value_2034, (
            f"{row.parameter_name} does not rise at the 2035 wage-indexing boundary"
        )
        assert row.growth_2026_to_2100_pct >= MIN_WAGE_INDEXED_THRESHOLD_GROWTH_PCT, (
            f"{row.parameter_name} only grows {row.growth_2026_to_2100_pct:.1f}% "
            "from 2026 to 2100"
        )


def test_post_obbba_tob_baseline_manifest_matches_current_artifact():
    manifest = load_post_obbba_manifest()

    assert manifest["scenario_id"] == "crfb_tr2026_current_law_tob_75y"
    assert manifest["baseline_kind"] == "calibration_target"
    # TR2026 carries OBBBA in current law, so the baseline is law-based.
    assert manifest["not_law"] is False
    assert manifest["law_mode"] == "trustees-2026-intermediate-v1"
    assert (
        manifest["artifact_contract"]["must_consume_baseline_sha256"]
        == manifest["baseline_sha256"]
    )
    assert manifest["artifact_contract"]["reject_raw_current_law_substitution"] is True


def test_release_and_dashboard_metadata_carry_baseline_hash_contract():
    manifest = load_post_obbba_manifest()
    expected_sha = manifest["baseline_sha256"]

    results_metadata = json.loads(RESULTS_METADATA.read_text(encoding="utf-8"))
    dashboard_metadata = json.loads(
        DASHBOARD_BASELINE_METADATA.read_text(encoding="utf-8")
    )
    public_manifest = json.loads(PUBLIC_BASELINE_MANIFEST.read_text(encoding="utf-8"))

    assert results_metadata["post_obbba_tob_baseline_applied"] is False
    assert "post_obbba_tob_baseline_sha256" not in results_metadata
    assert dashboard_metadata["post_obbba_tob_baseline_sha256"] == expected_sha
    assert dashboard_metadata["scenario_id"] == manifest["scenario_id"]
    assert dashboard_metadata["baseline_kind"] == "calibration_target"
    assert dashboard_metadata["not_law"] is False
    assert dashboard_metadata["law_mode"] == manifest["law_mode"]
    assert (
        dashboard_metadata["hi_bridge_method"]
        == manifest["bridge_methods"]["hi_method"]
    )

    assert public_manifest["baseline_sha256"] == expected_sha
    assert dashboard_metadata["policyengine_version"] == "4.5.1"
    assert Version(dashboard_metadata["policyengine_us_version"]) >= Version("1.691.10")
    assert Version(dashboard_metadata["policyengine_core_version"]) >= Version("3.26.1")
    for package_name in ("policyengine", "policyengine-us", "policyengine-core"):
        package_metadata = dashboard_metadata["policyengine_packages"][package_name]
        assert package_metadata["version"]
        if package_name == "policyengine":
            assert package_metadata["source"] in {"registry", "direct_url"}
            assert package_metadata["direct_url_present"] is (
                package_metadata["source"] == "direct_url"
            )
        else:
            assert package_metadata["source"] == "registry"
            assert package_metadata["direct_url_present"] is False
            assert package_metadata["editable"] is False


def test_release_builder_does_not_apply_post_obbba_tob_calibration():
    import importlib.util

    script = REPO_ROOT / "scripts" / "publish_full_h5_static_dashboard_results.py"
    spec = importlib.util.spec_from_file_location("build_latesthf_guard_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert not hasattr(module, "load_tob_calibration_target")
    assert not hasattr(module, "apply_tob_baseline_calibration")


def test_release_pipeline_has_no_ambiguous_raw_trustees_cli_or_dashboard_reference():
    guarded_paths = [
        REPO_ROOT / "scripts" / "publish_full_h5_static_dashboard_results.py",
        REPO_ROOT / "scripts" / "build_dashboard_baseline_assumptions.py",
        REPO_ROOT / "dashboard" / "src" / "lib" / "baseline-assumptions-data.ts",
    ]

    for path in guarded_paths:
        text = path.read_text(encoding="utf-8")
        assert "--trustees-current-law-tob" not in text
        assert "tob_current_law_tr2025.csv" not in text


def test_static_release_exposes_all_static_reforms_in_dashboard_metadata():
    static = load_dashboard_results("static")
    reforms_ts = REPO_ROOT / "dashboard" / "src" / "lib" / "reforms.ts"
    reform_text = reforms_ts.read_text(encoding="utf-8")

    for reform_name in sorted(static["reform_name"].unique()):
        assert f'id: "{reform_name}"' in reform_text


def test_legacy_combined_dashboard_csv_is_not_public():
    legacy_paths = [
        DASHBOARD_DATA / "tob_revnue_impacts_result.csv",
        DASHBOARD_OUT / "tob_revnue_impacts_result.csv",
        *VERCEL_SITE.rglob("tob_revnue_impacts_result.csv"),
    ]
    for path in legacy_paths:
        assert not path.exists(), f"Legacy combined dashboard CSV is public: {path}"


def test_stale_multiplier_response_artifacts_are_not_public_or_packaged():
    stale_patterns = [
        "*all_conventional_results*",
        "*conventional_sample20*",
        "*sample20_multiplier*",
        "*same_sample*",
        "*behavioral_sentinel*",
        "*dynamic_results*",
        "*option13_balanced_fix*",
        "*trustees_vs_pe_gaps_comparison*",
    ]
    roots = [RESULTS, DASHBOARD_DATA, DASHBOARD_OUT, VERCEL_SITE]
    stale_paths = [
        path
        for root in roots
        if root.exists()
        for pattern in stale_patterns
        for path in root.rglob(pattern)
    ]
    assert stale_paths == []


def test_paper_links_use_dashboard_base_path():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    assert 'sitePath("/paper/")' in shell
    assert 'href="/paper/' not in shell


def test_dashboard_defaults_to_full_75_year_surface():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    data_loader = (
        REPO_ROOT / "dashboard" / "src" / "lib" / "dashboard-data.ts"
    ).read_text(encoding="utf-8")

    # Static-only scoring: hardcoded, with no scoring toggle exposed.
    assert 'const scoringType: ScoringType = "static";' in shell
    assert "Labor response" not in shell
    assert 'value: "behavioral"' not in shell
    # The full 75-year surface is always shown: view mode is fixed and the
    # 10-year/75-year period toggle is gone.
    assert 'const viewMode: ViewMode = "75year";' in shell
    assert '{ label: "10-year", value: "10year" }' not in shell
    assert 'useState<DisplayUnit>("pctPayroll")' in shell
    # The summary card carries the four headline figures.
    assert 'label: "10-year effect"' in shell
    assert '"75-year total"' in shell
    assert 'label: "75-year OASDI"' in shell
    assert 'label: "75-year HI"' in shell
    assert "spotlightRows(selectedData, viewMode)" in shell
    assert "new Set([2026, 2035, 2050, 2075, 2100])" in data_loader
    assert "const xAxisDomain: [number, number]" in shell
    assert 'viewMode === "75year" ? [2026, 2100] : [2026, 2035]' in shell
    assert 'type="number"' in shell


def test_ss_solvent_dashboard_view_is_long_run_only():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")

    # The solvency baseline is offered and framed as a long-run scenario that
    # splices scheduled-benefits scoring before 2035.
    assert '{ label: "SS solvent", value: "ssSolvent" }' in shell
    assert "on top of the solvent system from 2035 (shown" in shell
    assert '? "SS-solvent total"' in shell
    assert ': "75-year total"' in shell
    # The chart marks the 2035 baseline switch only under the solvency view.
    assert "solventStartYear={" in shell
    assert 'baselineScenario === "ssSolvent" ? 2035 : undefined' in shell
    # External current-law estimates stay hidden under the solvency baseline.
    assert 'baselineScenario !== "ssSolvent" && (' in shell


def test_reproducibility_roadmap_points_to_full_reform_h5_artifacts():
    roadmap = (
        REPO_ROOT / "dashboard" / "src" / "lib" / "reproducibility-roadmap-data.ts"
    ).read_text(encoding="utf-8")

    assert "reform_full_h5/year=YYYY/reform=OPTION/metadata.json" in roadmap
    assert "full reform H5 plus metadata" in roadmap
    assert "reform_raw_h5" not in roadmap
    assert "raw reform H5" not in roadmap


def test_legacy_reform_raw_h5_helpers_are_removed():
    for path in [
        REPO_ROOT / "src" / "year_runner.py",
        REPO_ROOT / "src" / "modal_batch_helpers.py",
    ]:
        text = path.read_text(encoding="utf-8")
        assert "reform_raw_h5" not in text
        assert "raw_h5_output_path" not in text
        assert "save_reform_raw_h5_only" not in text
        assert "CRFB_REFORM_RAW_H5" not in text


def test_canonical_progress_ledger_is_tracked_and_fail_closed():
    ledger = json.loads(
        (REPO_ROOT / "docs" / "current" / "reform-modeling-progress.json").read_text(
            encoding="utf-8"
        )
    )

    assert ledger["paid_modal_launch_allowed"] is False
    assert ledger["sentinel_launch_allowed"] is False
    assert ledger["full_launch_allowed"] is False
    assert ledger["allowed_paid_call_count"] == 0
    assert ledger["approved_cells"] == []
    assert ledger["approved_worker_entrypoint"] == (
        "src.reform_full_h5_worker.run_reform_full_h5_cell"
    )


def test_legacy_gcp_batch_paths_are_fail_closed():
    script_expectations = {
        REPO_ROOT / "batch" / "compute_year.py": "modal_batch/reform_full_h5.py",
        REPO_ROOT / "batch" / "submit_years.py": "modal_batch/reform_full_h5.py",
    }
    for script, expected_pointer in script_expectations.items():
        text = script.read_text(encoding="utf-8")
        tree = ast.parse(text)
        cloud_imports = [
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Import)
                and any(alias.name.startswith("google.cloud") for alias in node.names)
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("google.cloud")
            )
        ]
        assert "archived and fail-closed" in text
        assert expected_pointer in text
        assert cloud_imports == []
        assert "client.create_job" not in text
        assert "BatchServiceClient" not in text


def test_legacy_special_case_modal_runners_are_fail_closed():
    script_expectations = {
        REPO_ROOT / "batch" / "run_option12_standalone.py": "canonical full-H5",
        REPO_ROOT / "batch" / "run_option13_modal.py": "balanced_fix_recompute_spec.md",
        REPO_ROOT / "batch" / "run_option14_only.py": "balanced_fix_recompute_spec.md",
        REPO_ROOT
        / "scripts"
        / "recover_special_case_run.py": "balanced_fix_recompute_spec.md",
        REPO_ROOT
        / "scripts"
        / "assemble_special_case_results.py": "balanced_fix_recompute_spec.md",
        REPO_ROOT
        / "scripts"
        / "run_attribution_grid.py": "modal_batch/reform_full_h5.py",
        REPO_ROOT / "scripts" / "recover_modal_scenario_artifacts.py": "reform_full_h5",
        REPO_ROOT / "modal_batch" / "decomposition.py": "reform_full_h5",
        REPO_ROOT / "scripts" / "run_local_static_panel.py": "reform_full_h5",
    }
    for script, expected_pointer in script_expectations.items():
        text = script.read_text(encoding="utf-8")
        tree = ast.parse(text)
        modal_imports = [
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Import)
                and any(alias.name == "modal" for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and node.module == "modal")
        ]
        assert "archived and fail-closed" in text
        assert expected_pointer in text
        assert modal_imports == []
        assert "modal.App" not in text
        assert "run_modal_refresh.py" not in text
        assert "run_cells" not in text


def test_legacy_gcloud_monitor_scripts_are_fail_closed():
    for script in ["monitor_all.sh", "monitor_option4.sh"]:
        text = (REPO_ROOT / script).read_text(encoding="utf-8")
        assert "archived and fail-closed" in text
        assert "gcloud" not in text
        assert "gsutil" not in text
        assert "option4_dynamic" not in text


def test_legacy_dynamic_notebook_path_is_removed():
    assert not (REPO_ROOT / "analysis" / "policy-impacts-dynamic.ipynb").exists()
    analysis_readme = (REPO_ROOT / "analysis" / "README.md").read_text(encoding="utf-8")
    assert "policy-impacts-dynamic.ipynb" not in analysis_readme
    assert "policy_impacts_dynamic" not in analysis_readme
    assert "jupyter nbconvert" not in analysis_readme


def test_dashboard_uses_crfb_roth_naming_and_hides_legacy_special_cases():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    reforms = (REPO_ROOT / "dashboard" / "src" / "lib" / "reforms.ts").read_text(
        encoding="utf-8"
    )

    assert 'const STRUCTURAL_IDS = ["option5", "option12", "reverse_roth"];' in shell
    assert 'id: "option6"' in reforms
    assert 'shortName: "Short phase-in Roth"' in reforms
    assert 'id: "option12"' in reforms
    assert 'name: "Phased Roth-Style Swap"' in reforms
    assert 'shortName: "Phased Roth"' in reforms
    assert 'shortName: "Stacked Roth"' not in reforms
    assert 'id: "option13"' not in reforms
    assert 'id: "option14_stacked"' not in reforms
    assert "Balanced Fix baseline" not in shell
    assert "Balanced fix baseline" not in shell
    assert "balancedFix" not in shell


def test_dashboard_exposes_requested_trust_fund_split_modes():
    shell = (
        REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
    ).read_text(encoding="utf-8")
    data_loader = (
        REPO_ROOT / "dashboard" / "src" / "lib" / "dashboard-data.ts"
    ).read_text(encoding="utf-8")

    for mode in [
        '{ label: "Baseline shares", value: "baselineShares" }',
        '{ label: "Current law", value: "currentLaw" }',
        '{ label: "All OASDI", value: "allOasdi" }',
        '{ label: "All HI", value: "allHi" }',
    ]:
        assert mode in shell

    assert '"allOasdi"' in data_loader
    assert '"allHi"' in data_loader


def test_option7_dashboard_accounting_preserves_federal_total_and_residual():
    data_loader = (
        REPO_ROOT / "dashboard" / "src" / "lib" / "dashboard-data.ts"
    ).read_text(encoding="utf-8")
    methods = (REPO_ROOT / "paper" / "sections" / "03-methods.qmd").read_text(
        encoding="utf-8"
    )
    static = load_dashboard_results("static")
    option7_10 = static[
        (static["reform_name"] == "option7") & static["year"].between(2026, 2035)
    ]

    assert "generalRevenueOptions" not in data_loader
    assert "generalFundImpact" in data_loader
    assert "revenueImpact: row.revenueImpact" in data_loader
    assert option7_10["tob_total_impact"].sum() > 0
    assert option7_10["revenue_impact"].sum() > option7_10["tob_total_impact"].sum()
    assert (
        abs(
            option7_10["tob_total_impact"].sum()
            - option7_10["tob_oasdi_impact"].sum()
            - option7_10["tob_medicare_hi_impact"].sum()
        )
        < 1e-9
    )
    assert "general-fund columns show the" in methods
    assert "accounting split" in methods


def test_static_exhibit_generator_does_not_emit_unused_validation_sentinel_exhibit():
    generator = (REPO_ROOT / "scripts" / "generate_paper_static_exhibits.py").read_text(
        encoding="utf-8"
    )

    assert "validation-sentinels.md" not in generator


def test_labor_supply_response_exhibit_uses_current_contract():
    exhibit = (
        REPO_ROOT / "paper" / "exhibits" / "labor-supply-response-status.md"
    ).read_text(encoding="utf-8")

    assert "Labor-supply response rows are generated" in exhibit
    assert "current full-H5 reform contract" in exhibit


def test_public_dashboard_data_cover_full_2026_2100_horizon():
    static = load_dashboard_results("static")
    behavioral = load_dashboard_results("behavioral")

    for df, expected_reforms in [
        (static, 14),
        (behavioral, 14),
    ]:
        by_reform = df.groupby("reform_name")["year"].agg(["min", "max", "count"])
        assert len(by_reform) == expected_reforms
        assert by_reform["min"].eq(2026).all()
        assert by_reform["max"].eq(2100).all()
        assert by_reform["count"].eq(75).all()


def test_public_dashboard_percent_payroll_denominators_cover_full_horizon():
    oasdi_payroll = pd.read_csv(DASHBOARD_DATA / "ssa_economic_projections.csv")
    hi_payroll = pd.read_csv(DASHBOARD_DATA / "hi_taxable_payroll.csv")

    for df in [oasdi_payroll, hi_payroll]:
        years = sorted(df["year"].astype(int).tolist())
        assert years[0] <= 2026
        assert years[-1] >= 2100
        assert set(range(2026, 2101)).issubset(years)


def test_hi_payroll_denominator_follows_tr2026_ratio_path():
    """The HI denominator scales TR2026 OASDI payroll by the TR2025
    HI/OASDI payroll ratio; the CMS 2026 expanded tables publish no HI
    payroll levels."""
    dashboard = pd.read_csv(DASHBOARD_DATA / "hi_taxable_payroll.csv")
    tr2026 = pd.read_csv(RESULTS.parent / "data" / "social_security_aux_tr2026.csv")
    tr2025 = pd.read_csv(RESULTS.parent / "data" / "social_security_aux_tr2025.csv")
    raw_hi_2025 = pd.read_csv(RESULTS.parent / "data" / "hi_expenditures_tr2025.csv")
    raw_hi_2025 = raw_hi_2025[["year", "hi_taxable_payroll"]].copy()
    max_dashboard_year = int(dashboard["year"].max())
    max_raw_year = int(raw_hi_2025["year"].max())
    if max_raw_year < max_dashboard_year:
        previous = raw_hi_2025.sort_values("year").tail(2)
        growth = (
            previous["hi_taxable_payroll"].iloc[-1]
            / previous["hi_taxable_payroll"].iloc[-2]
        )
        value = previous["hi_taxable_payroll"].iloc[-1]
        extrapolated = []
        for year in range(max_raw_year + 1, max_dashboard_year + 1):
            value *= growth
            extrapolated.append({"year": year, "hi_taxable_payroll": value})
        raw_hi_2025 = pd.concat(
            [raw_hi_2025, pd.DataFrame(extrapolated)], ignore_index=True
        )

    merged = (
        dashboard.merge(
            tr2026[["year", "taxable_payroll_in_billion_nominal_usd"]], on="year"
        )
        .merge(
            tr2025[["year", "taxable_payroll_in_billion_nominal_usd"]],
            on="year",
            suffixes=("_tr2026", "_tr2025"),
        )
        .merge(raw_hi_2025, on="year")
    )
    assert len(merged) > 30
    assert 2100 in set(merged["year"])
    ratio = (merged["hi_taxable_payroll_y"] / 1e9) / merged[
        "taxable_payroll_in_billion_nominal_usd_tr2025"
    ]
    expected = ratio * merged["taxable_payroll_in_billion_nominal_usd_tr2026"]
    assert (merged["hi_taxable_payroll_x"] - expected).abs().max() < 1e-3
    # The uncapped HI base always exceeds the capped OASDI base.
    assert (
        merged["hi_taxable_payroll_x"]
        > merged["taxable_payroll_in_billion_nominal_usd_tr2026"]
    ).all()
