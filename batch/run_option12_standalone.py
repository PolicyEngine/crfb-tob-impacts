#!/usr/bin/env python3
"""Archived standalone Option 12 Modal runner.

This historical runner used a non-canonical current-law microsimulation path
and wrote old special-case artifacts. It is fail-closed because current Option
12 results must come from the canonical full-H5 static/behavioral pipeline.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "batch/run_option12_standalone.py is archived and fail-closed. Use "
        "the canonical full-H5 static/behavioral pipeline for Option 12."
    )


if __name__ == "__main__":
    main()
