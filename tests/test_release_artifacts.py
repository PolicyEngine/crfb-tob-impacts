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
STATIC_METADATA = (
    RESULTS / "all_static_results_full_h5_v2pop_panel_20260612_metadata.json"
)
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
    RESULTS / "all_static_results_full_h5_v2pop_panel_display_20260612.csv",
    RESULTS / "results_full_h5_v2pop_panel_display_20260612.csv",
    DASHBOARD_RESULTS,
]
ALLOWED_CSV_ARTIFACTS = {
    "dashboard/public/data/balanced_fix_baseline.csv",
    "dashboard/public/data/baseline_aggregates.csv",
    "dashboard/public/data/baseline_calibration_diagnostics.csv",
    "dashboard/public/data/baseline_calibration_targets.csv",
    "dashboard/public/data/baseline_indexed_parameter_summary.csv",
    "dashboard/public/data/baseline_indexed_parameters.csv",
    "dashboard/public/data/baseline_indexing_growth.csv",
    "dashboard/public/data/baseline_policy_parameters.csv",
    "dashboard/public/data/baseline_reform_parameters.csv",
    "dashboard/public/data/hi_taxable_payroll.csv",
    "dashboard/public/data/live_baseline_results.csv",
    "dashboard/public/data/live_reform_status.csv",
    "dashboard/public/data/results.csv",
    "dashboard/public/data/ssa_economic_projections.csv",
    "dashboard/public/data/v2_baseline_diagnostics.csv",
    "data/SSPopJul_TR2024.csv",
    "data/SSPopJul_TR2026_interim.csv",
    "data/hi_expenditures_tr2025.csv",
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
    "results/all_static_results_full_h5_v2pop_panel_20260612.csv",
    "results/all_static_results_full_h5_v2pop_panel_display_20260612.csv",
    "results/behavioral_endpoint_full_h5_exact_20260612.csv",
    "results/behavioral_endpoint_ratio_display_20260612.csv",
    "results/modal_runs_production/full_h5_v2pop_tr2026_behavioral_endpoints_20260612.csv",
    "results/modal_runs_production/full_h5_v2pop_tr2026_panel_20260612.csv",
    "results/results_full_h5_v2pop_panel_display_20260612.csv",
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
    raw = pd.read_csv(
        RESULTS / "modal_runs_production" / "full_h5_v2pop_tr2026_panel_20260612.csv"
    )
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
    assert len(exact) == 224
    assert (
        exact["baseline_revenue"] - exact["baseline_revenue_raw_billions"]
    ).abs().max() < 1e-6
    assert (
        exact["baseline_tob_total"] - exact["baseline_tob_total_raw_billions"]
    ).abs().max() < 1e-6


def assert_income_tax_baseline_is_direct_microsim(path: Path) -> None:
    assert_release_artifact_matches_raw_full_h5(path)


def test_release_artifacts_keep_post_obbba_tob_as_diagnostic_target_only():
    static = pd.read_csv(
        RESULTS / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
    )
    dashboard_static = load_dashboard_results("static")
    dashboard_behavioral = load_dashboard_results("behavioral")

    assert load_dashboard_results("conventional").empty
    for results in [static, dashboard_static, dashboard_behavioral]:
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
        if Path(path).parent == Path(".")
        or any((REPO_ROOT / path).is_relative_to(root) for root in roots)
    }

    stale = discovered - ALLOWED_CSV_ARTIFACTS
    missing = ALLOWED_CSV_ARTIFACTS - discovered
    assert not stale, f"Unexpected stale CSV artifacts: {sorted(stale)}"
    assert not missing, f"Expected current CSV artifacts missing: {sorted(missing)}"


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
    good = pd.read_csv(
        RESULTS / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
    )
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

    static_metadata = json.loads(STATIC_METADATA.read_text(encoding="utf-8"))
    dashboard_metadata = json.loads(
        DASHBOARD_BASELINE_METADATA.read_text(encoding="utf-8")
    )
    public_manifest = json.loads(PUBLIC_BASELINE_MANIFEST.read_text(encoding="utf-8"))

    assert static_metadata["post_obbba_tob_baseline_applied"] is False
    assert "post_obbba_tob_baseline_sha256" not in static_metadata
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
    static = pd.read_csv(
        RESULTS / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
    )
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

    assert 'useState<ScoringType>("static")' in shell
    assert 'useState<DisplayUnit>("pctPayroll")' in shell
    assert 'useState<ViewMode>("75year")' in shell
    assert '{ label: "Static", value: "static" }' in shell
    assert '{ label: "Labor response", value: "behavioral" }' in shell
    assert '{ label: "Labor-supply response", value: "conventional" }' not in shell
    assert '{ label: "75-year", value: "75year" }' in shell
    assert shell.index('{ label: "10-year", value: "10year" }') < shell.index(
        '{ label: "75-year", value: "75year" }'
    )
    assert shell.index('label="75-year effect"') < shell.index('label="10-year effect"')
    assert 'label="OASDI / HI split"' not in shell
    assert 'caption="2026 baseline share"' not in shell
    assert "spotlightRows(selectedData, viewMode)" in shell
    assert "new Set([2026, 2035, 2050, 2075, 2100])" in data_loader


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


def test_validation_exhibit_uses_current_full_h5_contract_not_old_sentinel_csvs():
    exhibit = (REPO_ROOT / "paper" / "exhibits" / "validation-sentinels.md").read_text(
        encoding="utf-8"
    )
    static = pd.read_csv(
        RESULTS / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
    )
    standard = static[static["reform_name"].isin({f"option{i}" for i in range(1, 13)})]

    assert len(standard[standard["source"].eq("exact_full_h5")]) == 192
    assert "current full-H5 production" in exhibit
    assert "contract" in exhibit
    assert "Older non-contract artifacts are not" in exhibit


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

    merged = (
        dashboard.merge(
            tr2026[["year", "taxable_payroll_in_billion_nominal_usd"]], on="year"
        )
        .merge(
            tr2025[["year", "taxable_payroll_in_billion_nominal_usd"]],
            on="year",
            suffixes=("_tr2026", "_tr2025"),
        )
        .merge(raw_hi_2025[["year", "hi_taxable_payroll"]], on="year")
    )
    assert len(merged) > 30
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
