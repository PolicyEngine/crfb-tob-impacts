"""Guards for the public paper at /us/taxation-of-benefits-reforms/paper/.

The paper's generated exhibits must match what the generators produce from
the committed results panel, and the reform count the paper states must match
the reforms the dashboard menu offers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scripts import generate_paper_static_exhibits as exhibits

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SHELL = REPO_ROOT / "dashboard" / "src" / "components" / "dashboard-shell.tsx"
EXHIBIT_DIRS = (
    REPO_ROOT / "paper" / "exhibits",
    REPO_ROOT / "paper" / "sections" / "exhibits",
)


def dashboard_menu_ids() -> set[str]:
    shell = DASHBOARD_SHELL.read_text(encoding="utf-8")
    ids: set[str] = set()
    for name in ("BENEFIT_RULE_IDS", "STRUCTURAL_IDS"):
        match = re.search(rf"const {name} = \[(.*?)\];", shell, re.DOTALL)
        assert match, f"{name} not found in dashboard-shell.tsx"
        ids.update(re.findall(r'"([a-z0-9_]+)"', match.group(1)))
    return ids


def test_committed_exhibits_match_generator() -> None:
    for name, text in exhibits.render_all().items():
        for directory in EXHIBIT_DIRS:
            committed = (directory / name).read_text(encoding="utf-8")
            assert committed == text, (
                f"{directory.name}/{name} is stale; run "
                "scripts/generate_paper_static_exhibits.py"
            )


def test_menu_reforms_match_dashboard_and_panel() -> None:
    static = pd.read_csv(exhibits.RESULTS_CSV)
    static = static[static["scoring_type"] == "static"]
    scored = set(static["reform_name"])

    assert set(exhibits.STANDARD_REFORMS) == scored
    assert set(exhibits.MENU_REFORMS) == dashboard_menu_ids()
    assert set(exhibits.MENU_REFORMS) == scored - set(exhibits.SENSITIVITY_REFORMS)
    assert len(exhibits.MENU_REFORMS) == 15
