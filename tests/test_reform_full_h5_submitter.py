from __future__ import annotations

from pathlib import Path


def test_full_h5_modal_submitter_is_guarded_and_not_legacy_aggregate_path():
    source = Path("modal_batch/reform_full_h5.py").read_text(encoding="utf-8")

    required = [
        "submitter_consume_and_reserve(",
        "record_spawned_call(",
        "record_launched_call_ids(",
        "compute_reform_full_h5_cell_remote.spawn",
        "remote_bundle_sha",
        "compute_reform_full_h5_bundle_sha",
        "runtime_fingerprint",
        "policyengine_us_tree_sha256",
        "run_reform_full_h5_cell(",
        "require_object_store=True",
        "CANONICAL_LEDGER_PATH",
        "ledger_file.resolve() != CANONICAL_LEDGER_PATH.resolve()",
        'launch_mode not in {"sentinel", "full"}',
        "code_bundle_paths",
        "CODE_BUNDLE_PYTHON_DIRS",
        '"src"',
        '"modal_batch"',
        'rglob("*.py")',
        "expected_schema_manifest_payload",
        "expected_schema_manifest_text",
        "baseline_dataset_manifest_payload",
        "baseline_dataset_manifest_text",
        "load_expected_schema_manifest(expected_schema_manifest_path)",
        'status": "spawning"',
        "wait_for_completion",
        "call.get()",
        'status": "waiting_for_completion"',
        "compute_reform_full_h5_cell_remote.remote(payload)",
        "compute_reform_full_h5_cell_from_json",
        "_compute_reform_full_h5_payload",
        "remote-direct:",
        "DEFAULT_R2_MODAL_SECRET_NAME",
        "modal_batch/reform_full_h5.py",
        "uv.lock",
    ]
    for text in required:
        assert text in source
    spawn_segment = source[
        source.index("call = compute_reform_full_h5_cell_remote.spawn") :
    ]
    assert spawn_segment.index("record_spawned_call(") < spawn_segment.index(
        "get_dashboard_url"
    )

    forbidden = [
        "load_baseline",
        "validate_baseline_reconciliation",
        "compute_scenario_household_metrics",
        "compute_reform_result",
        "compute_cell.spawn",
        "compute_year.spawn",
        "compute_scenario_artifact.spawn",
        "from .year_runner",
        "from year_runner",
    ]
    for text in forbidden:
        assert text not in source


def test_refuse_mixed_scoring_prefix_blocks_cross_scoring_overwrites(monkeypatch):
    import json

    from modal_batch import reform_full_h5 as submitter
    from src.reform_full_h5_contract import ReformCell

    class _Body:
        def __init__(self, payload: dict):
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

    class _StubClient:
        def __init__(self, scoring: str | None):
            self._scoring = scoring

        def list_objects_v2(self, **_kwargs):
            if self._scoring is None:
                return {"Contents": []}
            return {
                "Contents": [
                    {
                        "Key": "crfb/reform_full_h5/p/reform_full_h5/year=2026/reform=option1/metadata.json"
                    },
                    {
                        "Key": "crfb/reform_full_h5/p/reform_full_h5/year=2026/reform=option1/scenario.h5"
                    },
                ]
            }

        def get_object(self, **_kwargs):
            return {"Body": _Body({"scoring_type": self._scoring})}

    static_cells = [ReformCell(year=2026, reform="option1", scoring_type="static")]
    behavioral_cells = [
        ReformCell(year=2026, reform="option1", scoring_type="behavioral")
    ]

    # Mixed scoring within one request is refused outright.
    monkeypatch.setattr(submitter, "_boto3_client_from_env", lambda: _StubClient(None))
    try:
        submitter._refuse_mixed_scoring_prefix("p", static_cells + behavioral_cells)
    except submitter.ApprovalGuardError:
        pass
    else:
        raise AssertionError("Mixed-scoring request should be refused")

    # A prefix already holding static artifacts refuses behavioral cells.
    monkeypatch.setattr(
        submitter, "_boto3_client_from_env", lambda: _StubClient("static")
    )
    try:
        submitter._refuse_mixed_scoring_prefix("p", behavioral_cells)
    except submitter.ApprovalGuardError:
        pass
    else:
        raise AssertionError("Cross-scoring prefix reuse should be refused")

    # Same scoring type and empty prefixes pass.
    submitter._refuse_mixed_scoring_prefix("p", static_cells)
    monkeypatch.setattr(submitter, "_boto3_client_from_env", lambda: _StubClient(None))
    submitter._refuse_mixed_scoring_prefix("p", behavioral_cells)
