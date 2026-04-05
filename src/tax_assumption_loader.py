from __future__ import annotations

import importlib.util
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_TAX_ASSUMPTION_FACTORY = "create_wage_indexed_core_thresholds_reform"


def candidate_tax_assumption_modules() -> list[Path]:
    return [
        Path.home()
        / ".codex-worktrees"
        / "us-data-calibration-contract"
        / "policyengine_us_data"
        / "datasets"
        / "cps"
        / "long_term"
        / "tax_assumptions.py",
        WORKSPACE_ROOT
        / "policyengine-us-data"
        / "policyengine_us_data"
        / "datasets"
        / "cps"
        / "long_term"
        / "tax_assumptions.py",
    ]


def resolve_tax_assumption_module(module_path: str | Path | None = None) -> Path:
    if module_path is None:
        module_path = os.environ.get("CRFB_TAX_ASSUMPTION_MODULE")

    if module_path:
        path = Path(module_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    for candidate in candidate_tax_assumption_modules():
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Could not resolve a tax assumption module. "
        "Pass a module path or set CRFB_TAX_ASSUMPTION_MODULE."
    )


def load_tax_assumption_reform(
    module_path: Path,
    factory_name: str,
    start_year: int,
    end_year: int,
):
    spec = importlib.util.spec_from_file_location("tax_assumptions", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tax assumption module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, factory_name)
    return factory(start_year=start_year, end_year=end_year)
