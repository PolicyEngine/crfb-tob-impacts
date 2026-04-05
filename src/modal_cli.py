from __future__ import annotations

import os
from pathlib import Path
import shutil


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


def modal_cli_prefix() -> list[str]:
    return [
        resolve_uvx_executable(),
        "--from",
        "modal",
        "--with",
        "pandas",
        "modal",
    ]
