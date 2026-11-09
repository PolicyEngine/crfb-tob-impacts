"""The economic assumption survives loss or alteration of the sidecar."""

from __future__ import annotations

import json

import h5py
import pytest

from src import tax_assumption_loader as loader

H5_ATTR = "policyengine_economic_assumption"
RECORD = {
    "active": True,
    "applies_before": "tax_assumption",
    "reform": "example_assumptions:income_growth",
    "module_sha256": "a" * 64,
    "inputs_aged_under_assumption": True,
    "input_aging_end_year": 2030,
}


def _dataset(tmp_path, *, embedded=None, sidecar=None):
    path = tmp_path / "year_2030.h5"
    with h5py.File(path, "w") as store:
        store.create_dataset("person_id/2030", data=[0])
        if embedded is not None:
            store.attrs[H5_ATTR] = json.dumps(embedded)
    if sidecar is not None:
        path.with_suffix(".h5.metadata.json").write_text(json.dumps(sidecar))
    return path


READERS = [
    pytest.param(loader.load_tax_assumption_metadata_for_dataset, id="metadata"),
    pytest.param(loader.load_economic_assumption_reform_for_dataset, id="economic"),
    pytest.param(
        lambda path: loader.tax_assumption_contract_for_dataset(path, 2030),
        id="tax-contract",
    ),
    pytest.param(
        lambda path: loader.scoring_assumptions_for_dataset(path, 2030),
        id="scoring-contract",
    ),
    pytest.param(
        lambda path: loader.load_scoring_assumption_reform_for_dataset(path, 2030),
        id="scoring-reform",
    ),
]


@pytest.mark.parametrize("reader", READERS)
def test_embedded_economic_assumption_refuses_a_missing_sidecar(tmp_path, reader):
    path = _dataset(tmp_path, embedded=RECORD)
    with pytest.raises(
        FileNotFoundError, match="economic assumption.*sidecar"
    ) as error:
        reader(path)
    assert str(path) in str(error.value)


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize(
    "sidecar_record",
    [
        {**RECORD, "reform": "other_assumptions:income_growth"},
        {**RECORD, "module_sha256": "b" * 64},
        {**RECORD, "input_aging_end_year": 2050},
        {"active": False, "reform": None},
        None,
    ],
    ids=["reform", "module-hash", "aging-end-year", "inactive", "missing"],
)
def test_embedded_and_sidecar_economic_records_must_agree(
    tmp_path, reader, sidecar_record
):
    metadata = {} if sidecar_record is None else {"economic_assumption": sidecar_record}
    path = _dataset(tmp_path, embedded=RECORD, sidecar=metadata)
    with pytest.raises(ValueError, match="economic assumption.*disagree") as error:
        reader(path)
    assert str(path) in str(error.value)


def test_matching_economic_records_retain_the_complete_sidecar(tmp_path):
    metadata = {"economic_assumption": RECORD, "year": 2030}
    path = _dataset(tmp_path, embedded=RECORD, sidecar=metadata)
    assert loader.load_tax_assumption_metadata_for_dataset(path) == metadata
    assert loader.scoring_assumptions_for_dataset(path, 2030).economic_assumption.active


@pytest.mark.parametrize("sidecar", [None, {"year": 2030}])
def test_no_embedded_or_sidecar_assumption_remains_allowed(tmp_path, sidecar):
    path = _dataset(tmp_path, sidecar=sidecar)
    assert not loader.scoring_assumptions_for_dataset(path, 2030).active
    assert loader.load_scoring_assumption_reform_for_dataset(path, 2030) is None


def test_embedded_inactive_record_needs_no_sidecar(tmp_path):
    path = _dataset(tmp_path, embedded={"active": False, "reform": None})
    assert not loader.scoring_assumptions_for_dataset(path, 2030).active


@pytest.mark.parametrize(
    "reader",
    [
        loader.tax_assumption_contract_for_dataset,
        loader.scoring_assumptions_for_dataset,
    ],
)
def test_inactive_economic_record_does_not_replace_a_long_run_tax_contract(
    tmp_path, reader
):
    path = _dataset(tmp_path, embedded={"active": False, "reform": None})
    with pytest.raises(FileNotFoundError, match="post-2034"):
        reader(path, 2050)


def test_legacy_sidecar_only_assumption_remains_readable(tmp_path):
    metadata = {"economic_assumption": RECORD}
    path = _dataset(tmp_path, sidecar=metadata)
    assert loader.load_tax_assumption_metadata_for_dataset(path) == metadata
