from __future__ import annotations

import argparse
import sys

from . import (
    dashboard_baseline_assumptions,
    reform_full_h5_artifacts,
    repro_bundle_cli,
    selected_cells,
)


def _run_dashboard_baseline_assumptions(
    args: argparse.Namespace,
    remaining: list[str],
) -> int:
    forwarded: list[str] = []
    for metadata_root in args.metadata_root:
        forwarded.extend(["--metadata-root", str(metadata_root)])
    if args.policyengine_us_path is not None:
        forwarded.extend(["--policyengine-us-path", str(args.policyengine_us_path)])
    forwarded.extend(remaining)
    return dashboard_baseline_assumptions.main(forwarded)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    command_handlers = {
        "write-repro-bundle": repro_bundle_cli.main,
        "build-dashboard-baseline-assumptions": dashboard_baseline_assumptions.main,
        "write-selected-cells": selected_cells.main,
        "reform-full-h5-artifacts": reform_full_h5_artifacts.main,
    }
    if argv and argv[0] in command_handlers:
        return command_handlers[argv[0]](argv[1:])

    parser = argparse.ArgumentParser(prog="crfb-tob")
    subparsers = parser.add_subparsers(dest="command", required=True)

    repro_parser = subparsers.add_parser(
        "write-repro-bundle",
        help="Write a reproducibility bundle without launching Modal.",
    )
    repro_parser.set_defaults(handler=repro_bundle_cli.main)

    baseline_parser = subparsers.add_parser(
        "build-dashboard-baseline-assumptions",
        help="Build public dashboard baseline assumption and audit artifacts.",
    )
    baseline_parser.add_argument(
        "--metadata-root",
        action="append",
        default=[],
        help=(
            "Projected dataset directory or .h5.metadata.json file to include in "
            "calibration target/support exports. May be passed more than once."
        ),
    )
    baseline_parser.add_argument(
        "--policyengine-us-path",
        default=None,
        help=(
            "Optional explicit policyengine-us checkout/runtime path. If omitted, "
            "the installed policyengine-us package is used."
        ),
    )
    baseline_parser.set_defaults(
        handler=_run_dashboard_baseline_assumptions,
        handler_accepts_namespace=True,
    )

    selected_cells_parser = subparsers.add_parser(
        "write-selected-cells",
        help="Write the selected CRFB long-run reform/year cells CSV.",
    )
    selected_cells_parser.set_defaults(handler=selected_cells.main)

    reform_full_h5_parser = subparsers.add_parser(
        "reform-full-h5-artifacts",
        help="Inspect and validate CRFB full reform H5 artifacts.",
    )
    reform_full_h5_parser.set_defaults(handler=reform_full_h5_artifacts.main)

    args, remaining = parser.parse_known_args(argv)
    if getattr(args, "handler_accepts_namespace", False):
        return args.handler(args, remaining)
    return args.handler(remaining)
