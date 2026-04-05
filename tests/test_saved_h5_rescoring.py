from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "score_saved_h5_reforms.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "score_saved_h5_reforms", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_cache_path_includes_module_digest_and_policyengine_fingerprint(
    tmp_path,
):
    module = _load_script_module()
    dataset_path = tmp_path / "2090.h5"
    dataset_path.write_text("", encoding="utf-8")

    path_a = module.baseline_cache_path(
        dataset_path=dataset_path,
        module_path=tmp_path / "tax_assumptions.py",
        module_sha256="aaa",
        policyengine_fingerprint={"git_head": "one"},
        factory_name="factory",
        start_year=2035,
        end_year=2100,
        cache_dir=str(tmp_path / "cache"),
    )
    path_b = module.baseline_cache_path(
        dataset_path=dataset_path,
        module_path=tmp_path / "tax_assumptions.py",
        module_sha256="bbb",
        policyengine_fingerprint={"git_head": "one"},
        factory_name="factory",
        start_year=2035,
        end_year=2100,
        cache_dir=str(tmp_path / "cache"),
    )
    path_c = module.baseline_cache_path(
        dataset_path=dataset_path,
        module_path=tmp_path / "tax_assumptions.py",
        module_sha256="aaa",
        policyengine_fingerprint={"git_head": "two"},
        factory_name="factory",
        start_year=2035,
        end_year=2100,
        cache_dir=str(tmp_path / "cache"),
    )

    assert path_a != path_b
    assert path_a != path_c


def test_resolve_dataset_year_rejects_filename_metadata_mismatch(tmp_path):
    module = _load_script_module()
    dataset_path = tmp_path / "2090.h5"
    dataset_path.write_text("", encoding="utf-8")

    try:
        module.resolve_dataset_year(
            dataset_path,
            inferred_year=2090,
            metadata={"year": 2100},
        )
    except ValueError as error:
        assert "filename implies year 2090" in str(error)
        assert "metadata records year 2100" in str(error)
    else:
        raise AssertionError("Expected a filename/metadata year mismatch error")
