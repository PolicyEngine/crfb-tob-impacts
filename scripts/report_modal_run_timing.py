from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_timing import timing_dataframe  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize launch, scheduling, and runtime timings for a recovered Modal run."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Recovered run directory containing manifest.json and scenario artifacts.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="CSV path for per-cell timing rows.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    df = timing_dataframe(run_dir, manifest)

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Wrote {output_path}")
    print(df.to_json(orient="records", indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
