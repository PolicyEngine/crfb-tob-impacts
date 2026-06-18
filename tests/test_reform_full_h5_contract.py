from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import threading

import pytest

from src.reform_full_h5_contract import (
    ApprovalGuardError,
    LocalFileLockApprovalStore,
    R2ConditionalApprovalStore,
    ReformCell,
    compute_code_bundle_sha,
    load_ledger,
    parse_r2_uri,
    record_launched_call_ids,
    record_spawned_call,
    submitter_consume_and_reserve,
    worker_verify_reserved_call,
    write_ledger,
)
from src.reform_full_h5_worker import WORKER_ENTRYPOINT


def _approved_ledger(tmp_path: Path, *, nonce: str = "nonce-1") -> Path:
    ledger_path = tmp_path / "progress.json"
    write_ledger(
        ledger_path,
        {
            "paid_modal_launch_allowed": True,
            "sentinel_launch_allowed": True,
            "full_launch_allowed": False,
            "current_gate": "G5.5",
            "approved_worker_entrypoint": WORKER_ENTRYPOINT,
            "approved_worker_sha": None,
            "approved_code_bundle_sha": "bundle-sha",
            "approved_submit_command": "submit --one",
            "approved_durable_storage_target": "r2://bucket/prefix",
            "approved_r2_bucket_prefix": "bucket/prefix",
            "approval_transaction_store": "local-file-lock://test-only",
            "approved_expected_schema_manifest": "schema.json",
            "approved_expected_schema_manifest_sha": "schema-sha",
            "approved_baseline_dataset_manifest": "baseline-datasets.json",
            "approved_baseline_dataset_manifest_sha": "baseline-datasets-sha",
            "approved_pip_freeze_sha256": None,
            "approved_cells": [
                {"year": 2075, "reform": "option10", "scoring_type": "static"}
            ],
            "allowed_paid_call_count": 1,
            "approval_nonce": nonce,
            "approval_consumed": False,
            "approval_consumed_at": None,
            "approval_consumed_by": None,
            "paid_call_count_consumed": 0,
            "reserved_cells": [],
            "reservation_token_hashes": [],
            "spawned_call_records": [],
            "spawned_call_ids": [],
            "launched_call_ids": [],
            "approval_text_or_id": "user-approved-test",
            "approved_by": "Max",
            "approved_at": "2026-05-21T00:00:00-04:00",
        },
    )
    return ledger_path


def _full_approved_ledger(tmp_path: Path) -> Path:
    ledger_path = _approved_ledger(tmp_path)
    ledger = load_ledger(ledger_path)
    ledger.update(
        {
            "sentinel_launch_allowed": False,
            "full_launch_allowed": True,
            "current_gate": "G8",
            "approved_pip_freeze_sha256": "pip-freeze-sha",
        }
    )
    write_ledger(ledger_path, ledger)
    return ledger_path


def test_submitter_consumes_approval_and_worker_consumes_reservation(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)

    reservations = submitter_consume_and_reserve(
        ledger_path=ledger_path,
        requested_cells=[cell],
        launch_mode="sentinel",
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha="worker-sha",
        submit_command="submit --one",
        code_bundle_sha="bundle-sha",
        durable_storage_target="r2://bucket/prefix",
        approval_nonce="nonce-1",
        consumed_by="pytest",
        store=store,
    )

    ledger = load_ledger(ledger_path)
    assert ledger["approval_consumed"] is True
    assert ledger["paid_call_count_consumed"] == 1
    assert ledger["reserved_cells"] == [cell.to_ledger()]
    assert ledger["reservation_token_hashes"] == [reservations[0].token_hash]

    worker_verify_reserved_call(
        ledger_path=ledger_path,
        cell=cell,
        launch_mode="sentinel",
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha="worker-sha",
        code_bundle_sha="bundle-sha",
        durable_storage_target="r2://bucket/prefix",
        approval_nonce="nonce-1",
        reservation_token=reservations[0].token,
        store=store,
    )

    worker_verify_reserved_call(
        ledger_path=ledger_path,
        cell=cell,
        launch_mode="sentinel",
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha="worker-sha",
        code_bundle_sha="bundle-sha",
        durable_storage_target="r2://bucket/prefix",
        approval_nonce="nonce-1",
        reservation_token=reservations[0].token,
        store=store,
    )


def test_reform_cell_keeps_behavioral_label():
    cell = ReformCell(year=2026, reform="option1", scoring_type="behavioral")

    assert cell.scoring_type == "behavioral"
    assert cell.key() == "year=2026/reform=option1/scoring=behavioral"
    assert (
        ReformCell.from_any(
            {"year": 2026, "reform": "option1", "scoring_type": "behavioral"}
        )
        == cell
    )


def test_reform_cell_rejects_conventional_label():
    with pytest.raises(ValueError, match="Unsupported scoring_type"):
        ReformCell(year=2026, reform="option1", scoring_type="conventional")


def test_submitter_approval_is_single_use_even_for_same_cell(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)
    kwargs = {
        "ledger_path": ledger_path,
        "requested_cells": [cell],
        "launch_mode": "sentinel",
        "worker_entrypoint": WORKER_ENTRYPOINT,
        "worker_sha": "worker-sha",
        "submit_command": "submit --one",
        "code_bundle_sha": "bundle-sha",
        "durable_storage_target": "r2://bucket/prefix",
        "approval_nonce": "nonce-1",
        "consumed_by": "pytest",
        "store": store,
    }

    submitter_consume_and_reserve(**kwargs)
    with pytest.raises(ApprovalGuardError):
        submitter_consume_and_reserve(**kwargs)


def test_submitter_rejects_mismatched_code_bundle_sha(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)

    with pytest.raises(ApprovalGuardError, match="approved_code_bundle_sha"):
        submitter_consume_and_reserve(
            ledger_path=ledger_path,
            requested_cells=[cell],
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            submit_command="submit --one",
            code_bundle_sha="different-bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            consumed_by="pytest",
            store=store,
        )


def test_submitter_rejects_mismatched_worker_sha(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "approved-worker-sha"
    write_ledger(ledger_path, ledger)

    with pytest.raises(ApprovalGuardError, match="approved_worker_sha"):
        submitter_consume_and_reserve(
            ledger_path=ledger_path,
            requested_cells=[cell],
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="different-worker-sha",
            submit_command="submit --one",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            consumed_by="pytest",
            store=store,
        )


def test_sentinel_launch_requires_correct_gate_and_approval_identity(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    ledger["current_gate"] = "G4"
    write_ledger(ledger_path, ledger)

    with pytest.raises(ApprovalGuardError, match="current_gate"):
        submitter_consume_and_reserve(
            ledger_path=ledger_path,
            requested_cells=[cell],
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            submit_command="submit --one",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            consumed_by="pytest",
            store=store,
        )

    ledger["current_gate"] = "G5.5"
    ledger["approved_by"] = ""
    write_ledger(ledger_path, ledger)
    with pytest.raises(ApprovalGuardError, match="approved_by"):
        submitter_consume_and_reserve(
            ledger_path=ledger_path,
            requested_cells=[cell],
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            submit_command="submit --one",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            consumed_by="pytest",
            store=store,
        )


def test_full_launch_requires_approved_pip_freeze_sha(tmp_path: Path):
    ledger_path = _full_approved_ledger(tmp_path)
    ledger = load_ledger(ledger_path)
    ledger["approved_pip_freeze_sha256"] = None
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")

    with pytest.raises(ApprovalGuardError, match="approved_pip_freeze_sha256"):
        submitter_consume_and_reserve(
            ledger_path=ledger_path,
            requested_cells=[cell],
            launch_mode="full",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            submit_command="submit --one",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            consumed_by="pytest",
            store=store,
        )


def test_worker_rejects_direct_invocation_without_reserved_token(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)

    with pytest.raises(ApprovalGuardError, match="Approval was not consumed"):
        worker_verify_reserved_call(
            ledger_path=ledger_path,
            cell=cell,
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            reservation_token="not-reserved",
            store=store,
        )


def test_concurrent_submitter_consumption_allows_exactly_one_success(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)
    results: list[str] = []

    def attempt() -> None:
        try:
            submitter_consume_and_reserve(
                ledger_path=ledger_path,
                requested_cells=[cell],
                launch_mode="sentinel",
                worker_entrypoint=WORKER_ENTRYPOINT,
                worker_sha="worker-sha",
                submit_command="submit --one",
                code_bundle_sha="bundle-sha",
                durable_storage_target="r2://bucket/prefix",
                approval_nonce="nonce-1",
                consumed_by="pytest",
                store=store,
            )
        except ApprovalGuardError:
            results.append("blocked")
        else:
            results.append("success")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(results) == ["blocked", "success"]
    store_records = list((tmp_path / "store" / "approvals").glob("*.json"))
    assert len(store_records) == 1
    assert json.loads(store_records[0].read_text())["nonce"] == "nonce-1"


def test_code_bundle_sha_is_deterministic_and_content_sensitive(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "worker.py").write_text("print('worker')\n", encoding="utf-8")
    (repo / "submit.py").write_text("print('submit')\n", encoding="utf-8")

    first = compute_code_bundle_sha(
        repo_root=repo,
        paths=["worker.py", "submit.py"],
    )
    reversed_order = compute_code_bundle_sha(
        repo_root=repo,
        paths=["submit.py", "worker.py"],
    )
    (repo / "worker.py").write_text("print('changed')\n", encoding="utf-8")
    changed = compute_code_bundle_sha(
        repo_root=repo,
        paths=["worker.py", "submit.py"],
    )

    assert first == reversed_order
    assert changed != first


def test_record_launched_call_ids_is_counted_and_single_use(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)
    submitter_consume_and_reserve(
        ledger_path=ledger_path,
        requested_cells=[cell],
        launch_mode="sentinel",
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha="worker-sha",
        submit_command="submit --one",
        code_bundle_sha="bundle-sha",
        durable_storage_target="r2://bucket/prefix",
        approval_nonce="nonce-1",
        consumed_by="pytest",
        store=store,
    )

    with pytest.raises(ApprovalGuardError, match="count"):
        record_launched_call_ids(ledger_path=ledger_path, call_ids=[])

    record_launched_call_ids(ledger_path=ledger_path, call_ids=["fc-test"])
    assert load_ledger(ledger_path)["launched_call_ids"] == ["fc-test"]

    with pytest.raises(ApprovalGuardError, match="already set"):
        record_launched_call_ids(ledger_path=ledger_path, call_ids=["fc-test-2"])


def test_spawned_call_record_is_incremental_and_finalized(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    store = LocalFileLockApprovalStore(tmp_path / "store")
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    ledger = load_ledger(ledger_path)
    ledger["approved_worker_sha"] = "worker-sha"
    write_ledger(ledger_path, ledger)
    submitter_consume_and_reserve(
        ledger_path=ledger_path,
        requested_cells=[cell],
        launch_mode="sentinel",
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha="worker-sha",
        submit_command="submit --one",
        code_bundle_sha="bundle-sha",
        durable_storage_target="r2://bucket/prefix",
        approval_nonce="nonce-1",
        consumed_by="pytest",
        store=store,
    )
    call_record = {
        **cell.to_ledger(),
        "call_id": "fc-test",
        "dashboard_url": "https://modal.example/fc-test",
    }

    record_spawned_call(ledger_path=ledger_path, call_record=call_record)
    ledger = load_ledger(ledger_path)
    assert ledger["spawned_call_ids"] == ["fc-test"]
    assert ledger["spawned_call_records"] == [call_record]
    assert ledger["launched_call_ids"] == []

    with pytest.raises(ApprovalGuardError, match="already recorded"):
        record_spawned_call(ledger_path=ledger_path, call_record=call_record)

    record_launched_call_ids(ledger_path=ledger_path, call_ids=["fc-test"])
    assert load_ledger(ledger_path)["launched_call_ids"] == ["fc-test"]


def test_parse_r2_uri_requires_bucket_and_prefix():
    assert parse_r2_uri("r2://bucket/prefix/nested") == ("bucket", "prefix/nested")

    with pytest.raises(ApprovalGuardError, match="Unsupported"):
        parse_r2_uri("s3://bucket/prefix")

    with pytest.raises(ApprovalGuardError, match="prefix"):
        parse_r2_uri("r2://bucket")


class FakeR2Client:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(
        self,
        *,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str,
        IfNoneMatch: str,
    ) -> None:
        del ContentType
        assert IfNoneMatch == "*"
        storage_key = (Bucket, Key)
        if storage_key in self.objects:
            raise RuntimeError("precondition failed")
        self.objects[storage_key] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}


def test_r2_reservation_consume_requires_existing_reservation_payload(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    token = "reserved-token"
    digest = __import__("hashlib").sha256(token.encode("utf-8")).hexdigest()
    ledger = load_ledger(ledger_path)
    ledger.update(
        {
            "approval_consumed": True,
            "approved_worker_sha": "worker-sha",
            "paid_call_count_consumed": 1,
            "reserved_cells": [cell.to_ledger()],
            "reservation_token_hashes": [digest],
        }
    )
    write_ledger(ledger_path, ledger)

    store = R2ConditionalApprovalStore(
        client=FakeR2Client(),
        bucket="bucket",
        prefix="approval-store",
    )
    with pytest.raises(ApprovalGuardError, match="reservation read failed"):
        worker_verify_reserved_call(
            ledger_path=ledger_path,
            cell=cell,
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            reservation_token=token,
            store=store,
        )


def test_r2_reservation_consumption_is_idempotent_for_modal_retry(tmp_path: Path):
    ledger_path = _approved_ledger(tmp_path)
    cell = ReformCell(year=2075, reform="option10", scoring_type="static")
    token = "reserved-token"
    digest = __import__("hashlib").sha256(token.encode("utf-8")).hexdigest()
    ledger = load_ledger(ledger_path)
    ledger.update(
        {
            "approval_consumed": True,
            "approved_worker_sha": "worker-sha",
            "paid_call_count_consumed": 1,
            "reserved_cells": [cell.to_ledger()],
            "reservation_token_hashes": [digest],
        }
    )
    write_ledger(ledger_path, ledger)

    client = FakeR2Client()
    store = R2ConditionalApprovalStore(
        client=client,
        bucket="bucket",
        prefix="approval-store",
    )
    store.create_reservation(
        digest,
        {
            "nonce": "nonce-1",
            "cell": cell.to_ledger(),
            "launch_mode": "sentinel",
            "worker_entrypoint": WORKER_ENTRYPOINT,
            "code_bundle_sha": "bundle-sha",
        },
    )

    for _ in range(2):
        worker_verify_reserved_call(
            ledger_path=ledger_path,
            cell=cell,
            launch_mode="sentinel",
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha="worker-sha",
            code_bundle_sha="bundle-sha",
            durable_storage_target="r2://bucket/prefix",
            approval_nonce="nonce-1",
            reservation_token=token,
            store=store,
        )
