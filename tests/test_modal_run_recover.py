from __future__ import annotations

from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def test_download_run_uses_force_for_modal_volume_get(tmp_path: Path, monkeypatch):
    import modal_run_recover as module

    run_id = "run123"
    temp_root = tmp_path / "temp"
    output_dir = tmp_path / "recovered"
    calls: list[tuple[str, ...]] = []

    class DummyTempDir:
        def __enter__(self) -> str:
            temp_root.mkdir(parents=True, exist_ok=True)
            return str(temp_root)

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_modal_volume(*args: str) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[0] == "ls":
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[0] == "get":
            recovered_root = temp_root / module.run_root(run_id)
            recovered_root.mkdir(parents=True, exist_ok=True)
            (recovered_root / "manifest.json").write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected modal_volume args: {args}")

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", lambda prefix="": DummyTempDir())
    monkeypatch.setattr(module, "modal_volume", fake_modal_volume)

    manifest_path = module.download_run(run_id, output_dir)

    assert manifest_path == output_dir / "manifest.json"
    assert ("get", "--force", "crfb-results", f"{module.run_root(run_id)}/", f"{temp_root}/") in calls


def test_download_volume_prefix_returns_output_dir_when_manifest_missing(
    tmp_path: Path, monkeypatch
):
    import modal_run_recover as module

    prefix = "special_case_reruns/demo"
    temp_root = tmp_path / "temp"
    output_dir = tmp_path / "recovered"

    class DummyTempDir:
        def __enter__(self) -> str:
            temp_root.mkdir(parents=True, exist_ok=True)
            return str(temp_root)

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def fake_modal_volume(*args: str) -> subprocess.CompletedProcess[str]:
        if args[0] == "ls":
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[0] == "get":
            recovered_root = temp_root / prefix
            recovered_root.mkdir(parents=True, exist_ok=True)
            (recovered_root / "option13").mkdir()
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(f"Unexpected modal_volume args: {args}")

    monkeypatch.setattr(module.tempfile, "TemporaryDirectory", lambda prefix="": DummyTempDir())
    monkeypatch.setattr(module, "modal_volume", fake_modal_volume)

    recovered = module.download_volume_prefix(prefix, output_dir)

    assert recovered == output_dir
    assert (output_dir / "option13").exists()
