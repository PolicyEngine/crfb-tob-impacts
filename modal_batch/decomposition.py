"""Archived aggregate-only TOB decomposition Modal runner.

This historical runner launched paid Modal cells that wrote decomposition JSON
without persisting full reform-output H5 artifacts. It is fail-closed so
production work derives trust-fund split results from approved full-H5 outputs.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "modal_batch/decomposition.py is archived and fail-closed. Derive "
        "decomposition from approved reform_full_h5 artifacts instead of "
        "launching aggregate-only Modal cells."
    )


if __name__ == "__main__":
    main()
