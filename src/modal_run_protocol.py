from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
import re
import secrets
from typing import Any


BASELINE_SCENARIO = "baseline"


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    root: Path
    manifest: Path


def parse_years(years: str) -> list[int]:
    if "-" in years:
        start, end = years.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(year.strip()) for year in years.split(",") if year.strip()]


def parse_reforms(reforms: str) -> list[str]:
    return [reform.strip() for reform in reforms.split(",") if reform.strip()]


def scenario_name(reform_id: str | None) -> str:
    return BASELINE_SCENARIO if reform_id is None else reform_id


def scenario_slug(name: str) -> str:
    return name.replace("/", "_")


def build_cells(
    *,
    years: list[int],
    reforms: list[str],
    include_baseline: bool,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for year in years:
        if include_baseline:
            cells.append(
                {
                    "year": year,
                    "scenario_name": BASELINE_SCENARIO,
                    "reform_id": None,
                }
            )
        for reform_id in reforms:
            cells.append(
                {
                    "year": year,
                    "scenario_name": scenario_name(reform_id),
                    "reform_id": reform_id,
                }
            )
    return cells


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def spec_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_run_id(label: str, payload: dict[str, Any]) -> str:
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") or "modal-scenarios"
    created_at = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    nonce = secrets.token_hex(3)
    return f"{safe_label}_{created_at}_{spec_hash(payload)[:10]}_{nonce}"


def run_root(run_id: str) -> Path:
    return Path("runs") / run_id


def run_paths(run_id: str) -> RunPaths:
    root = run_root(run_id)
    return RunPaths(
        run_id=run_id,
        root=root,
        manifest=root / "manifest.json",
    )


def scenario_root(run_id: str, year: int, scenario: str) -> Path:
    return run_root(run_id) / "scenarios" / f"year={year}" / f"scenario={scenario_slug(scenario)}"


def scenario_artifact_paths(run_id: str, year: int, scenario: str) -> dict[str, Path]:
    root = scenario_root(run_id, year, scenario)
    return {
        "root": root,
        "submitted": root / "submitted.json",
        "started": root / "started.json",
        "metrics": root / "metrics.npz",
        "metadata": root / "metadata.json",
        "success": root / "success.json",
        "error": root / "error.json",
    }


def year_artifact_root(run_id: str, year: int) -> Path:
    return run_root(run_id) / "years" / f"year={year}"


def year_artifact_paths(run_id: str, year: int) -> dict[str, Path]:
    root = year_artifact_root(run_id, year)
    return {
        "root": root,
        "weights": root / "weights.npz",
        "metadata": root / "weights_metadata.json",
    }


def within_run_root(run_id: str, path: Path) -> Path:
    return path.relative_to(run_root(run_id))


def summarize_run_directory(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    cells = manifest.get("cells", [])
    dispatch_path = run_dir / "dispatch.json"
    dispatch_payload: dict[str, Any] = {}
    if dispatch_path.exists():
        dispatch_payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
    dispatched_cells = {
        (int(record["year"]), str(record["scenario_name"])): record
        for record in dispatch_payload.get("submitted", [])
    }
    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    running: list[dict[str, Any]] = []
    submitted: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    run_id = manifest["run_id"]
    for cell in cells:
        paths = scenario_artifact_paths(
            run_id,
            int(cell["year"]),
            str(cell["scenario_name"]),
        )
        submitted_path = run_dir / within_run_root(run_id, paths["submitted"])
        success_path = run_dir / within_run_root(run_id, paths["success"])
        error_path = run_dir / within_run_root(run_id, paths["error"])
        started_path = run_dir / within_run_root(run_id, paths["started"])
        if success_path.exists():
            completed.append(cell)
        elif error_path.exists():
            failed.append(cell)
        elif started_path.exists():
            running.append(cell)
        elif submitted_path.exists() or (
            int(cell["year"]),
            str(cell["scenario_name"]),
        ) in dispatched_cells:
            submitted.append(cell)
        else:
            missing.append(cell)

    return {
        "expected_cells": len(cells),
        "completed_cells": len(completed),
        "failed_cells": len(failed),
        "running_cells": len(running),
        "submitted_cells": len(submitted),
        "missing_cells": len(missing),
        "pending_cells": len(running) + len(submitted) + len(missing),
        "completed": completed,
        "failed": failed,
        "running": running,
        "submitted": submitted,
        "missing": missing,
        "pending": [*running, *submitted, *missing],
    }
