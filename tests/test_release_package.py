from __future__ import annotations

import importlib.util
import csv
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_release_package.py"


def load_package_module():
    spec = importlib.util.spec_from_file_location(
        "build_release_package_test", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_release_package_includes_current_contract_outputs_and_sources(tmp_path):
    module = load_package_module()

    package = module.build_release_package(
        package_root=tmp_path,
        package_name="test-release-package",
        archive=False,
    )

    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    included = {record["path"]: record for record in manifest["files"]}
    included_paths = [record["path"] for record in manifest["files"]]
    baseline_contract = manifest["post_obbba_tob_baseline"]

    expected_files = [
        "results.csv",
        "results.csv.metadata.json",
        "results/modal_runs_production/static_cells.csv",
        "results/modal_runs_production/behavioral_endpoint_cells.csv",
        "results/modal_runs_production/balanced_fix_results.csv",
        "results/modal_runs_production/balanced_fix_results_metadata.json",
        "dashboard/public/data/results.csv",
        "dashboard/public/data/balanced_fix_results.csv",
        "dashboard/public/data/balanced_fix_results_metadata.json",
        "dashboard/public/data/baseline_aggregates.csv",
        "dashboard/public/data/baseline_indexed_parameters.csv",
        "dashboard/public/data/baseline_indexed_parameter_summary.csv",
        "dashboard/public/data/baseline_indexing_growth.csv",
        "dashboard/public/data/baseline_calibration_targets.csv",
        "dashboard/public/data/baseline_calibration_diagnostics.csv",
        "dashboard/public/data/baseline_policy_parameters.csv",
        "dashboard/public/data/baseline_reform_parameters.csv",
        "dashboard/public/data/baseline_assumptions_metadata.json",
        "dashboard/public/data/post_obbba_tob_baseline_manifest.json",
        "dashboard/public/data/hi_taxable_payroll.csv",
        "dashboard/public/data/distributional.json",
        "dashboard/public/data/results_contract.json",
        "dashboard/public/data/tob_explainer.json",
        "docs/current/REFORM_MODELING_BIBLE.md",
        "docs/current/budget-window-infill.md",
        "docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json",
        "docs/current/manifests/baseline-dataset-manifest-9f1260b-certinfill.json",
        "docs/current/v2-baseline-method.md",
        "docs/current/v2-launch-runbook.md",
        "scripts/build_dashboard_baseline_assumptions.py",
        "scripts/build_distributional_data.py",
        "scripts/build_hi_expenditures_tr2026.py",
        "scripts/build_results_contract.py",
        "scripts/publish_balanced_fix_results.py",
        "scripts/build_tob_explainer_data.py",
        "scripts/build_dashboard_payroll_denominators.py",
        "scripts/publish_behavioral_endpoint_dashboard_results.py",
        "scripts/publish_dashboard_results.py",
        "scripts/publish_full_h5_static_dashboard_results.py",
        "modal_batch/balanced_fix.py",
        "src/balanced_fix.py",
        "src/cli.py",
        "src/dashboard_baseline_assumptions.py",
        "src/tax_assumption_loader.py",
        "tests/test_dashboard_baseline_assumptions.py",
        "data/ssa_tob_baseline_75year.manifest.json",
        "data/hi_expenditures_tr2026.csv",
        "data/tr2026_sources.manifest.json",
    ]

    def assert_packaged_file(relative: str) -> None:
        packaged = package.package_dir / relative
        assert packaged.exists(), relative
        assert relative in included
        assert included[relative]["sha256"] == module.file_sha256(packaged)

    for relative in expected_files:
        assert_packaged_file(relative)

    results_contract = json.loads(
        (package.package_dir / "dashboard/public/data/results_contract.json").read_text(
            encoding="utf-8"
        )
    )
    contract_baseline_build = results_contract["lineage"]["baseline_build"]
    contract_manifest_paths = {
        contract_baseline_build["manifest_path"],
        *contract_baseline_build.get("supplemental_manifest_paths", []),
    }
    for relative in contract_manifest_paths:
        assert_packaged_file(relative)

    built_dashboard_source = REPO_ROOT / "dashboard" / "out"
    if built_dashboard_source.exists():
        for relative in [
            "dashboard/out/index.html",
            "dashboard/out/data/results.csv",
        ]:
            assert_packaged_file(relative)

    assert len(included_paths) == len(set(included_paths))
    assert manifest["files_count"] == len(manifest["files"])
    assert "self-referential checksum" in manifest["manifest_note"]
    assert "release_manifest.json" not in included

    referenced_metadata = set()
    for relative in [
        "dashboard/public/data/baseline_calibration_targets.csv",
        "dashboard/public/data/baseline_calibration_diagnostics.csv",
    ]:
        with (package.package_dir / relative).open(
            newline="", encoding="utf-8"
        ) as file:
            for row in csv.DictReader(file):
                dataset_path = row.get("dataset_path") or ""
                if dataset_path.endswith(".h5.metadata.json"):
                    referenced_metadata.add(dataset_path)

    baseline_metadata_files = {
        record["path"]
        for record in manifest["files"]
        if record["category"] == "baseline_metadata"
    }
    assert referenced_metadata.issubset(baseline_metadata_files)
    for relative in referenced_metadata:
        assert (package.package_dir / relative).exists()

    assert baseline_contract["scenario_id"] == "crfb_tr2026_current_law_tob_75y"
    assert baseline_contract["baseline_kind"] == "calibration_target"
    assert baseline_contract["not_law"] is False
    assert (
        baseline_contract["baseline_sha256"]
        == json.loads(
            (
                package.package_dir / "data/ssa_tob_baseline_75year.manifest.json"
            ).read_text(encoding="utf-8")
        )["baseline_sha256"]
    )

    assert not any(
        record["category"] == "special_case_raws" for record in manifest["files"]
    )
    assert package.archive_path is None


def test_release_package_copies_contract_referenced_dynamic_manifest(
    tmp_path, monkeypatch
):
    module = load_package_module()
    dynamic_manifest = (
        REPO_ROOT
        / "docs"
        / "current"
        / "manifests"
        / "baseline-dataset-manifest-v2pop.json"
    )
    static_required_paths = {source for _, source in module.REQUIRED_FILES}
    assert dynamic_manifest.exists()
    assert dynamic_manifest not in static_required_paths

    monkeypatch.setattr(module, "contract_manifest_paths", lambda: [dynamic_manifest])

    package = module.build_release_package(
        package_root=tmp_path,
        package_name="test-release-package-dynamic-manifest",
        archive=False,
    )
    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
    included = {record["path"] for record in manifest["files"]}

    assert str(dynamic_manifest.relative_to(REPO_ROOT)) in included


@pytest.mark.parametrize(
    "bad_path",
    [
        "",
        "/tmp/manifest.json",
        "../manifest.json",
        "docs/current/../manifest.json",
        "docs/current/manifest.txt",
    ],
)
def test_contract_manifest_paths_rejects_non_package_paths(tmp_path, bad_path):
    module = load_package_module()
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(
        json.dumps(
            {
                "lineage": {
                    "baseline_build": {
                        "manifest_path": bad_path,
                        "supplemental_manifest_paths": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Contract manifest path"):
        module.contract_manifest_paths(contract_path)
