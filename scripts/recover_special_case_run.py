#!/usr/bin/env python3
"""Archived special-case recovery helper.

This historical helper recovered Option 13/14 artifacts from old Modal volume
prefixes. It is fail-closed because those artifacts are outside the current
certified CRFB pipeline.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "scripts/recover_special_case_run.py is archived and fail-closed. Use "
        "analysis/balanced_fix_recompute_spec.md for current balanced-fix work."
    )


if __name__ == "__main__":
    main()
