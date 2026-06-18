from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


US_ENTITY_KEYS = (
    "person",
    "household",
    "tax_unit",
    "spm_unit",
    "family",
    "marital_unit",
)
US_ENTITY_WEIGHT_COLUMNS = {
    "person": "person_weight",
    "household": "household_weight",
    "tax_unit": "tax_unit_weight",
    "spm_unit": "spm_unit_weight",
    "family": "family_weight",
    "marital_unit": "marital_unit_weight",
}


class FullH5ValidationError(RuntimeError):
    """Raised when a reform H5 is not a full validated output artifact."""


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_schema_hash(entities: dict[str, dict[str, Any]]) -> str:
    schema_payload = {
        entity: {
            "rows": details["rows"],
            "columns": details["columns"],
            "required_weight_column_present": details["required_weight_column_present"],
        }
        for entity, details in sorted(entities.items())
    }
    encoded = json.dumps(schema_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def inspect_entity_table_h5(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    entities: dict[str, dict[str, Any]] = {}
    with pd.HDFStore(path, mode="r") as store:
        keys = {key.strip("/") for key in store.keys()}
        for entity in US_ENTITY_KEYS:
            if entity not in keys:
                continue
            dataframe = store[entity]
            required_weight = US_ENTITY_WEIGHT_COLUMNS[entity]
            columns = [str(column) for column in dataframe.columns]
            entities[entity] = {
                "rows": int(len(dataframe)),
                "columns": columns,
                "column_count": int(len(columns)),
                "required_weight_column": required_weight,
                "required_weight_column_present": required_weight in columns,
            }

    size_bytes = path.stat().st_size
    manifest = {
        "schema": "crfb_full_reform_h5_schema/v1",
        "path": str(path),
        "size_bytes": int(size_bytes),
        "sha256": file_sha256(path),
        "entities": entities,
        "entity_count": int(len(entities)),
        "schema_hash": _canonical_schema_hash(entities),
    }
    return manifest


def write_expected_schema_manifest(
    *,
    h5_path: str | Path,
    output_path: str | Path,
    source: str,
) -> dict[str, Any]:
    manifest = inspect_entity_table_h5(h5_path)
    manifest["schema_role"] = "preapproved_expected_full_output_schema"
    manifest["source"] = source
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_expected_schema_manifest(path: str | Path) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("schema_role") != "preapproved_expected_full_output_schema":
        raise FullH5ValidationError(
            "Expected schema manifest is not marked preapproved."
        )
    if not manifest.get("schema_hash"):
        raise FullH5ValidationError("Expected schema manifest lacks schema_hash.")
    if not isinstance(manifest.get("entities"), dict) or not manifest["entities"]:
        raise FullH5ValidationError("Expected schema manifest lacks entities.")
    if not isinstance(manifest.get("size_bytes"), int):
        raise FullH5ValidationError("Expected schema manifest lacks size_bytes.")
    for entity, details in manifest["entities"].items():
        if not isinstance(details, dict):
            raise FullH5ValidationError(f"{entity} schema details are invalid.")
        if not isinstance(details.get("rows"), int):
            raise FullH5ValidationError(f"{entity} schema lacks rows.")
        if not isinstance(details.get("columns"), list) or not details["columns"]:
            raise FullH5ValidationError(f"{entity} schema lacks columns.")
        if "required_weight_column_present" not in details:
            raise FullH5ValidationError(
                f"{entity} schema lacks required weight validation."
            )
        if details.get("required_weight_column_present") is not True:
            raise FullH5ValidationError(
                f"{entity} schema does not contain the required weight column."
            )
        required_weight_column = details.get("required_weight_column")
        if not required_weight_column:
            raise FullH5ValidationError(
                f"{entity} schema lacks required weight column."
            )
        if required_weight_column not in details["columns"]:
            raise FullH5ValidationError(
                f"{entity} schema required weight column is not in columns."
            )
    return manifest


def validate_full_h5_against_expected_schema(
    *,
    candidate_h5_path: str | Path,
    expected_schema_manifest_path: str | Path,
    expected_entity_rows: dict[str, int] | None = None,
    min_size_ratio: float = 0.25,
    max_size_ratio: float = 4.0,
) -> dict[str, Any]:
    expected = load_expected_schema_manifest(expected_schema_manifest_path)
    candidate = inspect_entity_table_h5(candidate_h5_path)

    expected_entities = {
        entity: dict(details) for entity, details in expected["entities"].items()
    }
    if expected_entity_rows is not None:
        for entity, rows in expected_entity_rows.items():
            if entity in expected_entities:
                expected_entities[entity]["rows"] = int(rows)
    candidate_entities = candidate["entities"]
    if set(candidate_entities) != set(expected_entities):
        raise FullH5ValidationError(
            "Candidate entity set does not match expected schema: "
            f"{sorted(candidate_entities)} != {sorted(expected_entities)}"
        )

    for entity, expected_details in expected_entities.items():
        candidate_details = candidate_entities[entity]
        if candidate_details["rows"] != expected_details["rows"]:
            raise FullH5ValidationError(
                f"{entity} row count mismatch: {candidate_details['rows']} != "
                f"{expected_details['rows']}"
            )
        if candidate_details["columns"] != expected_details["columns"]:
            raise FullH5ValidationError(f"{entity} column inventory mismatch.")
        if not candidate_details["required_weight_column_present"]:
            raise FullH5ValidationError(
                f"{entity} missing required weight column "
                f"{candidate_details['required_weight_column']}."
            )

    expected_size = int(expected["size_bytes"])
    if expected_size > 0:
        lower = expected_size * min_size_ratio
        upper = expected_size * max_size_ratio
        if not lower <= candidate["size_bytes"] <= upper:
            raise FullH5ValidationError(
                "Candidate H5 byte size outside sanity range: "
                f"{candidate['size_bytes']} not in [{lower}, {upper}]"
            )

    expected_schema_hash = _canonical_schema_hash(expected_entities)
    if candidate["schema_hash"] != expected_schema_hash:
        raise FullH5ValidationError("Candidate schema_hash mismatch.")

    return {
        "validated": True,
        "candidate_h5_path": str(candidate_h5_path),
        "candidate_h5_sha256": candidate["sha256"],
        "candidate_h5_size_bytes": candidate["size_bytes"],
        "expected_schema_manifest_path": str(expected_schema_manifest_path),
        "expected_schema_manifest_sha256": file_sha256(expected_schema_manifest_path),
        "schema_hash": candidate["schema_hash"],
        "expected_schema_hash": expected_schema_hash,
        "expected_entity_rows_override_used": expected_entity_rows is not None,
        "entities": candidate["entities"],
    }


def _read_body_bytes(body: Any) -> bytes:
    if hasattr(body, "read"):
        return body.read()
    if isinstance(body, bytes):
        return body
    raise TypeError(f"Unsupported object body type: {type(body).__name__}")


def validate_object_store_artifacts(
    *,
    client: Any,
    bucket: str,
    scenario_key: str,
    metadata_key: str,
    expected_scenario_sha256: str,
    expected_metadata_sha256: str | None = None,
    completion_key: str | None = None,
) -> dict[str, Any]:
    scenario_head = client.head_object(Bucket=bucket, Key=scenario_key)
    metadata_head = client.head_object(Bucket=bucket, Key=metadata_key)
    scenario_object = client.get_object(Bucket=bucket, Key=scenario_key)
    scenario_sha256 = hashlib.sha256(
        _read_body_bytes(scenario_object["Body"])
    ).hexdigest()
    metadata_object = client.get_object(Bucket=bucket, Key=metadata_key)
    metadata_sha256 = hashlib.sha256(
        _read_body_bytes(metadata_object["Body"])
    ).hexdigest()
    completion_head = None
    completion_sha256 = None
    if completion_key is not None:
        completion_head = client.head_object(Bucket=bucket, Key=completion_key)
        completion_object = client.get_object(Bucket=bucket, Key=completion_key)
        completion_sha256 = hashlib.sha256(
            _read_body_bytes(completion_object["Body"])
        ).hexdigest()
    if scenario_sha256 != expected_scenario_sha256:
        raise FullH5ValidationError(
            "Object-store scenario.h5 SHA256 mismatch: "
            f"{scenario_sha256} != {expected_scenario_sha256}"
        )
    if (
        expected_metadata_sha256 is not None
        and metadata_sha256 != expected_metadata_sha256
    ):
        raise FullH5ValidationError(
            "Object-store metadata.json SHA256 mismatch: "
            f"{metadata_sha256} != {expected_metadata_sha256}"
        )

    return {
        "bucket": bucket,
        "scenario_key": scenario_key,
        "metadata_key": metadata_key,
        "scenario_head": {
            "content_length": scenario_head.get("ContentLength"),
            "etag": scenario_head.get("ETag"),
        },
        "metadata_head": {
            "content_length": metadata_head.get("ContentLength"),
            "etag": metadata_head.get("ETag"),
        },
        "scenario_sha256": scenario_sha256,
        "metadata_sha256": metadata_sha256,
        "completion_key": completion_key,
        "completion_head": completion_head,
        "completion_sha256": completion_sha256,
        "validated": True,
    }


def _put_object_once(
    *,
    client: Any,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
) -> None:
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            IfNoneMatch="*",
        )
        return
    except Exception as error:
        try:
            existing = client.get_object(Bucket=bucket, Key=key)
            existing_body = existing["Body"]
            existing_bytes = (
                existing_body.read()
                if hasattr(existing_body, "read")
                else existing_body
            )
        except Exception:
            raise error
        if (
            hashlib.sha256(existing_bytes).hexdigest()
            != hashlib.sha256(body).hexdigest()
        ):
            raise error


def upload_artifact_pair_to_object_store(
    *,
    client: Any,
    bucket: str,
    scenario_path: str | Path,
    metadata_path: str | Path,
    scenario_key: str,
    metadata_key: str,
    completion_key: str | None = None,
) -> dict[str, Any]:
    scenario_path = Path(scenario_path)
    metadata_path = Path(metadata_path)
    scenario_sha = file_sha256(scenario_path)
    metadata_sha = file_sha256(metadata_path)
    _put_object_once(
        client=client,
        bucket=bucket,
        key=scenario_key,
        body=scenario_path.read_bytes(),
        content_type="application/x-hdf5",
    )
    _put_object_once(
        client=client,
        bucket=bucket,
        key=metadata_key,
        body=metadata_path.read_bytes(),
        content_type="application/json",
    )
    validation = validate_object_store_artifacts(
        client=client,
        bucket=bucket,
        scenario_key=scenario_key,
        metadata_key=metadata_key,
        expected_scenario_sha256=scenario_sha,
        expected_metadata_sha256=metadata_sha,
    )
    if completion_key is not None:
        completion_payload = {
            "schema": "crfb_reform_full_h5_completion/v1",
            "bucket": bucket,
            "scenario_key": scenario_key,
            "metadata_key": metadata_key,
            "scenario_sha256": scenario_sha,
            "metadata_sha256": metadata_sha,
            "validation": validation,
        }
        _put_object_once(
            client=client,
            bucket=bucket,
            key=completion_key,
            body=json.dumps(completion_payload, indent=2, sort_keys=True).encode(
                "utf-8"
            )
            + b"\n",
            content_type="application/json",
        )
        validation = validate_object_store_artifacts(
            client=client,
            bucket=bucket,
            scenario_key=scenario_key,
            metadata_key=metadata_key,
            expected_scenario_sha256=scenario_sha,
            expected_metadata_sha256=metadata_sha,
            completion_key=completion_key,
        )
    return validation


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or validate CRFB full reform H5 artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--h5", required=True, type=Path)
    inspect_parser.add_argument("--output", type=Path)
    schema_parser = subparsers.add_parser("write-expected-schema")
    schema_parser.add_argument("--h5", required=True, type=Path)
    schema_parser.add_argument("--output", required=True, type=Path)
    schema_parser.add_argument("--source", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--h5", required=True, type=Path)
    validate_parser.add_argument("--expected-schema", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "inspect":
        result = inspect_entity_table_h5(args.h5)
        text = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    if args.command == "write-expected-schema":
        write_expected_schema_manifest(
            h5_path=args.h5,
            output_path=args.output,
            source=args.source,
        )
        print(f"Wrote expected schema manifest to {args.output}")
        return 0
    if args.command == "validate":
        result = validate_full_h5_against_expected_schema(
            candidate_h5_path=args.h5,
            expected_schema_manifest_path=args.expected_schema,
        )
        print(json.dumps(result, indent=2))
        return 0
    raise AssertionError(args.command)
