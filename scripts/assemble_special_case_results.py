#!/usr/bin/env python3
"""Archived special-case assembly helper.

This historical helper assembled Option 13/14 CSV trees from old artifacts. It
is fail-closed because those artifacts are outside the current certified CRFB
pipeline.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "scripts/assemble_special_case_results.py is archived and fail-closed. "
        "Use analysis/balanced_fix_recompute_spec.md for current balanced-fix "
        "work."
    )


if __name__ == "__main__":
    main()
