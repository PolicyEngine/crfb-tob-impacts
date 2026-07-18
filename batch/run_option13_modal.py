#!/usr/bin/env python3
"""Archived Option 13/14 Modal runner.

This historical runner targeted an old baseline/runtime and must not be used
for current CRFB work. Git history retains the old implementation if it is ever
needed for archaeology.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "batch/run_option13_modal.py is archived and fail-closed. Use "
        "analysis/balanced_fix_recompute_spec.md to rebuild balanced-fix "
        "scoring on the current certified base."
    )


if __name__ == "__main__":
    main()
