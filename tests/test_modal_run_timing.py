from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_timing_dataframe_captures_wait_and_runtime(tmp_path: Path):
    from modal_run_protocol import scenario_artifact_paths, year_artifact_paths
    from modal_run_timing import timing_dataframe

    run_id = "timing-test"
    run_dir = tmp_path / run_id
    manifest = {
        "run_id": run_id,
        "created_at": "2026-04-05T18:40:00+00:00",
        "years": [2026],
        "reforms": ["option1"],
        "include_baseline": True,
        "execution": {
            "modal_worker_profile": "medium",
            "cpu": 4,
            "memory_mb": 32768,
        },
        "cells": [
            {"year": 2026, "scenario_name": "baseline", "reform_id": None},
            {"year": 2026, "scenario_name": "option1", "reform_id": "option1"},
        ],
    }
    _write_json(run_dir / "manifest.json", manifest)

    baseline_paths = scenario_artifact_paths(run_id, 2026, "baseline")
    _write_json(
        run_dir / baseline_paths["submitted"].relative_to(f"runs/{run_id}"),
        {
            "launched_at": "2026-04-05T18:40:10+00:00",
            "call_id": "fc-1",
            "function_name": "materialize_scenario_from_run_medium",
            "submission_mode": "deployed_function_spawn",
            "startup_confirmed": True,
        },
    )
    _write_json(
        run_dir / baseline_paths["started"].relative_to(f"runs/{run_id}"),
        {"started_at": "2026-04-05T18:40:20+00:00"},
    )
    _write_json(
        run_dir / baseline_paths["success"].relative_to(f"runs/{run_id}"),
        {"completed_at": "2026-04-05T18:41:50+00:00"},
    )

    reform_paths = scenario_artifact_paths(run_id, 2026, "option1")
    _write_json(
        run_dir / reform_paths["submitted"].relative_to(f"runs/{run_id}"),
        {
            "launched_at": "2026-04-05T18:40:15+00:00",
            "call_id": "fc-2",
            "function_name": "materialize_scenario_from_run_medium",
            "submission_mode": "deployed_function_spawn",
            "startup_confirmed": False,
        },
    )
    _write_json(
        run_dir / reform_paths["started"].relative_to(f"runs/{run_id}"),
        {"started_at": "2026-04-05T18:41:00+00:00"},
    )

    year_paths = year_artifact_paths(run_id, 2026)
    (run_dir / year_paths["weights"].relative_to(f"runs/{run_id}")).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = timing_dataframe(
        run_dir,
        manifest,
        collected_at=datetime(2026, 4, 5, 18, 42, 0, tzinfo=UTC),
    )

    baseline = df[df["scenario_name"] == "baseline"].iloc[0].to_dict()
    option1 = df[df["scenario_name"] == "option1"].iloc[0].to_dict()

    assert baseline["status"] == "completed"
    assert baseline["launch_to_start_seconds"] == 10.0
    assert baseline["start_to_complete_seconds"] == 90.0
    assert baseline["launch_to_complete_seconds"] == 100.0
    assert baseline["modal_worker_profile"] == "medium"
    assert baseline["requested_memory_mb"] == 32768
    assert baseline["call_id"] == "fc-1"
    assert baseline["function_name"] == "materialize_scenario_from_run_medium"
    assert baseline["submission_mode"] == "deployed_function_spawn"

    assert option1["status"] == "running"
    assert option1["launch_to_start_seconds"] == 45.0
    assert option1["runtime_so_far_seconds"] == 60.0
    assert option1["call_id"] == "fc-2"
    assert option1["startup_confirmed"] is False
