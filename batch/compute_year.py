#!/usr/bin/env python3
"""Archived Google Cloud Batch year worker.

This historical worker rebuilt baselines and wrote aggregate CSVs through the
old GCS batch path. It is fail-closed so there is a single production route for
current CRFB results.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "batch/compute_year.py is archived and fail-closed. Use "
        "modal_batch/reform_full_h5.py for current full-H5 scoring. Use "
        "analysis/balanced_fix_recompute_spec.md for balanced-fix work."
    )


if __name__ == "__main__":
    main()
