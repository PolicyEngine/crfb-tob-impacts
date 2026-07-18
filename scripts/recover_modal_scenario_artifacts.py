#!/usr/bin/env python3
"""Archived scenario-artifact recovery helper.

This helper recovered the old scenario metrics/weights/aggregate artifacts.
Current CRFB scoring persists reform full-H5 outputs plus metadata and derives
aggregate tables downstream, so this path is archived and fail-closed.
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "scripts/recover_modal_scenario_artifacts.py is archived and fail-closed. "
        "Recover current outputs from "
        "reform_full_h5/year=YYYY/reform=OPTION/scenario.h5 plus metadata."
    )


if __name__ == "__main__":
    main()
