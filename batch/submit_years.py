#!/usr/bin/env python3
"""Archived Google Cloud Batch submitter.

This historical submitter launched the pre-v2 year-worker pipeline and wrote
old CSV aggregates to GCS. It is fail-closed so production scoring uses the
canonical full-H5 Modal pipeline only.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "batch/submit_years.py is archived and fail-closed. Use "
        "modal_batch/reform_full_h5.py for full-H5 reform production."
    )


if __name__ == "__main__":
    main()
