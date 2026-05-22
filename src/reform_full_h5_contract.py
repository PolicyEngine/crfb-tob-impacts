from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import fcntl
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
from typing import Any, Protocol


class ApprovalGuardError(RuntimeError):
    """Raised when a paid reform-H5 launch is not explicitly approved."""


@dataclass(frozen=True, order=True)
class ReformCell:
    year: int
    reform: str
    scoring_type: str = "static"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scoring_type",
            normalize_scoring_type(self.scoring_type),
        )

    @classmethod
    def from_any(cls, value: Any) -> "ReformCell":
        if isinstance(value, ReformCell):
            return value
        if isinstance(value, dict):
            reform = value.get("reform") or value.get("reform_id")
            return cls(
                year=int(value["year"]),
                reform=str(reform),
                scoring_type=str(value.get("scoring_type", "static")),
            )
        if isinstance(value, (list, tuple)):
            if len(value) == 2:
                reform, year = value
                return cls(year=int(year), reform=str(reform))
            if len(value) == 3:
                reform, year, scoring_type = value
                return cls(
                    year=int(year),
                    reform=str(reform),
                    scoring_type=str(scoring_type),
                )
        raise TypeError(f"Cannot parse approved reform cell: {value!r}")

    def key(self) -> str:
        return f"year={self.year}/reform={self.reform}/scoring={self.scoring_type}"

    def to_ledger(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "reform": self.reform,
            "scoring_type": self.scoring_type,
        }


@dataclass(frozen=True)
class Reservation:
    cell: ReformCell
    token: str
    token_hash: str

    def to_worker_payload(self) -> dict[str, Any]:
        return {
            "cell": self.cell.to_ledger(),
            "reservation_token": self.token,
        }


class ApprovalStore(Protocol):
    def consume_approval_once(self, nonce: str, payload: dict[str, Any]) -> None:
        """Record approval consumption exactly once or raise ApprovalGuardError."""

    def create_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        """Create a per-cell reservation exactly once or raise ApprovalGuardError."""

    def consume_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        """Consume a per-cell reservation exactly once or raise ApprovalGuardError."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expected_reservation_payload_subset(
    *,
    nonce: str,
    cell: dict[str, Any],
    launch_mode: str,
    worker_entrypoint: str,
    code_bundle_sha: str,
) -> dict[str, Any]:
    return {
        "nonce": nonce,
        "cell": cell,
        "launch_mode": launch_mode,
        "worker_entrypoint": worker_entrypoint,
        "code_bundle_sha": code_bundle_sha,
    }


def _validate_payload_subset(
    *,
    actual: dict[str, Any],
    expected: dict[str, Any],
    context: str,
) -> None:
    for key, value in expected.items():
        _require(
            actual.get(key) == value,
            f"{context} payload field {key!r} does not match.",
        )


def compute_code_bundle_sha(
    *,
    repo_root: str | Path,
    paths: list[str] | tuple[str, ...],
) -> str:
    """Hash the code and metadata paths that define a paid reform-H5 launch."""

    root = Path(repo_root)
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path = root / relative
        if not path.exists():
            raise FileNotFoundError(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ledger(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_ledger(path: str | Path, ledger: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=destination.parent,
        delete=False,
    ) as temp:
        json.dump(ledger, temp, indent=2)
        temp.write("\n")
        temp_path = Path(temp.name)
    temp_path.replace(destination)


def normalize_cells(cells: list[Any] | tuple[Any, ...]) -> tuple[ReformCell, ...]:
    return tuple(sorted(ReformCell.from_any(cell) for cell in cells))


def normalize_scoring_type(scoring_type: str) -> str:
    normalized = scoring_type.strip().lower()
    if normalized == "conventional":
        return "behavioral"
    return normalized


def _ledger_cells(ledger: dict[str, Any], key: str) -> tuple[ReformCell, ...]:
    return normalize_cells(ledger.get(key) or [])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ApprovalGuardError(message)


def _validate_common_approval(
    ledger: dict[str, Any],
    *,
    requested_cells: tuple[ReformCell, ...],
    launch_mode: str,
    worker_entrypoint: str,
    submit_command: str | None,
    code_bundle_sha: str,
    durable_storage_target: str,
    approval_nonce: str,
    worker_sha: str | None = None,
) -> None:
    approved_cells = _ledger_cells(ledger, "approved_cells")
    _require(bool(approved_cells), "No approved_cells are recorded in the ledger.")
    _require(
        requested_cells == approved_cells,
        "Requested cells do not exactly match approved_cells.",
    )
    _require(
        int(ledger.get("allowed_paid_call_count") or 0) == len(requested_cells),
        "allowed_paid_call_count does not match the requested cell count.",
    )
    _require(
        ledger.get("approval_nonce") == approval_nonce,
        "approval_nonce does not match the ledger.",
    )
    _require(
        ledger.get("approved_worker_entrypoint") == worker_entrypoint,
        "approved_worker_entrypoint does not match the requested worker.",
    )
    _require(
        bool(ledger.get("approved_worker_sha")),
        "approved_worker_sha is missing.",
    )
    if worker_sha is not None:
        _require(
            ledger.get("approved_worker_sha") == worker_sha,
            "approved_worker_sha does not match the worker file.",
        )
    _require(
        ledger.get("approved_code_bundle_sha") == code_bundle_sha,
        "approved_code_bundle_sha does not match the requested code bundle.",
    )
    _require(
        ledger.get("approved_durable_storage_target") == durable_storage_target,
        "approved_durable_storage_target does not match the requested target.",
    )
    _require(
        bool(ledger.get("approval_transaction_store")),
        "approval_transaction_store is missing.",
    )
    _require(
        bool(ledger.get("approved_expected_schema_manifest")),
        "approved_expected_schema_manifest is missing.",
    )
    _require(
        bool(ledger.get("approved_expected_schema_manifest_sha")),
        "approved_expected_schema_manifest_sha is missing.",
    )
    _require(
        bool(ledger.get("approved_baseline_dataset_manifest")),
        "approved_baseline_dataset_manifest is missing.",
    )
    _require(
        bool(ledger.get("approved_baseline_dataset_manifest_sha")),
        "approved_baseline_dataset_manifest_sha is missing.",
    )
    if submit_command is not None:
        _require(
            ledger.get("approved_submit_command") == submit_command,
            "approved_submit_command does not match the requested submitter.",
        )
    if launch_mode in {"sentinel", "full"}:
        _require(
            ledger.get("paid_modal_launch_allowed") is True,
            "paid_modal_launch_allowed is not true.",
        )
        _require(bool(ledger.get("approval_text_or_id")), "approval_text_or_id is missing.")
        _require(bool(ledger.get("approved_by")), "approved_by is missing.")
        _require(bool(ledger.get("approved_at")), "approved_at is missing.")
    if launch_mode == "sentinel":
        _require(
            ledger.get("current_gate") == "G5.5",
            "current_gate must be G5.5 for sentinel launches.",
        )
        _require(
            ledger.get("sentinel_launch_allowed") is True,
            "sentinel_launch_allowed is not true.",
        )
        _require(len(requested_cells) == 1, "Sentinel approvals must contain one cell.")
    elif launch_mode == "full":
        _require(
            ledger.get("current_gate") == "G8",
            "current_gate must be G8 for full launches.",
        )
        _require(
            ledger.get("full_launch_allowed") is True,
            "full_launch_allowed is not true.",
        )
        _require(
            bool(ledger.get("approved_pip_freeze_sha256")),
            "approved_pip_freeze_sha256 is required for full launches.",
        )
    elif launch_mode == "test":
        pass
    else:
        raise ApprovalGuardError(f"Unknown launch_mode: {launch_mode}")


def submitter_consume_and_reserve(
    *,
    ledger_path: str | Path,
    requested_cells: list[Any] | tuple[Any, ...],
    launch_mode: str,
    worker_entrypoint: str,
    worker_sha: str | None = None,
    submit_command: str,
    code_bundle_sha: str,
    durable_storage_target: str,
    approval_nonce: str,
    consumed_by: str,
    store: ApprovalStore,
) -> list[Reservation]:
    """Validate, consume, and reserve a paid launch before creating calls."""

    ledger = load_ledger(ledger_path)
    cells = normalize_cells(requested_cells)
    _validate_common_approval(
        ledger,
        requested_cells=cells,
        launch_mode=launch_mode,
        worker_entrypoint=worker_entrypoint,
        worker_sha=worker_sha,
        submit_command=submit_command,
        code_bundle_sha=code_bundle_sha,
        durable_storage_target=durable_storage_target,
        approval_nonce=approval_nonce,
    )
    _require(ledger.get("approval_consumed") is False, "Approval is already consumed.")
    _require(
        int(ledger.get("paid_call_count_consumed") or 0) == 0,
        "paid_call_count_consumed is already nonzero.",
    )
    _require(not ledger.get("reserved_cells"), "reserved_cells is already populated.")
    _require(
        not ledger.get("reservation_token_hashes"),
        "reservation_token_hashes is already populated.",
    )
    _require(not ledger.get("launched_call_ids"), "launched_call_ids is already set.")

    approval_payload = {
        "nonce": approval_nonce,
        "cells": [cell.to_ledger() for cell in cells],
        "launch_mode": launch_mode,
        "worker_entrypoint": worker_entrypoint,
        "submit_command": submit_command,
        "code_bundle_sha": code_bundle_sha,
        "durable_storage_target": durable_storage_target,
        "consumed_by": consumed_by,
        "consumed_at": utc_now_iso(),
    }
    store.consume_approval_once(approval_nonce, approval_payload)

    reservations: list[Reservation] = []
    for cell in cells:
        token = secrets.token_urlsafe(32)
        digest = token_hash(token)
        reservation_payload = {
            **_expected_reservation_payload_subset(
                nonce=approval_nonce,
                cell=cell.to_ledger(),
                launch_mode=launch_mode,
                worker_entrypoint=worker_entrypoint,
                code_bundle_sha=code_bundle_sha,
            ),
            "created_at": utc_now_iso(),
        }
        store.create_reservation(digest, reservation_payload)
        reservations.append(Reservation(cell=cell, token=token, token_hash=digest))

    ledger.update(
        {
            "approval_consumed": True,
            "approval_consumed_at": approval_payload["consumed_at"],
            "approval_consumed_by": consumed_by,
            "paid_call_count_consumed": len(cells),
            "reserved_cells": [cell.to_ledger() for cell in cells],
            "reservation_token_hashes": [
                reservation.token_hash for reservation in reservations
            ],
        }
    )
    write_ledger(ledger_path, ledger)
    return reservations


def worker_verify_reserved_call(
    *,
    ledger_path: str | Path,
    cell: Any,
    launch_mode: str,
    worker_entrypoint: str,
    worker_sha: str | None = None,
    code_bundle_sha: str,
    durable_storage_target: str,
    approval_nonce: str,
    reservation_token: str,
    store: ApprovalStore,
) -> dict[str, Any]:
    """Fail closed unless this worker invocation has a reserved cell token."""

    ledger = load_ledger(ledger_path)
    requested_cell = ReformCell.from_any(cell)
    requested_cells = (requested_cell,)
    _validate_common_approval(
        ledger,
        requested_cells=_ledger_cells(ledger, "approved_cells"),
        launch_mode=launch_mode,
        worker_entrypoint=worker_entrypoint,
        worker_sha=worker_sha,
        submit_command=None,
        code_bundle_sha=code_bundle_sha,
        durable_storage_target=durable_storage_target,
        approval_nonce=approval_nonce,
    )
    _require(ledger.get("approval_consumed") is True, "Approval was not consumed.")
    _require(
        requested_cell in _ledger_cells(ledger, "reserved_cells"),
        "Worker cell is not reserved in the ledger.",
    )
    digest = token_hash(reservation_token)
    _require(
        digest in set(ledger.get("reservation_token_hashes") or []),
        "Reservation token hash is not in the ledger.",
    )
    _require(
        requested_cell in _ledger_cells(ledger, "approved_cells"),
        "Worker cell is not approved.",
    )
    if launch_mode == "sentinel":
        _require(len(requested_cells) == 1, "Sentinel worker must run one cell.")

    expected_reservation = _expected_reservation_payload_subset(
        nonce=approval_nonce,
        cell=requested_cell.to_ledger(),
        launch_mode=launch_mode,
        worker_entrypoint=worker_entrypoint,
        code_bundle_sha=code_bundle_sha,
    )
    store.consume_reservation(
        digest,
        {
            **expected_reservation,
            "expected_reservation": expected_reservation,
            "consumed_at": utc_now_iso(),
        },
    )
    return ledger


class LocalFileLockApprovalStore:
    """Local transactional store for tests and dry-runs, not paid Modal work."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.root / ".approval-store.lock"

    def _with_lock(self, callback):
        with self._lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                return callback()
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write_once(self, relative_path: str, payload: dict[str, Any]) -> None:
        path = self.root / relative_path

        def operation() -> None:
            if path.exists():
                raise ApprovalGuardError(f"Store key already exists: {relative_path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        self._with_lock(operation)

    def consume_approval_once(self, nonce: str, payload: dict[str, Any]) -> None:
        self._write_once(f"approvals/{nonce}.json", payload)

    def create_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        self._write_once(f"reservations/{token_hash}.json", payload)

    def consume_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        reservation_path = self.root / f"reservations/{token_hash}.json"
        consumed_path = self.root / f"consumed_reservations/{token_hash}.json"

        def operation() -> None:
            if not reservation_path.exists():
                raise ApprovalGuardError("Reservation token does not exist.")
            expected = payload.get("expected_reservation")
            if not isinstance(expected, dict):
                raise ApprovalGuardError(
                    "Reservation consumption payload is missing expected_reservation."
                )
            if consumed_path.exists():
                consumed_payload = json.loads(consumed_path.read_text(encoding="utf-8"))
                consumed_expected = consumed_payload.get("expected_reservation")
                if not isinstance(consumed_expected, dict):
                    raise ApprovalGuardError(
                        "Consumed reservation payload is missing expected_reservation."
                    )
                _validate_payload_subset(
                    actual=consumed_expected,
                    expected=expected,
                    context="Local consumed reservation retry",
                )
                return
            if isinstance(expected, dict):
                reservation_payload = json.loads(
                    reservation_path.read_text(encoding="utf-8")
                )
                _validate_payload_subset(
                    actual=reservation_payload,
                    expected=expected,
                    context="Local reservation",
                )
            consumed_path.parent.mkdir(parents=True, exist_ok=True)
            consumed_path.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )

        self._with_lock(operation)


class R2ConditionalApprovalStore:
    """Approval store backed by conditional object creation in R2/S3."""

    def __init__(self, *, client: Any, bucket: str, prefix: str):
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    @classmethod
    def from_uri(cls, *, client: Any, uri: str) -> "R2ConditionalApprovalStore":
        bucket, prefix = parse_r2_uri(uri)
        return cls(client=client, bucket=bucket, prefix=prefix)

    def _key(self, relative_path: str) -> str:
        return f"{self.prefix}/{relative_path}" if self.prefix else relative_path

    def _put_once(self, relative_path: str, payload: dict[str, Any]) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self._key(relative_path),
                Body=json.dumps(payload, indent=2).encode("utf-8") + b"\n",
                ContentType="application/json",
                IfNoneMatch="*",
            )
        except Exception as error:  # pragma: no cover - exercised with real R2
            raise ApprovalGuardError(
                f"Conditional R2 write failed for {relative_path}: {error}"
            ) from error

    def _read_json(self, relative_path: str) -> dict[str, Any]:
        try:
            result = self.client.get_object(
                Bucket=self.bucket,
                Key=self._key(relative_path),
            )
            body = result["Body"]
            data = body.read() if hasattr(body, "read") else body
            return json.loads(data.decode("utf-8"))
        except Exception as error:  # pragma: no cover - exercised with real R2
            raise ApprovalGuardError(
                f"R2 reservation read failed for {relative_path}: {error}"
            ) from error

    def consume_approval_once(self, nonce: str, payload: dict[str, Any]) -> None:
        self._put_once(f"approvals/{nonce}.json", payload)

    def create_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        self._put_once(f"reservations/{token_hash}.json", payload)

    def consume_reservation(self, token_hash: str, payload: dict[str, Any]) -> None:
        reservation_payload = self._read_json(f"reservations/{token_hash}.json")
        expected = payload.get("expected_reservation")
        if not isinstance(expected, dict):
            raise ApprovalGuardError("Reservation consumption payload is missing expected_reservation.")
        _validate_payload_subset(
            actual=reservation_payload,
            expected=expected,
            context="R2 reservation",
        )
        try:
            self._put_once(f"consumed_reservations/{token_hash}.json", payload)
        except ApprovalGuardError as error:
            consumed_payload = self._read_json(
                f"consumed_reservations/{token_hash}.json"
            )
            consumed_expected = consumed_payload.get("expected_reservation")
            if not isinstance(consumed_expected, dict):
                raise error
            _validate_payload_subset(
                actual=consumed_expected,
                expected=expected,
                context="R2 consumed reservation retry",
            )


def record_launched_call_ids(
    *,
    ledger_path: str | Path,
    call_ids: list[str],
) -> None:
    ledger = load_ledger(ledger_path)
    _require(ledger.get("approval_consumed") is True, "Approval was not consumed.")
    _require(not ledger.get("launched_call_ids"), "launched_call_ids already set.")
    _require(
        len(call_ids) == int(ledger.get("paid_call_count_consumed") or 0),
        "launched_call_ids count does not match paid_call_count_consumed.",
    )
    spawned_call_ids = [
        str(record.get("call_id"))
        for record in (ledger.get("spawned_call_records") or [])
    ]
    if spawned_call_ids:
        _require(
            call_ids == spawned_call_ids,
            "launched_call_ids do not match spawned_call_records.",
        )
    ledger["launched_call_ids"] = list(call_ids)
    write_ledger(ledger_path, ledger)


def record_spawned_call(
    *,
    ledger_path: str | Path,
    call_record: dict[str, Any],
) -> None:
    ledger = load_ledger(ledger_path)
    _require(ledger.get("approval_consumed") is True, "Approval was not consumed.")
    paid_count = int(ledger.get("paid_call_count_consumed") or 0)
    _require(paid_count > 0, "paid_call_count_consumed is zero.")

    call_id = str(call_record.get("call_id") or "")
    _require(bool(call_id), "call_record is missing call_id.")
    cell = ReformCell.from_any(call_record)
    _require(
        cell in _ledger_cells(ledger, "reserved_cells"),
        "Spawned call cell is not reserved in the ledger.",
    )

    records = list(ledger.get("spawned_call_records") or [])
    existing_call_ids = {str(record.get("call_id")) for record in records}
    _require(call_id not in existing_call_ids, "Spawned call_id is already recorded.")
    existing_cells = {ReformCell.from_any(record) for record in records}
    _require(cell not in existing_cells, "Spawned cell is already recorded.")
    _require(
        len(records) < paid_count,
        "spawned_call_records already matches paid_call_count_consumed.",
    )

    records.append(call_record)
    ledger["spawned_call_records"] = records
    ledger["spawned_call_ids"] = [str(record["call_id"]) for record in records]
    write_ledger(ledger_path, ledger)


def cell_list_for_ledger(cells: list[ReformCell] | tuple[ReformCell, ...]) -> list[dict]:
    return [asdict(cell) for cell in cells]


def parse_r2_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("r2://"):
        raise ApprovalGuardError(f"Unsupported approval store URI: {uri}")
    remainder = uri.removeprefix("r2://").strip("/")
    if not remainder:
        raise ApprovalGuardError("R2 approval store URI is missing a bucket.")
    bucket, _, prefix = remainder.partition("/")
    if not bucket:
        raise ApprovalGuardError("R2 approval store URI is missing a bucket.")
    if not prefix:
        raise ApprovalGuardError("R2 approval store URI is missing a prefix.")
    return bucket, prefix.strip("/")
