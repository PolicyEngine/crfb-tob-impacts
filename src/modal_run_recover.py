from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def modal_volume(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "uvx",
            "--from",
            "modal",
            "--with",
            "pandas",
            "modal",
            "volume",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def run_root(run_id: str) -> str:
    return run_id.strip("/")


def _resolve_recovered_root(temp_path: Path, prefix: str) -> Path:
    candidates = [
        temp_path / prefix,
        temp_path / Path(prefix).name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    direct_children = [path for path in temp_path.iterdir() if path.exists()]
    if len(direct_children) == 1:
        return direct_children[0]

    raise FileNotFoundError(
        f"Recovered root missing after modal volume get for prefix {prefix}: {temp_path}"
    )


def download_volume_prefix(prefix: str, output_dir: Path) -> Path:
    prefix = prefix.strip("/")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ls_result = modal_volume("ls", "crfb-results", prefix)
    if ls_result.returncode != 0:
        raise RuntimeError(
            f"modal volume ls failed for {prefix}: {ls_result.stderr.strip()}"
        )

    with tempfile.TemporaryDirectory(prefix="modal-run-recover-") as temp_root:
        temp_path = Path(temp_root)
        get_result = modal_volume(
            "get",
            "--force",
            "crfb-results",
            f"{prefix}/",
            f"{temp_root}/",
        )
        if get_result.returncode != 0:
            raise RuntimeError(
                f"modal volume get failed for {prefix}: {get_result.stderr.strip()}"
            )

        recovered_root = _resolve_recovered_root(temp_path, prefix)

        shutil.copytree(recovered_root, output_dir, dirs_exist_ok=True)

    manifest_path = output_dir / "manifest.json"
    return manifest_path if manifest_path.exists() else output_dir


def download_run(run_id: str, output_dir: Path) -> Path:
    return download_volume_prefix(run_root(run_id), output_dir)
