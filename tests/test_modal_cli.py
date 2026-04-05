from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_modal_subprocess_env_uses_explicit_profile(monkeypatch):
    import modal_cli as module

    monkeypatch.setenv("CRFB_MODAL_PROFILE", "maxghenis")
    monkeypatch.delenv("MODAL_PROFILE", raising=False)

    env = module.modal_subprocess_env({"PATH": "/tmp"})

    assert env["PATH"] == "/tmp"
    assert env["MODAL_PROFILE"] == "maxghenis"


def test_modal_subprocess_env_falls_back_to_modal_profile(monkeypatch):
    import modal_cli as module

    monkeypatch.delenv("CRFB_MODAL_PROFILE", raising=False)
    monkeypatch.setenv("MODAL_PROFILE", "policyengine")

    env = module.modal_subprocess_env({"PATH": "/tmp"})

    assert env["PATH"] == "/tmp"
    assert env["MODAL_PROFILE"] == "policyengine"
