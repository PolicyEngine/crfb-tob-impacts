#!/usr/bin/env python3
"""Archived Option 14 Modal runner.

This historical runner targeted saved Option 13 parameters from an old
baseline/runtime and must not be used for current CRFB work.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "batch/run_option14_only.py is archived and fail-closed. Use "
        "analysis/balanced_fix_recompute_spec.md to rebuild balanced-fix "
        "comparisons on the current certified base."
    )


if __name__ == "__main__":
    main()
