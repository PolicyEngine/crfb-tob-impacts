from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from src.reform_full_h5_artifacts import (
    FullH5ValidationError,
    file_sha256,
    inspect_entity_table_h5,
    load_expected_schema_manifest,
    upload_artifact_pair_to_object_store,
    validate_full_h5_against_expected_schema,
    validate_object_store_artifacts,
    write_expected_schema_manifest,
)


def _write_full_h5(path: Path, *, omit_household_weight: bool = False) -> None:
    frames = {
        "person": pd.DataFrame(
            {"person_id": [1, 2], "person_weight": [1.0, 1.0], "age": [70, 72]}
        ),
        "household": pd.DataFrame(
            {
                "household_id": [1],
                **({} if omit_household_weight else {"household_weight": [2.0]}),
                "household_net_income": [10.0],
            }
        ),
        "tax_unit": pd.DataFrame(
            {"tax_unit_id": [1], "tax_unit_weight": [2.0], "income_tax": [1.0]}
        ),
        "spm_unit": pd.DataFrame(
            {"spm_unit_id": [1], "spm_unit_weight": [2.0], "snap": [0.0]}
        ),
        "family": pd.DataFrame(
            {"family_id": [1], "family_weight": [2.0], "family_size": [2]}
        ),
        "marital_unit": pd.DataFrame(
            {"marital_unit_id": [1], "marital_unit_weight": [2.0]}
        ),
    }
    with pd.HDFStore(path, mode="w") as store:
        for key, frame in frames.items():
            store.put(key, frame, format="table")


def test_expected_schema_manifest_validates_matching_full_h5(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    schema_path = tmp_path / "expected-schema.json"
    _write_full_h5(h5_path)

    write_expected_schema_manifest(
        h5_path=h5_path,
        output_path=schema_path,
        source="trusted-reference",
    )
    result = validate_full_h5_against_expected_schema(
        candidate_h5_path=h5_path,
        expected_schema_manifest_path=schema_path,
    )

    assert result["validated"] is True
    assert result["candidate_h5_sha256"] == file_sha256(h5_path)
    assert result["entities"]["household"]["required_weight_column_present"] is True


def test_expected_schema_validation_accepts_preapproved_row_overrides(
    tmp_path: Path,
):
    expected_h5 = tmp_path / "expected.h5"
    candidate_h5 = tmp_path / "candidate.h5"
    schema_path = tmp_path / "expected-schema.json"
    _write_full_h5(expected_h5)
    _write_full_h5(candidate_h5)

    with pd.HDFStore(candidate_h5, mode="a") as store:
        store.put(
            "household",
            pd.DataFrame(
                {
                    "household_id": [1, 2],
                    "household_weight": [2.0, 3.0],
                    "household_net_income": [10.0, 20.0],
                }
            ),
            format="table",
        )

    write_expected_schema_manifest(
        h5_path=expected_h5,
        output_path=schema_path,
        source="trusted-reference",
    )
    result = validate_full_h5_against_expected_schema(
        candidate_h5_path=candidate_h5,
        expected_schema_manifest_path=schema_path,
        expected_entity_rows={"household": 2},
    )

    assert result["validated"] is True
    assert result["expected_entity_rows_override_used"] is True
    assert result["entities"]["household"]["rows"] == 2


def test_schema_validation_rejects_candidate_missing_weight_column(tmp_path: Path):
    expected_h5 = tmp_path / "expected.h5"
    candidate_h5 = tmp_path / "candidate.h5"
    schema_path = tmp_path / "expected-schema.json"
    _write_full_h5(expected_h5)
    _write_full_h5(candidate_h5, omit_household_weight=True)
    write_expected_schema_manifest(
        h5_path=expected_h5,
        output_path=schema_path,
        source="trusted-reference",
    )

    with pytest.raises(FullH5ValidationError, match="column inventory mismatch"):
        validate_full_h5_against_expected_schema(
            candidate_h5_path=candidate_h5,
            expected_schema_manifest_path=schema_path,
        )


def test_expected_schema_manifest_loader_rejects_unapproved_role(tmp_path: Path):
    schema_path = tmp_path / "expected-schema.json"
    schema_path.write_text(
        '{"schema_role": "candidate_output", "schema_hash": "abc"}\n',
        encoding="utf-8",
    )

    with pytest.raises(FullH5ValidationError, match="preapproved"):
        load_expected_schema_manifest(schema_path)


def test_expected_schema_manifest_loader_rejects_missing_entity_structure(
    tmp_path: Path,
):
    schema_path = tmp_path / "expected-schema.json"
    schema_path.write_text(
        '{"schema_role": "preapproved_expected_full_output_schema", "schema_hash": "abc"}\n',
        encoding="utf-8",
    )

    with pytest.raises(FullH5ValidationError, match="entities"):
        load_expected_schema_manifest(schema_path)


def test_expected_schema_manifest_loader_requires_weight_column_present(
    tmp_path: Path,
):
    schema_path = tmp_path / "expected-schema.json"
    schema_path.write_text(
        """
        {
          "schema_role": "preapproved_expected_full_output_schema",
          "schema_hash": "abc",
          "size_bytes": 1,
          "entities": {
            "household": {
              "rows": 1,
              "columns": ["household_id"],
              "required_weight_column": "household_weight",
              "required_weight_column_present": false
            }
          }
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(FullH5ValidationError, match="required weight column"):
        load_expected_schema_manifest(schema_path)


class FakeObjectStoreClient:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.objects[(bucket, key)] = Path(filename).read_bytes()

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

    def head_object(self, *, Bucket: str, Key: str) -> dict:
        body = self.objects[(Bucket, Key)]
        return {"ContentLength": len(body), "ETag": "fake-etag"}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}


def test_object_store_validation_gets_h5_and_checks_sha(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    metadata_path = tmp_path / "metadata.json"
    _write_full_h5(h5_path)
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")
    client = FakeObjectStoreClient()

    result = upload_artifact_pair_to_object_store(
        client=client,
        bucket="bucket",
        scenario_path=h5_path,
        metadata_path=metadata_path,
        scenario_key="run/scenario.h5",
        metadata_key="run/metadata.json",
    )

    assert result["validated"] is True
    assert result["scenario_sha256"] == file_sha256(h5_path)
    assert result["metadata_sha256"] == file_sha256(metadata_path)
    assert validate_object_store_artifacts(
        client=client,
        bucket="bucket",
        scenario_key="run/scenario.h5",
        metadata_key="run/metadata.json",
        expected_scenario_sha256=file_sha256(h5_path),
        expected_metadata_sha256=file_sha256(metadata_path),
    )["validated"]


def test_object_store_upload_writes_completion_marker(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    metadata_path = tmp_path / "metadata.json"
    _write_full_h5(h5_path)
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")
    client = FakeObjectStoreClient()

    result = upload_artifact_pair_to_object_store(
        client=client,
        bucket="bucket",
        scenario_path=h5_path,
        metadata_path=metadata_path,
        scenario_key="run/scenario.h5",
        metadata_key="run/metadata.json",
        completion_key="run/complete.json",
    )

    assert result["validated"] is True
    assert result["completion_key"] == "run/complete.json"
    assert ("bucket", "run/complete.json") in client.objects


def test_object_store_upload_is_idempotent_for_same_content(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    metadata_path = tmp_path / "metadata.json"
    _write_full_h5(h5_path)
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")
    client = FakeObjectStoreClient()
    kwargs = {
        "client": client,
        "bucket": "bucket",
        "scenario_path": h5_path,
        "metadata_path": metadata_path,
        "scenario_key": "run/scenario.h5",
        "metadata_key": "run/metadata.json",
        "completion_key": "run/complete.json",
    }

    upload_artifact_pair_to_object_store(**kwargs)
    assert upload_artifact_pair_to_object_store(**kwargs)["validated"] is True


def test_object_store_upload_rejects_existing_key_with_different_content(
    tmp_path: Path,
):
    h5_path = tmp_path / "scenario.h5"
    metadata_path = tmp_path / "metadata.json"
    _write_full_h5(h5_path)
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")
    client = FakeObjectStoreClient()
    kwargs = {
        "client": client,
        "bucket": "bucket",
        "scenario_path": h5_path,
        "metadata_path": metadata_path,
        "scenario_key": "run/scenario.h5",
        "metadata_key": "run/metadata.json",
        "completion_key": "run/complete.json",
    }

    upload_artifact_pair_to_object_store(**kwargs)
    h5_path.write_bytes(h5_path.read_bytes() + b"different")
    with pytest.raises(RuntimeError, match="precondition failed"):
        upload_artifact_pair_to_object_store(**kwargs)


def test_object_store_validation_rejects_metadata_sha_mismatch(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    metadata_path = tmp_path / "metadata.json"
    _write_full_h5(h5_path)
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")
    client = FakeObjectStoreClient()
    upload_artifact_pair_to_object_store(
        client=client,
        bucket="bucket",
        scenario_path=h5_path,
        metadata_path=metadata_path,
        scenario_key="run/scenario.h5",
        metadata_key="run/metadata.json",
    )

    with pytest.raises(FullH5ValidationError, match="metadata.json SHA256"):
        validate_object_store_artifacts(
            client=client,
            bucket="bucket",
            scenario_key="run/scenario.h5",
            metadata_key="run/metadata.json",
            expected_scenario_sha256=file_sha256(h5_path),
            expected_metadata_sha256="not-the-sha",
        )


def test_inspect_entity_table_h5_records_required_weights(tmp_path: Path):
    h5_path = tmp_path / "scenario.h5"
    _write_full_h5(h5_path)

    manifest = inspect_entity_table_h5(h5_path)

    assert manifest["entity_count"] == 6
    assert manifest["entities"]["person"]["required_weight_column"] == "person_weight"
    assert manifest["entities"]["household"]["rows"] == 1
