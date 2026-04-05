from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

from modal_run_protocol import scenario_artifact_paths, within_run_root


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds(), 3)


def build_timing_rows(
    run_dir: Path,
    manifest: dict[str, Any],
    *,
    collected_at: datetime | None = None,
) -> list[dict[str, Any]]:
    collected = collected_at or datetime.now(UTC)
    run_id = str(manifest["run_id"])
    execution = manifest.get("execution", {})
    dispatch_path = run_dir / "dispatch.json"
    dispatch_payload: dict[str, Any] = {}
    if dispatch_path.exists():
        dispatch_payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    dispatch_submitted = {
        (int(record["year"]), str(record["scenario_name"])): record
        for record in dispatch_payload.get("submitted", [])
    }
    rows: list[dict[str, Any]] = []

    for cell in manifest.get("cells", []):
        year = int(cell["year"])
        scenario_name = str(cell["scenario_name"])
        reform_id = cell.get("reform_id")
        path_map = scenario_artifact_paths(run_id, year, scenario_name)

        submitted = _load_json(
            run_dir / within_run_root(run_id, path_map["submitted"])
        )
        if submitted is None:
            submitted = dispatch_submitted.get((year, scenario_name))
        started = _load_json(run_dir / within_run_root(run_id, path_map["started"]))
        success = _load_json(run_dir / within_run_root(run_id, path_map["success"]))
        error = _load_json(run_dir / within_run_root(run_id, path_map["error"]))

        launched_at = _parse_timestamp(
            (submitted or {}).get("launched_at")
            or manifest.get("created_at")
        )
        started_at = _parse_timestamp((started or {}).get("started_at"))
        completed_at = _parse_timestamp((success or {}).get("completed_at"))
        failed_at = _parse_timestamp((error or {}).get("failed_at"))

        status = "missing"
        if success is not None:
            status = "completed"
        elif error is not None:
            status = "failed"
        elif started is not None:
            status = "running"
        elif submitted is not None:
            status = "submitted"

        row: dict[str, Any] = {
            "run_id": run_id,
            "year": year,
            "scenario_name": scenario_name,
            "reform_id": reform_id,
            "status": status,
            "modal_worker_profile": execution.get("modal_worker_profile"),
            "requested_cpu": execution.get("cpu"),
            "requested_memory_mb": execution.get("memory_mb"),
            "launched_at": launched_at.isoformat() if launched_at else None,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "failed_at": failed_at.isoformat() if failed_at else None,
            "app_id": (submitted or {}).get("app_id"),
            "call_id": (submitted or {}).get("call_id"),
            "function_name": (submitted or {}).get("function_name"),
            "submission_mode": (submitted or {}).get("submission_mode"),
            "startup_confirmed": (submitted or {}).get("startup_confirmed"),
            "launch_to_start_seconds": _seconds_between(launched_at, started_at),
            "start_to_complete_seconds": _seconds_between(started_at, completed_at),
            "launch_to_complete_seconds": _seconds_between(
                launched_at,
                completed_at,
            ),
            "launch_wait_so_far_seconds": None,
            "runtime_so_far_seconds": None,
        }
        if status == "submitted":
            row["launch_wait_so_far_seconds"] = _seconds_between(
                launched_at,
                collected,
            )
        elif status == "running":
            row["runtime_so_far_seconds"] = _seconds_between(started_at, collected)
        rows.append(row)

    return rows


def timing_dataframe(
    run_dir: Path,
    manifest: dict[str, Any],
    *,
    collected_at: datetime | None = None,
) -> pd.DataFrame:
    return pd.DataFrame(
        build_timing_rows(
            run_dir,
            manifest,
            collected_at=collected_at,
        )
    ).sort_values(["year", "scenario_name"]).reset_index(drop=True)
