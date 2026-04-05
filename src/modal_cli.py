from __future__ import annotations

import os
from pathlib import Path
import shutil


def resolve_uv_executable() -> str:
    env_path = os.environ.get("CRFB_UV_PATH")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"CRFB_UV_PATH does not exist: {path}")
        return str(path)

    discovered = shutil.which("uv")
    if discovered:
        return discovered

    fallback = Path.home() / ".local" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)

    raise FileNotFoundError("Could not resolve uv. Add it to PATH or set CRFB_UV_PATH.")


def resolve_modal_profile() -> str | None:
    for key in ("CRFB_MODAL_PROFILE", "MODAL_PROFILE"):
        value = os.environ.get(key)
        if value:
            return value
    return None


def modal_subprocess_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    profile = resolve_modal_profile()
    if profile:
        env["MODAL_PROFILE"] = profile
    return env


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


def modal_python_prefix() -> list[str]:
    return [
        resolve_uv_executable(),
        "run",
        "--with",
        "modal",
        "--with",
        "pandas",
        "python",
    ]
