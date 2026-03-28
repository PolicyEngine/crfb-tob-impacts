from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_DATASET_TEMPLATE = "hf://policyengine/test/no-h6/{year}.h5"


def dataset_path(year: int, default_template: str = DEFAULT_DATASET_TEMPLATE) -> str:
    template = os.environ.get("CRFB_DATASET_TEMPLATE", default_template)
    return template.format(year=year)


def _first_existing_path(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_policyengine_us_path() -> Path:
    env_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_POLICYENGINE_US_PATH does not exist: {path}"
            )
        return path

    candidate = _first_existing_path(
        (
            WORKSPACE_ROOT / "policyengine-us-6830-port",
            WORKSPACE_ROOT / "policyengine-us",
        )
    )
    if candidate is not None:
        return candidate

    raise FileNotFoundError(
        "Could not resolve policyengine-us checkout. "
        "Set CRFB_POLICYENGINE_US_PATH or place a checkout at "
        f"{WORKSPACE_ROOT / 'policyengine-us-6830-port'} or "
        f"{WORKSPACE_ROOT / 'policyengine-us'}."
    )


def resolve_projected_datasets_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_PROJECTED_DATASETS_PATH does not exist: {path}"
            )
        return path

    path = WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets"
    if not path.exists():
        raise FileNotFoundError(
            "Could not resolve projected_datasets. "
            "Set CRFB_PROJECTED_DATASETS_PATH or build datasets at "
            f"{path}."
        )
    return path


def resolve_projected_datasets_snapshot_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH")
    if env_path:
        return Path(env_path)

    return WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets_snapshot"
