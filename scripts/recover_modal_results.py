from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pandas as pd
from modal_cli import modal_subprocess_env


def resolve_uvx_executable() -> str:
    env_path = os.environ.get("CRFB_UVX_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CRFB_UVX_PATH does not exist: {path}")
        return str(path)

    discovered = shutil.which("uvx")
    if discovered:
        return discovered

    fallback = Path.home() / ".local" / "bin" / "uvx"
    if fallback.exists():
        return str(fallback)

    raise FileNotFoundError(
        "Could not resolve uvx. Add it to PATH or set CRFB_UVX_PATH."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Modal volume results and combine recursive year CSVs."
    )
    parser.add_argument(
        "--volume-path", required=True, help="Path inside crfb-results volume."
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path, help="Local directory to populate."
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional combined CSV path. Defaults to <output-dir>.csv.",
    )
    return parser.parse_args()


def modal_volume(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            resolve_uvx_executable(),
            "--from",
            "modal",
            "--with",
            "pandas",
            "modal",
            "volume",
            *args,
        ],
        env=modal_subprocess_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def download(volume_path: str, output_dir: Path) -> None:
    listed = modal_volume("ls", "crfb-results", volume_path)
    print(f"Volume contents:\n{listed.stdout}")
    if listed.stderr:
        print(f"Volume ls stderr:\n{listed.stderr}")

    with tempfile.TemporaryDirectory(prefix="recover_modal_results_") as temp_dir:
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
            raise FileNotFoundError(
                f"Expected downloaded volume contents under {recovered_root}"
            )

        for source_path in recovered_root.rglob("*"):
            if not source_path.is_file():
                continue
            relative_path = source_path.relative_to(recovered_root)
            target_path = output_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def combine(output_dir: Path, output_csv: Path) -> None:
    files = sorted(output_dir.rglob("year_*.csv"))
    if not files:
        raise FileNotFoundError(f"No year CSVs found under {output_dir}")

    df = pd.concat([pd.read_csv(file_path) for file_path in files], ignore_index=True)
    df = df.sort_values(["reform_name", "year"])
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    print(f"Downloaded {len(files)} result files")
    print(f"Combined CSV: {output_csv}")

    error_files = sorted(output_dir.rglob("*.error.txt"))
    if error_files:
        print(f"Recovered {len(error_files)} error files:")
        for error_path in error_files:
            print(f"  {error_path}")


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_csv or args.output_dir.with_suffix(".csv")
    download(args.volume_path, args.output_dir)
    combine(args.output_dir, output_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
