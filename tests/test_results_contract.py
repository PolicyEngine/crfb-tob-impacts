"""The published results contract must validate against its schema and
carry a complete lineage chain for every exact cell."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO / "dashboard" / "public" / "data" / "results_contract.json"
SCHEMA_PATH = REPO / "contracts" / "results.schema.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    if not CONTRACT_PATH.exists():
        pytest.skip("results contract not yet published")
    return json.loads(CONTRACT_PATH.read_text())


def test_contract_validates_against_schema(contract: dict) -> None:
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(contract, schema)


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
