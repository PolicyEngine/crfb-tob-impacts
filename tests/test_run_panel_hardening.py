from __future__ import annotations

import ast
from pathlib import Path


def test_run_panel_is_archived_and_fail_closed():
    source = Path("modal_batch/run_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modal_imports = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Import)
            and any(alias.name == "modal" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "modal")
    ]

    assert "archived and fail-closed" in source
    assert "modal_batch/reform_full_h5.py::submit_reform_full_h5" in source
    assert modal_imports == []
    assert "modal.App" not in source
    assert "tmp/run_panel_raw.json" not in source
