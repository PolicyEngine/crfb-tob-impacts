"""Archived aggregate-only selected-cell Modal runner.

This historical runner produced aggregate records without persisting full
reform-output H5 artifacts. It is fail-closed so paid production scoring uses
``modal_batch/reform_full_h5.py::submit_reform_full_h5`` only.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "modal_batch/run_panel.py is archived and fail-closed. Use "
        "modal_batch/reform_full_h5.py::submit_reform_full_h5 for full-H5 "
        "reform production."
    )


if __name__ == "__main__":
    main()
