from pathlib import Path

from src.modal_batch_helpers import (
    cell_output_paths,
    default_submission_manifest_path,
    object_store_key_for_path,
    parse_cells_file,
    parse_years,
    reform_household_metrics_artifact_dir,
    reform_household_metrics_requested,
    reform_household_metrics_start_year,
    reform_raw_h5_object_store_config,
)


def test_parse_years_supports_range_and_list():
    assert parse_years("2026-2028") == [2026, 2027, 2028]
    assert parse_years("2026, 2035,2100") == [2026, 2035, 2100]
    assert parse_years("2026-2028, 2035, 2040-2041") == [
        2026,
        2027,
        2028,
        2035,
        2040,
        2041,
    ]


def test_cell_output_paths_suffixes_scoring_and_creates_dir(tmp_path: Path):
    output_path, stem, output_dir = cell_output_paths(
        str(tmp_path / "conventional_probe.csv"), "conventional"
    )

    assert output_path == tmp_path / "conventional_probe.csv"
    assert stem == "conventional_probe_conventional"
    assert output_dir == tmp_path / "conventional_probe_conventional"
    assert output_dir.exists()


def test_default_submission_manifest_path_uses_modal_submissions():
    manifest_path = default_submission_manifest_path(
        Path("/tmp/project"),
        "conventional_probe_conventional",
        "demo",
    )

    assert manifest_path.name == "conventional_probe_conventional_demo.json"
    assert manifest_path.parent.name == "modal_submissions"


def test_parse_cells_file_supports_reform_name_and_dedupes(tmp_path: Path):
    cells_file = tmp_path / "cells.csv"
    cells_file.write_text(
        "reform_name,year\noption1,2026\noption1,2026\noption7,2100\n",
        encoding="utf-8",
    )

    assert parse_cells_file(cells_file) == [("option1", 2026), ("option7", 2100)]


def test_reform_household_metrics_start_year_can_disable_or_default():
    assert reform_household_metrics_start_year(None) == 2040
    assert reform_household_metrics_start_year("0") is None
    assert reform_household_metrics_start_year("off") is None
    assert reform_household_metrics_start_year("2055") == 2055


def test_reform_household_metrics_requested_uses_start_year():
    assert not reform_household_metrics_requested(2035, 2040)
    assert reform_household_metrics_requested(2040, 2040)
    assert not reform_household_metrics_requested(2100, None)


def test_reform_household_metrics_artifact_dir_normalizes_year_and_cell_paths():
    year_dir = reform_household_metrics_artifact_dir(
        "run-prefix",
        year=2040,
        reform_id="option1",
    )
    cell_dir = reform_household_metrics_artifact_dir(
        "run-prefix/option1/year_2040.csv",
        year=2040,
        reform_id="option1",
    )

    expected = (
        Path("/results")
        / "run-prefix"
        / "reform_household_metrics"
        / "year=2040"
        / "reform=option1"
    )
    assert year_dir == expected
    assert cell_dir == expected


def test_modal_compute_does_not_auto_mount_local_policyengine_us():
    compute_source = Path("modal_batch/compute.py").read_text(encoding="utf-8")

    assert '(CONTAINER_PROJECT_ROOT / "policyengine-us").exists()' not in compute_source
    assert "if EXPLICIT_POLICYENGINE_US_PATH and POLICYENGINE_US_PATH.exists()" in (
        compute_source
    )


def test_modal_compute_forwards_non_secret_raw_h5_object_store_env():
    compute_source = Path("modal_batch/compute.py").read_text(encoding="utf-8")

    assert '"CRFB_R2_BUCKET"' in compute_source
    assert '"CRFB_REFORM_RAW_H5_OBJECT_STORE_PREFIX"' in compute_source
    assert '"AWS_SECRET_ACCESS_KEY"' not in compute_source.split(
        "def _modal_image_contract_env", maxsplit=1
    )[1].split("return env", maxsplit=1)[0]


def test_reform_raw_h5_object_store_config_is_disabled_without_bucket():
    assert reform_raw_h5_object_store_config({}) is None


def test_reform_raw_h5_object_store_config_accepts_r2_aliases():
    config = reform_raw_h5_object_store_config(
        {
            "CRFB_R2_BUCKET": "crfb-artifacts",
            "CRFB_R2_ACCOUNT_ID": "abc123",
            "CRFB_R2_ACCESS_KEY_ID": "key",
            "CRFB_R2_SECRET_ACCESS_KEY": "secret",
            "CRFB_REFORM_RAW_H5_OBJECT_STORE_PREFIX": "runs/raw",
        }
    )

    assert config == {
        "bucket": "crfb-artifacts",
        "endpoint_url": "https://abc123.r2.cloudflarestorage.com",
        "region_name": "auto",
        "access_key_id": "key",
        "secret_access_key": "secret",
        "prefix": "runs/raw",
    }


def test_reform_raw_h5_object_store_config_fails_closed_when_incomplete():
    try:
        reform_raw_h5_object_store_config({"CRFB_R2_BUCKET": "crfb-artifacts"})
    except RuntimeError as error:
        assert "endpoint_url" in str(error)
        assert "access_key_id" in str(error)
        assert "secret_access_key" in str(error)
    else:
        raise AssertionError("Expected incomplete object-store config to fail")


def test_object_store_key_for_path_preserves_modal_volume_relative_path():
    key = object_store_key_for_path(
        "/results/run-prefix/reform_raw_h5/year=2040/reform=option1/scenario.h5",
        prefix="crfb/reform_raw_h5",
    )

    assert key == (
        "crfb/reform_raw_h5/run-prefix/reform_raw_h5/"
        "year=2040/reform=option1/scenario.h5"
    )
