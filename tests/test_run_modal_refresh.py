from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_effective_modal_target_uses_detached_cell_entrypoint():
    import modal_refresh as module

    args = argparse.Namespace(detach=True, modal_target="run_cells")

    assert module.effective_modal_target(args) == "run_cells_detached"


def test_effective_modal_target_leaves_other_modes_unchanged():
    import modal_refresh as module

    attached = argparse.Namespace(detach=False, modal_target="run_cells")
    detached_year = argparse.Namespace(detach=True, modal_target="run_reforms")

    assert module.effective_modal_target(attached) == "run_cells"
    assert module.effective_modal_target(detached_year) == "run_reforms"
