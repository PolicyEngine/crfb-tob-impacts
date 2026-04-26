import json
from pathlib import Path
import shutil
import subprocess

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS = REPO_ROOT / "results"
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "public" / "data"
DASHBOARD_OUT = REPO_ROOT / "dashboard" / "out" / "data"
VERCEL_SITE = REPO_ROOT / ".vercel-site"


def conventional_static_baseline_mismatch() -> float:
    static = pd.read_csv(RESULTS / "all_static_results_latesthf_2026_2100_14options.csv")
    conventional = pd.read_csv(
        RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options.csv"
    )
    merged = conventional[["reform_name", "year", "baseline_revenue"]].merge(
        static[["reform_name", "year", "baseline_revenue"]],
        on=["reform_name", "year"],
        suffixes=("_conventional", "_static"),
    )
    return float(
        (
            merged["baseline_revenue_conventional"]
            - merged["baseline_revenue_static"]
        )
        .abs()
        .max()
    )


def test_static_release_exposes_all_static_reforms_in_dashboard_metadata():
    static = pd.read_csv(RESULTS / "all_static_results_latesthf_2026_2100_14options.csv")
    reforms_ts = REPO_ROOT / "dashboard" / "src" / "lib" / "reforms.ts"
    reform_text = reforms_ts.read_text(encoding="utf-8")

    for reform_name in sorted(static["reform_name"].unique()):
        assert f'id: "{reform_name}"' in reform_text


def test_option13_comparison_data_matches_option13_baseline_gaps():
    option13 = pd.read_csv(DASHBOARD_DATA / "option13_balanced_fix.csv")
    comparison = pd.read_csv(DASHBOARD_DATA / "trustees_vs_pe_gaps_comparison.csv")
    merged = option13.merge(comparison, on="year", how="inner")

    oasdi_diff = (merged["baseline_ss_gap"].abs() / 1e9) - merged["pe_oasdi_gap_B"]
    hi_diff = (merged["baseline_hi_gap"].abs() / 1e9) - merged["pe_hi_gap_B"]

    assert oasdi_diff.abs().max() < 1e-6
    assert hi_diff.abs().max() < 1e-6


def test_option13_static_row_uses_standard_current_law_baseline():
    static = pd.read_csv(RESULTS / "all_static_results_latesthf_2026_2100_14options.csv")
    standard_baseline = (
        static[static["reform_name"] == "option1"]
        .set_index("year")[
            [
                "baseline_revenue",
                "baseline_tob_medicare_hi",
                "baseline_tob_oasdi",
                "baseline_tob_total",
            ]
        ]
        .sort_index()
    )
    option13_baseline = (
        static[static["reform_name"] == "option13"]
        .set_index("year")[standard_baseline.columns]
        .sort_index()
    )

    diff = (option13_baseline - standard_baseline).abs().max()
    assert float(diff.max()) < 1e-6


def test_conventional_release_is_not_claimed_comparable_until_baselines_match():
    mismatch = conventional_static_baseline_mismatch()
    methods_text = (REPO_ROOT / "paper" / "sections" / "03-methods.qmd").read_text(
        encoding="utf-8"
    )
    dashboard_text = (
        REPO_ROOT / "dashboard" / "src" / "components" / "methodology-section.tsx"
    ).read_text(encoding="utf-8")

    assert mismatch > 1
    assert "quarantined" in methods_text.lower()
    assert "quarantined" in dashboard_text.lower()


def test_quarantined_conventional_results_are_not_public_dashboard_artifacts():
    if conventional_static_baseline_mismatch() <= 1e-6:
        pytest.skip("Conventional baseline matches static; public publish is allowed.")

    public_conventional_paths = [
        DASHBOARD_DATA / "all_dynamic_results.csv",
        DASHBOARD_OUT / "all_dynamic_results.csv",
        *VERCEL_SITE.rglob("all_dynamic_results.csv"),
    ]
    for path in public_conventional_paths:
        assert not path.exists(), f"Quarantined conventional artifact is public: {path}"


def test_legacy_combined_dashboard_csv_is_not_public():
    legacy_paths = [
        DASHBOARD_DATA / "tob_revnue_impacts_result.csv",
        DASHBOARD_OUT / "tob_revnue_impacts_result.csv",
        *VERCEL_SITE.rglob("tob_revnue_impacts_result.csv"),
    ]
    for path in legacy_paths:
        assert not path.exists(), f"Legacy combined dashboard CSV is public: {path}"


def test_rendered_paper_does_not_publish_quarantined_conventional_estimates():
    unsafe_patterns = [
        "Dynamic standard-panel",
        "Ten-year conventional revenue effects",
        "Terminal-year conventional effects",
        "The conventional release now covers",
        "conventional dynamic release",
    ]
    html_paths = [
        REPO_ROOT / "paper" / "_build" / "index.html",
        *VERCEL_SITE.rglob("paper/index.html"),
    ]
    for path in html_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in unsafe_patterns:
            assert pattern not in text, f"Unsafe rendered paper text in {path}: {pattern}"

    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return
    pdf_paths = [
        REPO_ROOT / "paper" / "_build" / "index.pdf",
        *VERCEL_SITE.rglob("paper/index.pdf"),
    ]
    for path in pdf_paths:
        if not path.exists():
            continue
        text = subprocess.check_output(
            [pdftotext, str(path), "-"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for pattern in unsafe_patterns:
            assert pattern not in text, f"Unsafe rendered paper text in {path}: {pattern}"


def test_publish_conventional_results_rejects_mismatched_baseline():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "publish_conventional_results_test",
        REPO_ROOT / "scripts" / "publish_conventional_results.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    conventional = pd.read_csv(
        RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options.csv"
    )

    with pytest.raises(ValueError, match="Conventional baseline does not match"):
        module.validate_static_baseline_alignment(
            conventional,
            RESULTS / "all_static_results_latesthf_2026_2100_14options.csv",
        )


def test_special_case_metadata_tracks_manifest_and_run_id():
    metadata = json.loads(
        (RESULTS / "all_static_results_latesthf_2026_2100_14options_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    static = pd.read_csv(RESULTS / "all_static_results_latesthf_2026_2100_14options.csv")
    special = static[static["reform_name"].isin(["option13", "option14_stacked"])]

    assert metadata["special_case_manifest"]
    assert Path(metadata["special_case_manifest"]).exists()
    assert metadata["special_case_output_prefix"]
    assert not special["run_id"].eq("special-case-adhoc").any()


def test_paper_links_use_dashboard_base_path():
    shell = (REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx").read_text(
        encoding="utf-8"
    )
    assert "sitePath(\"/paper/\")" in shell
    assert 'href="/paper/' not in shell


def test_balanced_fix_tab_surfaces_roth_under_solvency_comparison():
    option13_tab = (
        REPO_ROOT / "dashboard" / "src" / "components" / "option13-tab.tsx"
    ).read_text(encoding="utf-8")

    assert "option14_stacked" in option13_tab
    assert "Roth swap under current law and Balanced Fix" in option13_tab
    assert "Balanced Fix solvency baseline" in option13_tab
