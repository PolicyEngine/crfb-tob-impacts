from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from repro_freeze import freeze_repro_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive the snapshot and pinned repo heads for a reproducibility bundle."
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Path to a results/repro_bundles/<run>/ directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = freeze_repro_bundle(args.bundle_dir)
    print(f"Freeze manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
