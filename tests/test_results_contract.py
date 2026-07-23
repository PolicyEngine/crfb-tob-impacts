"""The published results contract must validate against its schema and
carry a complete lineage chain for every exact cell."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO / "dashboard" / "public" / "data" / "results_contract.json"
SCHEMA_PATH = REPO / "contracts" / "results.schema.json"
ALT_BASELINE_MANIFEST = (
    REPO / "docs" / "current" / "manifests" / "baseline-dataset-manifest-v2pop.json"
)
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_results_contract import (  # noqa: E402
    DEFAULT_BASELINE_MANIFEST,
    DEFAULT_DISPLAY,
    DEFAULT_LIVE_STATUS,
    DEFAULT_SUPPLEMENTAL_BASELINE_MANIFESTS,
    build_contract,
)


@pytest.fixture(scope="module")
def contract() -> dict:
    if not CONTRACT_PATH.exists():
        pytest.skip("results contract not yet published")
    return json.loads(CONTRACT_PATH.read_text())


def test_contract_validates_against_schema(contract: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(contract, schema)


def test_contract_builder_regenerates_current_contract(contract: dict) -> None:
    import jsonschema

    regenerated = build_contract(
        DEFAULT_DISPLAY,
        DEFAULT_BASELINE_MANIFEST,
        DEFAULT_LIVE_STATUS,
    )
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(regenerated, schema)

    committed_without_timestamp = {**contract, "generated_at": None}
    regenerated_without_timestamp = {**regenerated, "generated_at": None}
    assert regenerated_without_timestamp == committed_without_timestamp


def test_schema_rejects_malformed_supplemental_manifest_paths(contract: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    malformed = json.loads(json.dumps(contract))
    malformed["lineage"]["baseline_build"]["supplemental_manifest_paths"] = (
        "not-an-array"
    )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(malformed, schema)


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("manifest_path", ""),
        ("manifest_path", "/tmp/manifest.json"),
        ("manifest_path", "../manifest.json"),
        ("manifest_path", "docs/current/../manifest.json"),
        ("manifest_path", "docs/current/manifest.txt"),
        ("supplemental_manifest_paths", [""]),
        ("supplemental_manifest_paths", ["/tmp/manifest.json"]),
        ("supplemental_manifest_paths", ["../manifest.json"]),
        ("supplemental_manifest_paths", ["docs/current/../manifest.json"]),
        ("supplemental_manifest_paths", ["docs/current/manifest.txt"]),
    ],
)
def test_schema_rejects_non_package_manifest_paths(
    contract: dict, field: str, bad_value: object
) -> None:
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    malformed = json.loads(json.dumps(contract))
    malformed["lineage"]["baseline_build"][field] = bad_value

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(malformed, schema)


def test_contract_builder_rejects_missing_exact_year_baseline_lineage() -> None:
    with pytest.raises(ValueError, match="Exact full-H5 row lacks same-year"):
        build_contract(
            Path("dashboard/public/data/results.csv"),
            Path("docs/current/manifests/baseline-dataset-manifest-v2pop.json"),
            Path("dashboard/public/data/live_reform_status.csv"),
        )


def test_contract_builder_keeps_default_supplement_when_explicit_paths_are_added() -> (
    None
):
    regenerated = build_contract(
        Path("dashboard/public/data/results.csv"),
        DEFAULT_BASELINE_MANIFEST,
        Path("dashboard/public/data/live_reform_status.csv"),
        [Path("docs/current/manifests/baseline-dataset-manifest-v2pop.json")],
    )
    baseline_build = regenerated["lineage"]["baseline_build"]
    expected_supplements = {
        str(path.relative_to(REPO)) for path in DEFAULT_SUPPLEMENTAL_BASELINE_MANIFESTS
    } | {str(ALT_BASELINE_MANIFEST.relative_to(REPO))}

    assert set(baseline_build["supplemental_manifest_paths"]) == expected_supplements
    for infill_year in ["2028", "2029", "2032", "2033", "2062"]:
        assert infill_year in baseline_build["year_h5_sha256"]


def test_contract_builder_requires_custom_supplement_for_custom_manifest() -> None:
    regenerated = build_contract(
        Path("dashboard/public/data/results.csv"),
        Path("docs/current/manifests/baseline-dataset-manifest-v2pop.json"),
        Path("dashboard/public/data/live_reform_status.csv"),
        list(DEFAULT_SUPPLEMENTAL_BASELINE_MANIFESTS),
    )
    baseline_build = regenerated["lineage"]["baseline_build"]

    assert baseline_build["manifest_path"] == str(
        ALT_BASELINE_MANIFEST.relative_to(REPO)
    )
    assert baseline_build["supplemental_manifest_paths"] == [
        str(path.relative_to(REPO)) for path in DEFAULT_SUPPLEMENTAL_BASELINE_MANIFESTS
    ]


def test_contract_builder_rejects_missing_explicit_supplemental_manifest() -> None:
    with pytest.raises(FileNotFoundError, match="Supplemental baseline manifest"):
        build_contract(
            DEFAULT_DISPLAY,
            DEFAULT_BASELINE_MANIFEST,
            DEFAULT_LIVE_STATUS,
            [Path("docs/current/manifests/does-not-exist.json")],
        )


def test_every_exact_cell_carries_scenario_lineage(contract: dict) -> None:
    exact = [r for r in contract["results"] if r["result_type"] == "exact_full_h5"]
    assert exact, "Contract has no exact cells"
    missing = [
        (r["reform"], r["year"])
        for r in exact
        if not r["lineage"].get("scenario_h5_sha256")
        or not r["lineage"].get("run_prefix")
    ]
    assert not missing, f"Exact cells without scenario lineage: {missing[:10]}"


def test_interpolated_rows_name_their_anchors(contract: dict) -> None:
    interpolated = [
        r
        for r in contract["results"]
        if r["result_type"] == "linear_interpolation_between_full_h5_years"
    ]
    bad = [
        (r["reform"], r["year"])
        for r in interpolated
        if not r["lineage"].get("interpolated_between")
    ]
    assert not bad, f"Interpolated rows without anchors: {bad[:10]}"


def test_targets_use_populace_grammar(contract: dict) -> None:
    targets = contract["lineage"]["targets"]
    assert targets
    for target in targets:
        assert set(target) >= {
            "name",
            "entity",
            "aggregation",
            "period",
            "value",
            "source",
        }
        assert target["aggregation"] in {"sum", "count", "mean"}
