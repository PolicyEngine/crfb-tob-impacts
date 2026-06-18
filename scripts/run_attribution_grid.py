#!/usr/bin/env python3
"""Archived attribution-grid launcher.

This helper called a deleted Modal refresh path. It is fail-closed
so all selected-cell scoring goes through the canonical full-H5 panel runner.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "scripts/run_attribution_grid.py is archived and fail-closed. Use "
        "modal_batch/reform_full_h5.py for full-H5 reform production."
    )


if __name__ == "__main__":
    main()
