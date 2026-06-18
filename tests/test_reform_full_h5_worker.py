from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.reform_full_h5_artifacts import inspect_entity_table_h5
from src.reform_full_h5_worker import (
    FULL_H5_DIRNAME,
    ObjectStoreConfig,
    build_policy_reform,
    install_behavioral_baseline_tax_system,
    object_store_config_from_env,
    object_store_keys,
    reform_full_h5_artifact_dir,
    save_complete_microsimulation_h5,
    validate_baseline_dataset_against_manifest,
    validate_object_store_target_matches_approval,
)


class _Entity:
    def __init__(self, key: str):
        self.key = key


class _Population:
    def __init__(self, key: str, count: int):
        self.entity = _Entity(key)
        self.count = count


class _Variable:
    def __init__(self, entity: str):
        self.entity = _Entity(entity)


class _System:
    def __init__(self):
        self.variables = {
            "person_id": _Variable("person"),
            "person_weight": _Variable("person"),
            "age": _Variable("person"),
            "household_id": _Variable("household"),
            "household_weight": _Variable("household"),
            "household_net_income": _Variable("household"),
            "tax_unit_id": _Variable("tax_unit"),
            "tax_unit_weight": _Variable("tax_unit"),
            "income_tax": _Variable("tax_unit"),
        }


class _Simulation:
    def __init__(self):
        self.populations = {
            "person": _Population("person", 2),
            "household": _Population("household", 1),
            "tax_unit": _Population("tax_unit", 1),
        }
        self.tax_benefit_system = _System()
        self.values = {
            ("person_id", "person"): np.array([1, 2]),
            ("person_weight", "person"): np.array([1.0, 1.0]),
            ("age", "person"): np.array([70, 72]),
            ("household_id", "household"): np.array([1]),
            ("household_weight", "household"): np.array([2.0]),
            ("household_net_income", "household"): np.array([10.0]),
            ("tax_unit_id", "tax_unit"): np.array([1]),
            ("tax_unit_weight", "tax_unit"): np.array([2.0]),
            ("income_tax", "tax_unit"): np.array([1.0]),
        }

    def calculate(self, variable_name: str, period: int, map_to: str):
        del period
        return self.values[(variable_name, map_to)]


_TEST_VARIABLES_BY_ENTITY = {
    "person": ["age", "person_id", "person_weight"],
    "household": ["household_id", "household_weight", "household_net_income"],
    "tax_unit": ["tax_unit_id", "tax_unit_weight", "income_tax"],
}


class _SkippingSimulation(_Simulation):
    def __init__(self):
        super().__init__()
        self.tax_benefit_system.variables["missing_person_variable"] = _Variable(
            "person"
        )


def test_save_complete_microsimulation_h5_writes_entity_tables(tmp_path: Path):
    output = tmp_path / "scenario.h5"

    metadata = save_complete_microsimulation_h5(
        _Simulation(),
        output,
        year=2075,
        fail_on_empty_entity=False,
        variables_by_entity=_TEST_VARIABLES_BY_ENTITY,
    )
    manifest = inspect_entity_table_h5(output)

    assert metadata["artifact_type"] == "policyengine_us_full_reform_output_h5"
    assert metadata["variable_count"] == 9
    assert manifest["entities"]["person"]["columns"] == [
        "age",
        "person_id",
        "person_weight",
    ]
    assert manifest["entities"]["household"]["required_weight_column_present"] is True


def test_behavioral_scoring_uses_behavioral_reform_alias(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        "src.reform_full_h5_worker._option_behavioral_reform",
        lambda reform_id: (reform_id, marker),
    )

    assert build_policy_reform("option1", "behavioral") == ("option1", marker)


def test_conventional_scoring_label_is_not_accepted():
    with pytest.raises(ValueError, match="Unsupported scoring_type"):
        build_policy_reform("option1", "conventional")


def test_behavioral_scoring_accepts_custom_reform(monkeypatch):
    marker = object()

    monkeypatch.setattr(
        "src.reforms.get_reverse_roth_behavioral_reform",
        lambda: marker,
    )

    assert build_policy_reform("reverse_roth", "behavioral") is marker


def test_behavioral_baseline_installation_uses_current_law_reform(monkeypatch):
    baseline_reform = object()
    baseline_system = SimpleNamespace(simulation=None)
    sim = SimpleNamespace(baseline=SimpleNamespace())

    monkeypatch.setattr(
        "policyengine_us.Microsimulation.default_tax_benefit_system",
        staticmethod(
            lambda reform: baseline_system if reform is baseline_reform else None
        ),
    )

    result = install_behavioral_baseline_tax_system(
        sim,
        baseline_reform=baseline_reform,
    )

    assert result["installed"] is True
    assert sim.baseline.tax_benefit_system is baseline_system
    assert baseline_system.simulation is sim.baseline
    assert sim.baseline.reform is baseline_reform


def test_save_complete_microsimulation_h5_fails_on_unapproved_skipped_variable(
    tmp_path: Path,
):
    with pytest.raises(ValueError, match="skipped unapproved variables"):
        save_complete_microsimulation_h5(
            _SkippingSimulation(),
            tmp_path / "scenario.h5",
            year=2075,
            fail_on_empty_entity=False,
            variables_by_entity={
                **_TEST_VARIABLES_BY_ENTITY,
                "person": [
                    *_TEST_VARIABLES_BY_ENTITY["person"],
                    "missing_person_variable",
                ],
            },
        )


def test_full_h5_paths_use_required_production_shape():
    path = reform_full_h5_artifact_dir(
        "/results/run",
        year=2100,
        reform_id="option12",
    )

    assert path == (
        Path("/results") / "run" / FULL_H5_DIRNAME / "year=2100" / "reform=option12"
    )


def test_full_h5_object_store_config_and_keys_use_full_h5_prefix():
    config = object_store_config_from_env(
        {
            "CRFB_R2_BUCKET": "bucket",
            "CRFB_R2_ACCOUNT_ID": "abc",
            "CRFB_R2_ACCESS_KEY_ID": "key",
            "CRFB_R2_SECRET_ACCESS_KEY": "secret",
            "CRFB_REFORM_FULL_H5_OBJECT_STORE_PREFIX": "crfb/full",
        }
    )

    assert config is not None
    assert config.endpoint_url == "https://abc.r2.cloudflarestorage.com"
    assert object_store_keys(
        config=config,
        run_prefix="run1",
        year=2100,
        reform_id="option12",
    ) == (
        "crfb/full/run1/reform_full_h5/year=2100/reform=option12/scenario.h5",
        "crfb/full/run1/reform_full_h5/year=2100/reform=option12/metadata.json",
    )


def test_object_store_target_must_match_approved_r2_prefix():
    config = ObjectStoreConfig(
        bucket="bucket",
        endpoint_url="https://example.com",
        region_name="auto",
        access_key_id="key",
        secret_access_key="secret",
        prefix="crfb/full",
    )

    assert validate_object_store_target_matches_approval(
        config=config,
        run_prefix="run1",
        year=2100,
        reform_id="option12",
        approved_target="r2://bucket/crfb/full",
    ) == (
        "crfb/full/run1/reform_full_h5/year=2100/reform=option12/scenario.h5",
        "crfb/full/run1/reform_full_h5/year=2100/reform=option12/metadata.json",
    )

    with pytest.raises(RuntimeError, match="outside approved durable target"):
        validate_object_store_target_matches_approval(
            config=config,
            run_prefix="run1",
            year=2100,
            reform_id="option12",
            approved_target="r2://bucket/other/prefix",
        )


def test_baseline_dataset_manifest_validates_year_h5_sha(tmp_path: Path):
    dataset = tmp_path / "enhanced_cps_2100.h5"
    output = tmp_path / "scenario.h5"
    save_complete_microsimulation_h5(
        _Simulation(),
        dataset,
        year=2100,
        fail_on_empty_entity=False,
        variables_by_entity=_TEST_VARIABLES_BY_ENTITY,
    )
    metadata = tmp_path / "enhanced_cps_2100.h5.metadata.json"
    metadata.write_text(
        (
            '{"tax_assumption": {"name": "trustees-2025-core-thresholds-v1", '
            '"start_year": 2035, "end_year": 2100}}\n'
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "baseline-datasets.json"
    manifest.write_text(
        (
            '{"datasets": [{"year": 2100, "h5_sha256": "'
            + __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()
            + '", "metadata_path": "enhanced_cps_2100.h5.metadata.json", '
            + '"metadata_sha256": "'
            + __import__("hashlib").sha256(metadata.read_bytes()).hexdigest()
            + '"}]}\n'
        ),
        encoding="utf-8",
    )

    result = validate_baseline_dataset_against_manifest(
        dataset_path=dataset,
        year=2100,
        manifest_path=manifest,
        approved_manifest_sha256=__import__("hashlib")
        .sha256(manifest.read_bytes())
        .hexdigest(),
    )

    assert result["validated"] is True
    assert result["year"] == 2100
    assert output.name == "scenario.h5"


def test_baseline_dataset_manifest_rejects_wrong_h5_sha(tmp_path: Path):
    dataset = tmp_path / "enhanced_cps_2100.h5"
    save_complete_microsimulation_h5(
        _Simulation(),
        dataset,
        year=2100,
        fail_on_empty_entity=False,
        variables_by_entity=_TEST_VARIABLES_BY_ENTITY,
    )
    manifest = tmp_path / "baseline-datasets.json"
    manifest.write_text(
        '{"datasets": [{"year": 2100, "h5_sha256": "bad"}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Baseline dataset H5 SHA"):
        validate_baseline_dataset_against_manifest(
            dataset_path=dataset,
            year=2100,
            manifest_path=manifest,
            approved_manifest_sha256=__import__("hashlib")
            .sha256(manifest.read_bytes())
            .hexdigest(),
        )


def test_full_h5_worker_does_not_import_legacy_aggregate_path():
    source = Path("src/reform_full_h5_worker.py").read_text(encoding="utf-8")

    required = [
        "expected_schema_manifest_path is required for approved runs.",
        "load_expected_schema_manifest(expected_schema_manifest_path)",
        "validate_full_h5_against_expected_schema(",
        "validate_baseline_dataset_against_manifest(",
        "preflight_validated_before_microsimulation",
    ]
    for text in required:
        assert text in source
    assert source.index(
        "load_expected_schema_manifest(expected_schema_manifest_path)"
    ) < source.index("policy_reform = build_policy_reform")
    assert source.index(
        "Object-store config is required for production H5 cells."
    ) < source.index("policy_reform = build_policy_reform")

    forbidden = [
        "load_baseline",
        "validate_baseline_reconciliation",
        "compute_scenario_household_metrics",
        "compute_reform_result",
        "from .year_runner",
        "from year_runner",
    ]
    for text in forbidden:
        assert text not in source
