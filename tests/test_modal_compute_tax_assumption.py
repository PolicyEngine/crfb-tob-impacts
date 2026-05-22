import json
import os
from pathlib import Path

import pytest
from modal_batch import compute
from batch import run_option12_standalone, run_option13_modal, run_option14_only


def test_load_baseline_reform_for_year_starts_in_2035(monkeypatch):
    sentinel = object()

    monkeypatch.setattr(compute, "TAX_ASSUMPTION_START_YEAR", 2035)
    monkeypatch.setattr(compute, "TAX_ASSUMPTION_END_YEAR", 2100)
    monkeypatch.setattr(compute, "_load_baseline_reform", lambda: sentinel)

    assert compute._load_baseline_reform_for_year(2034) is None
    assert compute._load_baseline_reform_for_year(2035) is sentinel
    assert compute._load_baseline_reform_for_year(2100) is sentinel
    assert compute._load_baseline_reform_for_year(2101) is None


def test_modal_loader_uses_dataset_metadata(monkeypatch):
    sentinel = object()
    calls = []

    def load_reform(dataset_name, year, *, module_path=None, factory_name=None):
        calls.append((dataset_name, year, module_path, factory_name))
        return sentinel

    monkeypatch.setattr(
        compute,
        "load_tax_assumption_reform_for_dataset",
        load_reform,
    )

    assert compute._load_baseline_reform_for_dataset(2075, "dataset.h5") is sentinel
    assert calls == [("dataset.h5", 2075, None, None)]


def test_remote_dataset_contract_env_is_year_aware(monkeypatch):
    monkeypatch.setattr(compute, "TAX_ASSUMPTION_START_YEAR", 2035)
    monkeypatch.setattr(compute, "TAX_ASSUMPTION_END_YEAR", 2100)
    monkeypatch.setattr(compute, "REQUIRED_TAX_ASSUMPTION", "trustees-core")
    monkeypatch.delenv("CRFB_REQUIRED_TARGET_SOURCE", raising=False)
    monkeypatch.delenv("CRFB_MIN_CALIBRATION_QUALITY", raising=False)
    monkeypatch.setenv("CRFB_REQUIRED_TAX_ASSUMPTION", "stale-required-value")

    compute._set_remote_dataset_contract_env(2034)

    assert "CRFB_REQUIRED_TAX_ASSUMPTION" not in os.environ
    assert os.environ["CRFB_REQUIRED_TARGET_SOURCE"] == compute.REQUIRED_TARGET_SOURCE
    assert os.environ["CRFB_MIN_CALIBRATION_QUALITY"] == (
        compute.MINIMUM_CALIBRATION_QUALITY
    )

    compute._set_remote_dataset_contract_env(2035)

    assert os.environ["CRFB_REQUIRED_TAX_ASSUMPTION"] == "trustees-core"

    compute._set_remote_dataset_contract_env(
        2035,
        require_tax_assumption_contract=False,
    )

    assert "CRFB_REQUIRED_TAX_ASSUMPTION" not in os.environ


def test_managed_dataset_mode_does_not_install_raw_modal_template(monkeypatch):
    monkeypatch.setenv("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", "1")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    compute._set_remote_raw_dataset_template_if_needed()

    assert "CRFB_DATASET_TEMPLATE" not in os.environ


def test_raw_dataset_mode_installs_modal_template(monkeypatch):
    monkeypatch.delenv("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", raising=False)
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    compute._set_remote_raw_dataset_template_if_needed()

    assert os.environ["CRFB_DATASET_TEMPLATE"] == "/app/projected_datasets/{year}.h5"


def test_special_case_dataset_contract_env_is_year_aware(monkeypatch):
    for module in (run_option13_modal, run_option14_only):
        monkeypatch.setattr(module, "TAX_ASSUMPTION_START_YEAR", 2035)
        monkeypatch.setattr(module, "TAX_ASSUMPTION_END_YEAR", 2100)
        monkeypatch.setattr(module, "REQUIRED_TAX_ASSUMPTION", "trustees-core")
        monkeypatch.delenv("CRFB_REQUIRED_TARGET_SOURCE", raising=False)
        monkeypatch.delenv("CRFB_MIN_CALIBRATION_QUALITY", raising=False)
        monkeypatch.delenv("CRFB_REQUIRED_TAX_ASSUMPTION", raising=False)

        module.require_runtime_dataset_contract(2035)

        assert os.environ["CRFB_REQUIRED_TAX_ASSUMPTION"] == "trustees-core"
        assert os.environ["CRFB_REQUIRED_TARGET_SOURCE"] == (
            "trustees_2025_current_law"
        )
        assert os.environ["CRFB_MIN_CALIBRATION_QUALITY"] == "exact"

        module.require_runtime_dataset_contract(2034)

        assert "CRFB_REQUIRED_TAX_ASSUMPTION" not in os.environ


def test_option12_standalone_requires_contract_before_dataset_resolution():
    source = Path(run_option12_standalone.__file__).read_text(encoding="utf-8")
    function_source = source[source.index("def compute_option12_standalone") :]

    assert function_source.index("set_required_long_run_contract_env(year)") < (
        function_source.index("dataset = dataset_path(year)")
    )


def test_load_worker_baseline_skips_artifact_when_tax_assumption_inactive(monkeypatch):
    def fail_if_artifact_lookup_runs(year: int, dataset_name):
        raise AssertionError(f"artifact lookup should not run for {year}")

    def load_baseline(year, dataset_name, baseline_reform, progress_label):
        assert year == 2034
        assert dataset_name == "dataset.h5"
        assert baseline_reform is None
        assert progress_label == "baseline-2034-static"
        return "computed baseline"

    monkeypatch.setattr(
        compute, "_resolve_baseline_metrics_path", fail_if_artifact_lookup_runs
    )

    baseline, source = compute._load_worker_baseline(
        year=2034,
        scoring_type="static",
        dataset_name="dataset.h5",
        baseline_reform=None,
        load_baseline=load_baseline,
        progress_label="baseline-2034-static",
    )

    assert baseline == "computed baseline"
    assert source == "computed in worker with MicroSeries.sum()"


def test_load_worker_baseline_validates_artifact_then_recomputes_with_microseries(
    monkeypatch, tmp_path
):
    metrics_path = tmp_path / "metrics.npz"
    baseline_reform = object()

    def load_baseline(year, dataset_name, baseline_reform, progress_label):
        assert year == 2035
        assert dataset_name == "dataset.h5"
        assert baseline_reform is baseline_reform_obj
        return "computed baseline"

    baseline_reform_obj = baseline_reform

    monkeypatch.setattr(
        compute,
        "_resolve_baseline_metrics_path",
        lambda year, dataset_name: metrics_path,
    )

    baseline, source = compute._load_worker_baseline(
        year=2035,
        scoring_type="static",
        dataset_name="dataset.h5",
        baseline_reform=baseline_reform,
        load_baseline=load_baseline,
    )

    assert baseline == "computed baseline"
    assert source == "computed in worker with MicroSeries.sum()"


def test_baseline_artifact_requires_matching_dataset_metadata(tmp_path):
    dataset_path = tmp_path / "2075.h5"
    dataset_path.write_text("", encoding="utf-8")
    dataset_metadata = {
        "profile": {"name": "ss-payroll-tob"},
        "target_source": {"name": "trustees_2025_current_law"},
        "tax_assumption": {"name": "trustees-2025-core-thresholds-v1"},
        "support_augmentation": {"name": "donor-backed-composite-v1"},
        "calibration_audit": {
            "calibration_quality": "exact",
            "validation_passed": True,
            "max_constraint_pct_error": 0.0,
            "effective_sample_size": 5000.0,
            "top_10_weight_share_pct": 1.5,
            "top_100_weight_share_pct": 10.0,
            "donor_family_effective_sample_size": 2000.0,
            "top_10_donor_family_weight_share_pct": 2.0,
            "max_donor_family_weight_share_pct": 0.5,
            "positive_clone_donor_family_count": 2000,
            "clone_donor_family_effective_sample_size": 2000.0,
            "top_10_clone_donor_family_weight_share_pct": 2.0,
            "top_100_clone_donor_family_weight_share_pct": 10.0,
            "max_clone_donor_family_weight_share_pct": 0.5,
            "constraints": {"oasdi_tob": {"pct_error": 0.0}},
            "support_blueprint": {"clone_household_count": 1000},
        },
    }
    Path(f"{dataset_path}.metadata.json").write_text(
        json.dumps(dataset_metadata),
        encoding="utf-8",
    )

    metrics_dir = tmp_path / "scenario=baseline"
    metrics_dir.mkdir()
    metrics_path = metrics_dir / "metrics.npz"
    metrics_path.write_text("", encoding="utf-8")
    artifact_metadata = {
        "tax_assumption": {
            "name": compute.REQUIRED_TAX_ASSUMPTION,
            "factory": compute.TAX_ASSUMPTION_FACTORY,
            "start_year": compute.TAX_ASSUMPTION_START_YEAR,
            "end_year": compute.TAX_ASSUMPTION_END_YEAR,
            "implementation": compute.canonical_tax_assumption_implementation_metadata(
                compute.REQUIRED_TAX_ASSUMPTION
            ),
        },
        "dataset": {
            "dataset_size": dataset_path.stat().st_size,
            "metadata": dataset_metadata,
            "metadata_sha256": compute._file_sha256(
                Path(f"{dataset_path}.metadata.json")
            ),
        },
    }
    (metrics_dir / "metadata.json").write_text(
        json.dumps(artifact_metadata),
        encoding="utf-8",
    )

    assert compute._baseline_metrics_matches_contract(metrics_path, dataset_path)

    dataset_metadata["calibration_audit"]["effective_sample_size"] = 12.0
    Path(f"{dataset_path}.metadata.json").write_text(
        json.dumps(dataset_metadata),
        encoding="utf-8",
    )

    assert not compute._baseline_metrics_matches_contract(metrics_path, dataset_path)


def test_dataset_artifact_metadata_uses_baseline_contract_keys(
    monkeypatch,
    tmp_path,
):
    dataset_path = tmp_path / "2075.h5"
    dataset_path.write_text("dataset", encoding="utf-8")
    metadata_path = Path(f"{dataset_path}.metadata.json")
    metadata_path.write_text('{"year": 2075}', encoding="utf-8")
    monkeypatch.delenv("CRFB_HASH_SCENARIO_DATASET", raising=False)

    metadata = compute._dataset_artifact_metadata(dataset_path)

    assert metadata["size"] == dataset_path.stat().st_size
    assert metadata["dataset_size"] == dataset_path.stat().st_size
    assert metadata["sha256"] == compute._file_sha256(dataset_path)
    assert metadata["dataset_sha256"] == compute._file_sha256(dataset_path)
    assert metadata["metadata_sha256"] == compute._file_sha256(metadata_path)


def test_special_case_runners_only_load_tax_assumption_from_2035(monkeypatch):
    sentinel = object()

    for module in (run_option13_modal, run_option14_only):
        monkeypatch.setattr(module, "TAX_ASSUMPTION_START_YEAR", 2035)
        monkeypatch.setattr(module, "TAX_ASSUMPTION_END_YEAR", 2100)
        monkeypatch.setattr(module, "load_runtime_baseline_reform", lambda: sentinel)

        assert module.load_runtime_baseline_reform_for_year(2034) is None
        assert module.load_runtime_baseline_reform_for_year(2035) is sentinel


def test_special_case_runners_load_tax_assumption_from_dataset_metadata(monkeypatch):
    for module in (run_option13_modal, run_option14_only):
        calls = []
        sentinel = object()

        def load_reform(dataset_name, year, *, module_path=None, factory_name=None):
            calls.append((dataset_name, year, module_path, factory_name))
            return sentinel

        monkeypatch.setattr(
            module,
            "load_tax_assumption_reform_for_dataset",
            load_reform,
        )

        assert (
            module.load_runtime_baseline_reform_for_dataset(2075, "dataset.h5")
            is sentinel
        )
        assert calls == [("dataset.h5", 2075, None, None)]


def test_special_case_reform_combiner_omits_inactive_baseline_reform():
    baseline = object()
    reform = object()

    for module in (run_option13_modal, run_option14_only):
        assert module.combine_with_baseline_reform(None, reform) is reform
        assert module.combine_with_baseline_reform(baseline, reform) == (
            baseline,
            reform,
        )


def test_tax_assumption_loader_reads_embedded_h5_contract(tmp_path):
    h5py = pytest.importorskip("h5py")

    from src.tax_assumption_loader import (
        H5_LONG_TERM_CONTRACT_ATTR,
        tax_assumption_contract_for_dataset,
    )

    dataset_path = tmp_path / "2075.h5"
    with h5py.File(dataset_path, "w") as h5_file:
        h5_file.attrs[H5_LONG_TERM_CONTRACT_ATTR] = json.dumps(
            {
                "tax_assumption": {
                    "name": "trustees-2025-core-thresholds-v1",
                    "start_year": 2035,
                    "end_year": 2100,
                }
            }
        )

    contract = tax_assumption_contract_for_dataset(dataset_path, 2075)

    assert contract.name == "trustees-2025-core-thresholds-v1"
    assert contract.active is True
    assert contract.start_year == 2035
    assert contract.end_year == 2100


def test_tax_assumption_loader_rejects_missing_post_2034_dataset_contract(tmp_path):
    from src.tax_assumption_loader import tax_assumption_contract_for_dataset

    dataset_path = tmp_path / "2035.h5"
    dataset_path.write_text("", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="metadata missing"):
        tax_assumption_contract_for_dataset(dataset_path, 2035)

    contract = tax_assumption_contract_for_dataset(dataset_path, 2034)
    assert contract.active is False


def test_tax_assumption_loader_rejects_external_trustees_module_by_default(tmp_path):
    from src.tax_assumption_loader import load_tax_assumption_reform_for_metadata

    module_path = tmp_path / "tax_assumptions.py"
    module_path.write_text(
        "def create_trustees_core_thresholds_reform(**kwargs):\n    return object()\n",
        encoding="utf-8",
    )
    metadata = {
        "tax_assumption": {
            "name": "trustees-2025-core-thresholds-v1",
            "start_year": 2035,
            "end_year": 2100,
        }
    }

    with pytest.raises(ValueError, match="Refusing external tax-assumption"):
        load_tax_assumption_reform_for_metadata(
            metadata,
            2035,
            module_path=module_path,
        )


def test_modal_and_special_runners_do_not_package_tax_assumption_modules():
    local_wrapper = (
        Path(__file__).resolve().parents[1] / "src" / "crfb_tax_assumptions.py"
    )
    assert not local_wrapper.exists()

    for module in (compute, run_option13_modal, run_option14_only):
        source = Path(module.__file__).read_text(encoding="utf-8")

        assert "TAX_ASSUMPTION_LOCAL_PATH" not in source
        assert "tax_assumption_runtime_path" not in source
        assert "_tax_assumption_runtime_path" not in source
        assert "add_local_dir(TAX_ASSUMPTION" not in source


def test_tax_assumption_preserves_pre_start_brackets_and_anchors_2035():
    policyengine_us = pytest.importorskip("policyengine_us")
    pytest.importorskip("policyengine_us.reforms.ssa.trustees_core_thresholds")

    from src.tax_assumption_loader import load_tax_assumption_reform_by_name

    reform = load_tax_assumption_reform_by_name(
        "trustees-2025-core-thresholds-v1",
        start_year=2035,
        end_year=2100,
    )

    def bracket2_single(parameters, year: int) -> float:
        return float(
            getattr(parameters.gov.irs.income.bracket.thresholds, "2").SINGLE(
                f"{year}-01-01"
            )
        )

    def rounded_down_25(value: float) -> float:
        return (value // 25) * 25

    def nawi_ratio_since_2034(parameters, year: int) -> float:
        nawi = parameters.gov.ssa.nawi
        return float(nawi(f"{year - 1}-01-01")) / float(nawi("2033-01-01"))

    default_2034 = policyengine_us.Microsimulation(
        start_instant="2034-01-01"
    ).tax_benefit_system.parameters
    reform_2034 = policyengine_us.Microsimulation(
        reform=reform,
        start_instant="2034-01-01",
    ).tax_benefit_system.parameters
    reform_2035 = policyengine_us.Microsimulation(
        reform=reform,
        start_instant="2035-01-01",
    ).tax_benefit_system.parameters
    reform_2036 = policyengine_us.Microsimulation(
        reform=reform,
        start_instant="2036-01-01",
    ).tax_benefit_system.parameters
    reform_2037 = policyengine_us.Microsimulation(
        reform=reform,
        start_instant="2037-01-01",
    ).tax_benefit_system.parameters

    assert bracket2_single(reform_2034, 2034) == bracket2_single(default_2034, 2034)

    assert bracket2_single(reform_2035, 2035) == rounded_down_25(
        bracket2_single(default_2034, 2034) * nawi_ratio_since_2034(reform_2035, 2035)
    )
    assert bracket2_single(reform_2036, 2036) == rounded_down_25(
        bracket2_single(default_2034, 2034) * nawi_ratio_since_2034(reform_2036, 2036)
    )
    assert bracket2_single(reform_2037, 2037) == rounded_down_25(
        bracket2_single(default_2034, 2034) * nawi_ratio_since_2034(reform_2037, 2037)
    )
