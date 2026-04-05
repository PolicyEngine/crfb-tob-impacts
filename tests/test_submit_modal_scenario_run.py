from __future__ import annotations

import pytest
from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_build_submitted_record_captures_call_metadata():
    import modal_run_submit as module

    cell = {"year": 2026, "scenario_name": "option1", "reform_id": "option1"}

    record = module.build_submitted_record(
        cell,
        "fc-abc",
        "https://modal.com/apps/policyengine/main/ap-abc?function=fc-abc",
        "2026-04-05T13:30:00+00:00",
        startup_confirmed=True,
        function_name="materialize_scenario_from_run",
    )

    assert record == {
        "year": 2026,
        "scenario_name": "option1",
        "reform_id": "option1",
        "launched_at": "2026-04-05T13:30:00+00:00",
        "call_id": "fc-abc",
        "dashboard_url": "https://modal.com/apps/policyengine/main/ap-abc?function=fc-abc",
        "function_name": "materialize_scenario_from_run",
        "submission_mode": "deployed_function_spawn",
        "startup_confirmed": True,
    }


def test_build_modal_spawn_command_targets_remote_function():
    import modal_run_submit as module

    cell = {
        "run_id": "run123",
        "year": 2026,
        "scenario_name": "option1",
        "reform_id": "option1",
    }

    command = module.build_modal_spawn_command(cell, worker_profile="large")

    assert command[0].endswith("uv")
    assert command[1:7] == [
        "run",
        "--with",
        "modal",
        "--with",
        "pandas",
        "python",
    ]
    assert any(entry.endswith("src/modal_spawn_deployed_call.py") for entry in command)
    assert "--app-name" in command and "crfb-ss-analysis" in command
    assert "--function-name" in command
    assert "materialize_scenario_from_run" in command
    assert "--run-id" in command and "run123" in command
    assert "--year" in command and "2026" in command
    assert "--scenario-name" in command and "option1" in command
    assert "--reform-id" in command


def test_build_modal_spawn_command_targets_small_profile():
    import modal_run_submit as module

    cell = {
        "run_id": "run123",
        "year": 2026,
        "scenario_name": "baseline",
        "reform_id": None,
    }

    command = module.build_modal_spawn_command(cell, worker_profile="small")

    assert "materialize_scenario_from_run_small" in command
    assert "--reform-id" not in command


def test_modal_worker_target_profiles():
    import modal_run_submit as module

    assert module.modal_worker_target("large") == "materialize_scenario_from_run"
    assert (
        module.modal_worker_target("medium")
        == "materialize_scenario_from_run_medium"
    )
    assert module.modal_worker_target("small") == "materialize_scenario_from_run_small"


def test_build_modal_deploy_command_targets_compute_app():
    import modal_run_submit as module

    command = module.build_modal_deploy_command()

    assert command[0].endswith("uvx")
    assert command[1:6] == [
        "--from",
        "modal",
        "--with",
        "pandas",
        "modal",
    ]
    assert command[6] == "deploy"
    assert command[7].endswith("modal_batch/compute.py")
    assert command[8] == "--no-stream-logs"


def test_parse_spawn_record_reads_json_payload_with_noise():
    import modal_run_submit as module

    payload = module.parse_spawn_record(
        "Installed 39 packages in 327ms\n"
        '{"call_id":"fc-123","dashboard_url":"https://modal.com/x","function_name":"materialize_scenario_from_run"}\n'
    )

    assert payload == {
        "call_id": "fc-123",
        "dashboard_url": "https://modal.com/x",
        "function_name": "materialize_scenario_from_run",
    }


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
