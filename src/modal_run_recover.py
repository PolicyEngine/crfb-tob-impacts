from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from modal_cli import modal_cli_prefix
from modal_run_protocol import run_root, summarize_run_directory


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results" / "modal_runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download a remote Modal run tree and summarize cell status."
    )
    parser.add_argument("--run-id", required=True, help="Remote run identifier.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Local root directory for recovered runs.",
    )
    return parser.parse_args()


def modal_volume(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*modal_cli_prefix(), "volume", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def download_run(run_id: str, output_dir: Path) -> Path:
    volume_path = run_root(run_id)
    listed = modal_volume("ls", "crfb-results", str(volume_path))
    if listed.returncode != 0:
        raise RuntimeError(f"modal volume ls failed:\n{listed.stderr}")

    with tempfile.TemporaryDirectory(prefix="recover_modal_run_") as temp_dir:
        temp_path = Path(temp_dir)
        fetched = modal_volume(
            "get",
            "crfb-results",
            f"{volume_path}/",
            f"{temp_path}/",
        )
        if fetched.returncode != 0:
            raise RuntimeError(f"modal volume get failed:\n{fetched.stderr}")

        recovered_root = temp_path / volume_path
        if not recovered_root.exists():
            recovered_root = temp_path / run_id
        if not recovered_root.exists():
            raise FileNotFoundError(
                f"Expected downloaded run contents under {recovered_root}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        for source_path in recovered_root.rglob("*"):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(recovered_root)
            target_path = output_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    return output_dir / "manifest.json"


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_root).expanduser().resolve() / args.run_id
    manifest_path = download_run(args.run_id, output_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = summarize_run_directory(output_dir, manifest)
    status_path = output_dir / "status_summary.json"
    status_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Recovered manifest: {manifest_path}")
    print(f"Status summary: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
