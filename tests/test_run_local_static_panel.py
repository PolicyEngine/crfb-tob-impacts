from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from scripts.run_local_static_panel import (
    PROVENANCE_COLUMNS,
    apply_publishable_contract,
    assert_existing_row_matches,
)


def test_existing_row_matches_accepts_package_hash_without_git_sha(tmp_path):
    row = {column: "value" for column in PROVENANCE_COLUMNS}
    row["dataset_policyengine_us_git_sha"] = ""
    row["dataset_policyengine_us_package_tree_sha256"] = "a" * 64

    assert_existing_row_matches(
        row,
        expected=row,
        output=tmp_path / "scores.csv",
        cell=(2026, "option1", "static"),
    )


def test_existing_row_matches_rejects_missing_git_sha_and_package_hash(tmp_path):
    row = {column: "value" for column in PROVENANCE_COLUMNS}
    row["dataset_policyengine_us_git_sha"] = ""
    row["dataset_policyengine_us_package_tree_sha256"] = ""
    row["dataset_policyengine_us_package_file_sha256"] = ""

    with pytest.raises(ValueError, match="git_sha_or_package_hash"):
        assert_existing_row_matches(
            row,
            expected=row,
            output=tmp_path / "scores.csv",
            cell=(2026, "option1", "static"),
        )


def test_no_managed_dataset_flag_overrides_truthy_env(monkeypatch):
    monkeypatch.setenv("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", "1")

    apply_publishable_contract(
        SimpleNamespace(
            required_calibration_profile=None,
            required_target_source=None,
            required_tax_assumption=None,
            required_policyengine_us_version=None,
            use_packaged_policyengine_us_contract=False,
            use_policyengine_py_managed_datasets=False,
        )
    )

    assert os.environ["CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS"] == "0"
