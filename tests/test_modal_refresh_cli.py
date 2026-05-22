import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import modal_refresh


def test_modal_refresh_defaults_to_policyengine_py_managed(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    args = modal_refresh.parse_args(
        [
            "--reforms",
            "option1",
            "--years",
            "2026",
            "--output",
            str(tmp_path / "out.csv"),
        ]
    )

    resolved = modal_refresh._resolve_args(args)

    assert resolved.use_policyengine_py_managed_datasets is True
    assert resolved.policyengine_us_path is None


def test_modal_refresh_raw_h5_requires_explicit_paths(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)

    with pytest.raises(ValueError, match="require explicit paths"):
        modal_refresh._resolve_args(
            modal_refresh.parse_args(
                [
                    "--no-policyengine-py-managed-datasets",
                    "--reforms",
                    "option1",
                    "--years",
                    "2026",
                    "--output",
                    str(tmp_path / "out.csv"),
                ]
            )
        )


def test_modal_refresh_managed_rejects_raw_h5_args(tmp_path: Path):
    with pytest.raises(ValueError, match="cannot be combined"):
        modal_refresh._resolve_args(
            modal_refresh.parse_args(
                [
                    "--reforms",
                    "option1",
                    "--years",
                    "2026",
                    "--output",
                    str(tmp_path / "out.csv"),
                    "--projected-datasets-path",
                    str(tmp_path / "projected"),
                ]
            )
        )


def test_sync_snapshot_replaces_existing_h5_even_if_snapshot_is_newer(
    tmp_path: Path,
):
    source = tmp_path / "source"
    snapshot = tmp_path / "snapshot"
    source.mkdir()
    snapshot.mkdir()

    source_h5 = source / "2026.h5"
    source_metadata = source / "2026.h5.metadata.json"
    source_manifest = source / "calibration_manifest.json"
    source_h5.write_text("source h5", encoding="utf-8")
    source_metadata.write_text('{"source": true}', encoding="utf-8")
    source_manifest.write_text('{"manifest": "source"}', encoding="utf-8")

    snapshot_h5 = snapshot / "2026.h5"
    snapshot_metadata = snapshot / "2026.h5.metadata.json"
    snapshot_manifest = snapshot / "calibration_manifest.json"
    snapshot_h5.write_text("stale h5", encoding="utf-8")
    snapshot_metadata.write_text('{"source": false}', encoding="utf-8")
    snapshot_manifest.write_text('{"manifest": "stale"}', encoding="utf-8")

    newer_than_source = source_h5.stat().st_mtime + 1_000
    for path in (snapshot_h5, snapshot_metadata, snapshot_manifest):
        path.touch()
        path.chmod(0o644)
        os.utime(path, (newer_than_source, newer_than_source))

    modal_refresh.sync_snapshot(source, snapshot)

    assert snapshot_h5.read_text(encoding="utf-8") == "source h5"
    assert snapshot_metadata.read_text(encoding="utf-8") == '{"source": true}'
    assert snapshot_manifest.read_text(encoding="utf-8") == '{"manifest": "source"}'


def test_launch_modal_refuses_existing_submission_manifest(tmp_path: Path):
    manifest = tmp_path / "submission.json"
    manifest.write_text('{"status": "already-submitted"}', encoding="utf-8")

    args = SimpleNamespace(submission_manifest=manifest)

    with pytest.raises(FileExistsError, match="already exists and is non-empty"):
        modal_refresh.launch_modal(args)


def test_launch_modal_installs_policyengine_stack_for_modal_import(
    monkeypatch, tmp_path: Path
):
    recorded: dict[str, list[str]] = {}

    def fake_run(command, cwd, env):
        recorded["command"] = command
        recorded["env"] = env
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(modal_refresh, "snapshot_summary", lambda path: {})
    monkeypatch.setattr(
        modal_refresh,
        "resolved_environment_contract",
        lambda **kwargs: {},
    )
    monkeypatch.setattr(modal_refresh.subprocess, "run", fake_run)

    args = SimpleNamespace(
        submission_manifest=None,
        detach=False,
        modal_target="run_cells",
        reforms="option1",
        scoring="static",
        years="2026",
        output=str(tmp_path / "out.csv"),
        cells_file=tmp_path / "cells.csv",
        no_use_baseline_artifacts=False,
        snapshot_path=tmp_path / "snapshot",
        policyengine_us_path=None,
        use_policyengine_py_managed_datasets=True,
        policyengine_py_path=None,
    )

    assert modal_refresh.launch_modal(args) == 0

    command = recorded["command"]
    assert "--with" in command
    assert modal_refresh.POLICYENGINE_PACKAGE_SPEC in command
    assert not any(value.startswith("policyengine-us==") for value in command)
    assert not any(value.startswith("policyengine-core==") for value in command)


def test_launch_modal_managed_scrubs_stale_raw_and_local_env(
    monkeypatch, tmp_path: Path
):
    recorded: dict[str, dict[str, str]] = {}

    def fake_run(command, cwd, env):
        recorded["env"] = env
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("CRFB_POLICYENGINE_PY_PATH", "/stale/policyengine.py")
    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", "/stale/policyengine-us")
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", "/stale/datasets")
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", "/stale/{year}.h5")
    monkeypatch.setenv("CRFB_POLICYENGINE_US_DATA_REPO_PATH", "/stale/us-data")
    monkeypatch.setenv("POLICYENGINE_US_DATA_REPO", "/stale/us-data")
    monkeypatch.setattr(
        modal_refresh,
        "resolved_environment_contract",
        modal_refresh.resolved_environment_contract,
    )
    monkeypatch.setattr(modal_refresh.subprocess, "run", fake_run)

    args = SimpleNamespace(
        submission_manifest=None,
        detach=False,
        modal_target="run_cells",
        reforms="option1",
        scoring="static",
        years="2026",
        output=str(tmp_path / "out.csv"),
        cells_file=None,
        no_use_baseline_artifacts=False,
        snapshot_path=None,
        policyengine_us_path=None,
        use_policyengine_py_managed_datasets=True,
        policyengine_py_path=None,
    )

    assert modal_refresh.launch_modal(args) == 0

    for name in (
        "CRFB_POLICYENGINE_PY_PATH",
        "CRFB_POLICYENGINE_US_PATH",
        "CRFB_PROJECTED_DATASETS_PATH",
        "CRFB_DATASET_TEMPLATE",
        "CRFB_POLICYENGINE_US_DATA_REPO_PATH",
        "POLICYENGINE_US_DATA_REPO",
    ):
        assert name not in recorded["env"]


def test_main_records_snapshot_path_in_repro_bundle_contract(
    monkeypatch, tmp_path: Path
):
    captured: dict[str, Path] = {}
    snapshot = tmp_path / "snapshot"
    source = tmp_path / "source"
    policyengine_us = tmp_path / "policyengine-us"
    output = tmp_path / "out.csv"
    source.mkdir()
    policyengine_us.mkdir()

    def fake_create_repro_bundle(**kwargs):
        captured["projected_datasets_path"] = kwargs["projected_datasets_path"]
        captured["snapshot_path"] = kwargs["snapshot_path"]
        return SimpleNamespace(
            bundle_dir=tmp_path / "bundle",
            manifest_path=tmp_path / "bundle" / "run_manifest.json",
        )

    monkeypatch.setattr(modal_refresh, "sync_snapshot", lambda source, snapshot: None)
    monkeypatch.setattr(
        modal_refresh,
        "validate_policyengine_us_runtime_contract",
        lambda runtime, snapshot: {},
    )
    monkeypatch.setattr(modal_refresh, "create_repro_bundle", fake_create_repro_bundle)
    monkeypatch.setattr(modal_refresh, "launch_modal", lambda args: 0)

    assert (
        modal_refresh.main(
            [
                "--reforms",
                "option1",
                "--years",
                "2026",
                "--output",
                str(output),
                "--no-policyengine-py-managed-datasets",
                "--policyengine-us-path",
                str(policyengine_us),
                "--projected-datasets-path",
                str(source),
                "--snapshot-path",
                str(snapshot),
            ]
        )
        == 0
    )

    assert captured["projected_datasets_path"] == snapshot
    assert captured["snapshot_path"] == snapshot


def test_main_managed_mode_preflights_requested_years(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}
    output = tmp_path / "out.csv"
    policyengine_py = tmp_path / "policyengine.py"
    policyengine_py.mkdir()

    def fake_preflight(years):
        captured["years"] = list(years)
        assert "POLICYENGINE_US_DATA_REPO" not in os.environ
        assert "CRFB_PROJECTED_DATASETS_PATH" not in os.environ
        return {"checked_years": list(years), "records": []}

    def fake_create_repro_bundle(**kwargs):
        captured["managed"] = kwargs["use_policyengine_py_managed_datasets"]
        captured["projected_datasets_path"] = kwargs["projected_datasets_path"]
        return SimpleNamespace(
            bundle_dir=tmp_path / "bundle",
            manifest_path=tmp_path / "bundle" / "run_manifest.json",
        )

    monkeypatch.setattr(
        modal_refresh,
        "validate_policyengine_py_managed_long_term_dataset_availability",
        fake_preflight,
    )
    monkeypatch.setenv("POLICYENGINE_US_DATA_REPO", "/stale/us-data")
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", "/stale/datasets")
    monkeypatch.setattr(modal_refresh, "create_repro_bundle", fake_create_repro_bundle)
    monkeypatch.setattr(modal_refresh, "launch_modal", lambda args: 0)
    monkeypatch.setattr(
        modal_refresh,
        "sync_snapshot",
        lambda source, snapshot: pytest.fail("managed mode should not snapshot"),
    )

    assert (
        modal_refresh.main(
            [
                "--reforms",
                "option1",
                "--years",
                "2026-2027,2100",
                "--output",
                str(output),
                "--policyengine-py-path",
                str(policyengine_py),
            ]
        )
        == 0
    )

    assert captured["years"] == [2026, 2027, 2100]
    assert captured["managed"] is True
    assert captured["projected_datasets_path"] is None
