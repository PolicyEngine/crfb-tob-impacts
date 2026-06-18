from __future__ import annotations

import ast
from pathlib import Path


def test_local_static_panel_runner_is_archived_and_fail_closed():
    source = Path("scripts/run_local_static_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "archived and fail-closed" in source
    assert "reform_full_h5" in source
    assert "compute_reform_result" not in source
    assert "load_baseline" not in source
    assert [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "src.year_runner"
    ] == []
