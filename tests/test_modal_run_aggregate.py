from __future__ import annotations
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_ensure_aggregatable_run_rejects_missing_baseline(tmp_path: Path):
    from modal_run_aggregate import ensure_aggregatable_run

    manifest = {
        "run_id": "run123",
        "include_baseline": False,
        "cells": [],
    }

    try:
        ensure_aggregatable_run(tmp_path, manifest, allow_incomplete=False)
    except ValueError as error:
        assert "without baseline" in str(error)
    else:
        raise AssertionError("Expected missing-baseline run to be rejected")


def test_ensure_aggregatable_run_rejects_pending_cells(tmp_path: Path):
    from modal_run_aggregate import ensure_aggregatable_run
    from modal_run_protocol import build_cells, scenario_artifact_paths, within_run_root

    manifest = {
        "run_id": "run123",
        "include_baseline": True,
        "cells": build_cells(
            years=[2026],
            reforms=["option1"],
            include_baseline=True,
        ),
    }

    baseline_paths = scenario_artifact_paths("run123", 2026, "baseline")
    (tmp_path / within_run_root("run123", baseline_paths["submitted"])).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / within_run_root("run123", baseline_paths["submitted"])).write_text("{}")

    try:
        ensure_aggregatable_run(tmp_path, manifest, allow_incomplete=False)
    except ValueError as error:
        assert "incomplete" in str(error)
    else:
        raise AssertionError("Expected pending cells to be rejected")


def test_load_weights_reads_recovered_weight_bundle(tmp_path: Path):
    import numpy as np

    from modal_run_aggregate import load_weights

    weights_path = tmp_path / "weights.npz"
    np.savez_compressed(
        weights_path,
        household_ids=np.asarray([1, 2]),
        household_weights=np.asarray([0.25, 0.75]),
    )

    household_ids, household_weights = load_weights(weights_path)

    assert household_ids.tolist() == [1, 2]
    assert household_weights.tolist() == [0.25, 0.75]
