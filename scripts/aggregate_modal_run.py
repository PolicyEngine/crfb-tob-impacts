from __future__ import annotations
# ruff: noqa: E402

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_aggregate import main


if __name__ == "__main__":
    raise SystemExit(main())
