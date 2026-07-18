"""Archived local aggregate-only static/behavioral panel runner.

This script produced aggregate CSV rows without first creating durable full
reform-output H5 artifacts. It is fail-closed so production results come only
from approved ``reform_full_h5`` cells.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> int:
    raise RuntimeError(
        "scripts/run_local_static_panel.py is archived and fail-closed. "
        "Aggregate results from approved reform_full_h5 artifacts instead."
    )


if __name__ == "__main__":
    raise SystemExit(main())
