from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_MODAL_REFRESH = REPO_ROOT / "scripts" / "run_modal_refresh.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Launch the attribution grid using one year x one reform Modal cell "
            "per task and combine results locally."
        )
    )
    parser.add_argument("--reforms", required=True, help="Comma-separated reform IDs.")
    parser.add_argument("--years", required=True, help="Year range or comma-separated years.")
    parser.add_argument(
        "--scoring",
        default="static",
        choices=["static", "dynamic"],
        help="Scoring mode to run.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Combined output CSV path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = [
        sys.executable,
        str(RUN_MODAL_REFRESH),
        "--modal-target",
        "run_cells",
        "--reforms",
        args.reforms,
        "--scoring",
        args.scoring,
        "--years",
        args.years,
        "--output",
        str(args.output.resolve()),
    ]
    print(f"Launching: {' '.join(command)}")
    completed = subprocess.run(command, cwd=REPO_ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
