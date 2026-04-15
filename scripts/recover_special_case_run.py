from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_recover import download_volume_prefix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    return parser.parse_args()


def default_output_root(output_prefix: str) -> Path:
    slug = output_prefix.strip("/").replace("/", "__")
    return REPO_ROOT / "results" / "recovered_special_case_runs" / slug


def main() -> None:
    args = parse_args()
    output_root = args.output_root or default_output_root(args.output_prefix)
    recovered = download_volume_prefix(args.output_prefix, output_root)

    print(f"Recovered Modal volume prefix: {args.output_prefix}")
    print(f"Local output root: {output_root}")
    print(f"Recovery marker: {recovered}")
    if (output_root / "option13").exists():
        print(f"Option 13 dir: {output_root / 'option13'}")
    if (output_root / "option14").exists():
        print(f"Option 14 dir: {output_root / 'option14'}")


if __name__ == "__main__":
    main()
