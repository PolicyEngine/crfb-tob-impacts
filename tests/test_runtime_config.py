from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime_config import dataset_path


def _write_dataset(
    base_dir: Path,
    year: int,
    *,
    profile_name: str = "ss-payroll-tob",
    fell_back_to_ipf: bool = False,
    calibration_quality: str = "exact",
    max_constraint_pct_error: float = 0.0,
) -> Path:
    dataset_file = base_dir / f"{year}.h5"
    dataset_file.write_text("", encoding="utf-8")
    metadata = {
        "year": year,
        "target_source": {
            "name": "trustees_2025_current_law",
        },
        "profile": {
            "name": profile_name,
            "calibration_method": "entropy",
            "max_age_error_pct": 0.1,
            "max_constraint_error_pct": 0.1,
            "max_negative_weight_pct": 0.0,
            "approximate_windows": [
                {
                    "start_year": 2076,
                    "end_year": 2078,
                    "max_constraint_error_pct": 0.5,
                    "max_age_error_pct": 0.5,
                    "max_negative_weight_pct": 0.0,
                },
                {
                    "start_year": 2079,
                    "end_year": 2085,
                    "max_constraint_error_pct": 5.0,
                    "max_age_error_pct": 5.0,
                    "max_negative_weight_pct": 0.0,
                },
                {
                    "start_year": 2086,
                    "end_year": 2095,
                    "max_constraint_error_pct": 20.0,
                    "max_age_error_pct": 20.0,
                    "max_negative_weight_pct": 0.0,
                },
                {
                    "start_year": 2096,
                    "end_year": None,
                    "max_constraint_error_pct": 35.0,
                    "max_age_error_pct": 35.0,
                    "max_negative_weight_pct": 0.0,
                },
            ],
            "use_ss": True,
            "use_payroll": True,
            "use_h6_reform": False,
            "use_tob": True,
        },
        "calibration_audit": {
            "calibration_quality": calibration_quality,
            "method_used": "entropy",
            "fell_back_to_ipf": fell_back_to_ipf,
            "age_max_pct_error": 0.0,
            "max_constraint_pct_error": max_constraint_pct_error,
            "negative_weight_pct": 0.0,
            "constraints": {
                "ss_total": {"pct_error": 0.0},
                "payroll_total": {"pct_error": max_constraint_pct_error},
                "oasdi_tob": {"pct_error": 0.0},
                "hi_tob": {"pct_error": 0.0},
            },
        },
    }
    (base_dir / f"{year}.h5.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    return dataset_file


def test_dataset_path_requires_metadata(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    (dataset_dir / "2026.h5").write_text("", encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_ALLOW_UNVALIDATED_DATASETS", raising=False)
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(FileNotFoundError, match="Dataset metadata missing"):
        dataset_path(2026)


def test_dataset_path_rejects_wrong_profile(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, profile_name="ss-payroll")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="expected 'ss-payroll-tob'"):
        dataset_path(2026)


def test_dataset_path_accepts_validated_dataset(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    expected = _write_dataset(dataset_dir, 2026)

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    assert dataset_path(2026) == str(expected)


def test_dataset_path_rejects_quality_below_minimum(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, calibration_quality="approximate")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)
    monkeypatch.delenv("CRFB_MIN_CALIBRATION_QUALITY", raising=False)

    with pytest.raises(ValueError, match="below required minimum 'exact'"):
        dataset_path(2026)


def test_dataset_path_rejects_constraint_error_above_profile(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, max_constraint_pct_error=0.2)

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="max_constraint_pct_error"):
        dataset_path(2026)


def test_dataset_path_rejects_wrong_target_source(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    expected = _write_dataset(dataset_dir, 2026)

    metadata_path = dataset_dir / "2026.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["target_source"]["name"] = "oact_2025_08_05_provisional"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_REQUIRED_TARGET_SOURCE", "trustees_2025_current_law")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="expected 'trustees_2025_current_law'"):
        dataset_path(2026)


def test_dataset_path_accepts_year_bounded_approximate_dataset(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    expected = _write_dataset(
        dataset_dir,
        2080,
        calibration_quality="approximate",
        max_constraint_pct_error=3.0,
    )

    metadata_path = dataset_dir / "2080.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["age_max_pct_error"] = 3.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_MIN_CALIBRATION_QUALITY", "approximate")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    assert dataset_path(2080) == str(expected)


def test_dataset_path_rejects_approximate_dataset_above_year_window(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(
        dataset_dir,
        2080,
        calibration_quality="approximate",
        max_constraint_pct_error=6.0,
    )

    metadata_path = dataset_dir / "2080.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["age_max_pct_error"] = 3.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_MIN_CALIBRATION_QUALITY", "approximate")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="max_constraint_pct_error"):
        dataset_path(2080)
