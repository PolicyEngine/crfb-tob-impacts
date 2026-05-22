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
        "launch_mode not in {\"sentinel\", \"full\"}",
        "code_bundle_paths",
        "CODE_BUNDLE_PYTHON_DIRS",
        "\"src\"",
        "\"modal_batch\"",
        "rglob(\"*.py\")",
        "expected_schema_manifest_payload",
        "expected_schema_manifest_text",
        "baseline_dataset_manifest_payload",
        "baseline_dataset_manifest_text",
        "load_expected_schema_manifest(expected_schema_manifest_path)",
        "status\": \"spawning\"",
        "wait_for_completion",
        "call.get()",
        "status\": \"waiting_for_completion\"",
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
    spawn_segment = source[source.index("call = compute_reform_full_h5_cell_remote.spawn") :]
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
