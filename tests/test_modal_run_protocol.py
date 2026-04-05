from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
import sys
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_build_cells_includes_baseline_then_reforms():
    from modal_run_protocol import BASELINE_SCENARIO, build_cells

    cells = build_cells(years=[2035], reforms=["option1", "option2"], include_baseline=True)

    assert cells == [
        {"year": 2035, "scenario_name": BASELINE_SCENARIO, "reform_id": None},
        {"year": 2035, "scenario_name": "option1", "reform_id": "option1"},
        {"year": 2035, "scenario_name": "option2", "reform_id": "option2"},
    ]


def test_within_run_root_strips_remote_prefix():
    from modal_run_protocol import scenario_artifact_paths, within_run_root

    remote_path = scenario_artifact_paths("run123", 2035, "option1")["metrics"]

    assert remote_path == Path(
        "runs/run123/scenarios/year=2035/scenario=option1/metrics.npz"
    )
    assert within_run_root("run123", remote_path) == Path(
        "scenarios/year=2035/scenario=option1/metrics.npz"
    )


def test_summarize_run_directory_counts_success_error_and_pending(tmp_path: Path):
    from modal_run_protocol import (
        BASELINE_SCENARIO,
        build_cells,
        scenario_artifact_paths,
        summarize_run_directory,
        within_run_root,
    )

    manifest = {
        "run_id": "run123",
        "cells": build_cells(
            years=[2035],
            reforms=["option1", "option2"],
            include_baseline=True,
        ),
    }

    baseline_paths = scenario_artifact_paths("run123", 2035, BASELINE_SCENARIO)
    option1_paths = scenario_artifact_paths("run123", 2035, "option1")
    option2_paths = scenario_artifact_paths("run123", 2035, "option2")

    (tmp_path / within_run_root("run123", baseline_paths["success"])).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / within_run_root("run123", baseline_paths["success"])).write_text("{}")

    (tmp_path / within_run_root("run123", option1_paths["error"])).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / within_run_root("run123", option1_paths["error"])).write_text("{}")

    (tmp_path / within_run_root("run123", option2_paths["submitted"])).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / within_run_root("run123", option2_paths["submitted"])).write_text("{}")

    (tmp_path / within_run_root("run123", option2_paths["started"])).write_text("{}")

    summary = summarize_run_directory(tmp_path, manifest)

    assert summary["expected_cells"] == 3
    assert summary["completed_cells"] == 1
    assert summary["failed_cells"] == 1
    assert summary["running_cells"] == 1
    assert summary["submitted_cells"] == 0
    assert summary["missing_cells"] == 0
    assert summary["pending_cells"] == 1


def test_summarize_run_directory_distinguishes_submitted_from_missing(tmp_path: Path):
    from modal_run_protocol import (
        build_cells,
        scenario_artifact_paths,
        summarize_run_directory,
        within_run_root,
    )

    manifest = {
        "run_id": "run123",
        "cells": build_cells(
            years=[2035],
            reforms=["option1", "option2"],
            include_baseline=False,
        ),
    }

    option1_paths = scenario_artifact_paths("run123", 2035, "option1")

    (tmp_path / within_run_root("run123", option1_paths["submitted"])).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / within_run_root("run123", option1_paths["submitted"])).write_text("{}")

    summary = summarize_run_directory(tmp_path, manifest)

    assert summary["expected_cells"] == 2
    assert summary["completed_cells"] == 0
    assert summary["failed_cells"] == 0
    assert summary["running_cells"] == 0
    assert summary["submitted_cells"] == 1
    assert summary["missing_cells"] == 1
    assert summary["pending_cells"] == 2


def test_build_run_id_uses_nonce_to_avoid_same_second_collisions():
    import modal_run_protocol as module

    payload = {"reforms": ["option1"], "years": [2026]}

    with patch.object(module, "datetime") as mock_datetime, patch.object(
        module.secrets,
        "token_hex",
        side_effect=["abc123", "def456"],
    ):
        mock_datetime.now.return_value = datetime(2026, 4, 5, 12, 0, 0, tzinfo=UTC)
        run_id_one = module.build_run_id("same label", payload)
        run_id_two = module.build_run_id("same label", payload)

    assert run_id_one != run_id_two
    assert run_id_one.endswith("_abc123")
    assert run_id_two.endswith("_def456")
