from __future__ import annotations

import pytest
from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_build_submitted_record_captures_app_metadata():
    import modal_run_submit as module

    cell = {"year": 2026, "scenario_name": "option1", "reform_id": "option1"}

    record = module.build_submitted_record(
        cell,
        "ap-abc",
        "https://modal.com/apps/policyengine/main/ap-abc",
        "2026-04-05T13:30:00+00:00",
        startup_confirmed=True,
    )

    assert record == {
        "year": 2026,
        "scenario_name": "option1",
        "reform_id": "option1",
        "launched_at": "2026-04-05T13:30:00+00:00",
        "app_id": "ap-abc",
        "dashboard_url": "https://modal.com/apps/policyengine/main/ap-abc",
        "startup_confirmed": True,
    }


def test_build_modal_command_targets_remote_function():
    import modal_run_submit as module

    cell = {
        "run_id": "run123",
        "year": 2026,
        "scenario_name": "option1",
        "reform_id": "option1",
    }

    command = module.build_modal_command(cell)

    assert command[0].endswith("uvx")
    assert command[1:8] == [
        "--from",
        "modal",
        "--with",
        "pandas",
        "modal",
        "run",
        "--detach",
    ]
    assert any(
        entry.endswith("modal_batch/compute.py::materialize_scenario_from_run")
        for entry in command
    )
    assert "--run-id" in command and "run123" in command
    assert "--year" in command and "2026" in command
    assert "--scenario-name" in command and "option1" in command
    assert "--reform-id" in command


def test_parse_app_id_reads_modal_output():
    import modal_run_submit as module

    app_id = module.parse_app_id(
        "Initialized.\nView run at https://modal.com/apps/policyengine/main/ap-abc\n"
    )

    assert app_id == "ap-abc"


def test_build_launch_failure_record_is_stable():
    import modal_run_submit as module

    cell = {"year": 2030, "scenario_name": "baseline", "reform_id": None}

    record = module.build_launch_failure_record(
        cell,
        "2026-04-05T13:31:00+00:00",
        ValueError("boom"),
    )

    assert record == {
        "year": 2030,
        "scenario_name": "baseline",
        "reform_id": None,
        "launched_at": "2026-04-05T13:31:00+00:00",
        "error": "ValueError: boom",
    }


def test_build_run_spec_rejects_no_baseline():
    import modal_run_submit as module

    args = SimpleNamespace(
        include_baseline=False,
        reforms="option1",
        years="2026",
        projected_datasets_path=Path("/tmp"),
        snapshot_path=Path("/tmp"),
        tax_assumption_module=None,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="exact",
        required_target_source="oact_2025_08_05_provisional",
        required_tax_assumption="trustees-core-thresholds-v1",
        label="test",
        scoring="static",
        tax_assumption_factory="factory",
        tax_assumption_start_year=2035,
        tax_assumption_end_year=2100,
        output_root="/tmp",
        policyengine_us_path=Path("/tmp"),
    )

    try:
        module.build_run_spec(args)
    except ValueError as error:
        assert "require baseline" in str(error)
    else:
        raise AssertionError("Expected build_run_spec to reject baseline-free runs")


def test_prepare_snapshot_path_defaults_to_distinct_immutable_dir(tmp_path: Path):
    from projected_dataset_snapshot import prepare_snapshot_path

    live = tmp_path / "projected_datasets"
    live.mkdir()

    snapshot = prepare_snapshot_path(
        live,
        None,
        repo_root=tmp_path,
        label="Long Run Batch",
    )

    assert snapshot.parent == tmp_path / "projected_datasets_snapshots"
    assert snapshot != live
    assert snapshot.name.startswith("Long-Run-Batch_")


def test_prepare_snapshot_path_rejects_live_projected_dataset_root(tmp_path: Path):
    from projected_dataset_snapshot import prepare_snapshot_path

    live = tmp_path / "projected_datasets"
    live.mkdir()

    with pytest.raises(
        ValueError,
        match="distinct from the live projected datasets path",
    ):
        prepare_snapshot_path(
            live,
            live,
            repo_root=tmp_path,
            label="test",
        )
