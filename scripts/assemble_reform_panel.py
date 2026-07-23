"""Archived aggregate-JSON panel assembler (superseded by full-H5 publishers).

This script assembled the dashboard panel from per-cell aggregate score
JSONs and carried its own behavioral endpoint-ratio interpolation. The
release path is now ``publish_dashboard_results.py`` /
``publish_behavioral_endpoint_dashboard_results.py`` over durable
``reform_full_h5`` artifacts; the ratio edge cases this module tested are
covered by ``tests/test_behavioral_anchor_interpolation.py``. Fail-closed
per the retired-entry-point convention (2026-07 audit, cleanup A2).
"""

from __future__ import annotations


def main(*_args, **_kwargs) -> int:
    raise RuntimeError(
        "assemble_reform_panel.py is retired. Publish results with "
        "scripts/publish_dashboard_results.py (static + behavioral over "
        "reform_full_h5 cells); see docs/current/ for the release flow."
    )


if __name__ == "__main__":
    main()
