from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "batch" / "run_option13_modal.py"
BUILDER_PATH = REPO_ROOT / "scripts" / "build_latesthf_14option_delivery.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_hi_data_extrapolates_2100():
    module = _load_module("run_option13_modal_test", RUNNER_PATH)

    module.HI_DATA = None
    hi = module.get_hi_data()

    assert 2100 in hi
    extrapolated = hi[2100]
    assert math.isclose(
        extrapolated["cost_rate"],
        0.045066666666666644,
        rel_tol=0,
        abs_tol=1e-12,
    )
    assert math.isclose(
        extrapolated["hi_taxable_payroll"],
        232_316_852_933_334.0,
        rel_tol=0,
        abs_tol=1.0,
    )
    assert math.isclose(
        extrapolated["hi_expenditures"],
        10_492_177_502_613.5,
        rel_tol=0,
        abs_tol=1.0,
    )


def test_runtime_path_prefers_local_repo_when_container_mount_missing():
    module = _load_module("run_option13_modal_runtime_path_test", RUNNER_PATH)

    resolved = module.runtime_path("src")

    assert resolved == REPO_ROOT / "src"


def test_configure_runtime_snapshot_env_sets_dataset_roots(monkeypatch, tmp_path):
    module = _load_module("run_option13_modal_snapshot_env_test", RUNNER_PATH)

    monkeypatch.setattr(module, "CONTAINER_SNAPSHOT_DIR", tmp_path)
    monkeypatch.delenv("CRFB_PROJECTED_DATASETS_PATH", raising=False)
    monkeypatch.delenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", raising=False)

    module.configure_runtime_snapshot_env()

    expected = str(tmp_path)
    assert os.environ["CRFB_PROJECTED_DATASETS_PATH"] == expected
    assert os.environ["CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH"] == expected


def test_results_root_uses_explicit_output_prefix():
    module = _load_module("run_option13_modal_results_root_test", RUNNER_PATH)

    resolved = module.results_root("special_case_reruns/smoke")

    assert resolved == Path("/results/special_case_reruns/smoke")


def test_default_output_prefix_uses_special_case_namespace():
    module = _load_module("run_option13_modal_default_prefix_test", RUNNER_PATH)

    prefix = module.default_output_prefix()

    assert prefix.startswith("special_case_reruns/option13-14-")


def test_default_submission_manifest_path_matches_output_prefix():
    module = _load_module("run_option13_modal_manifest_path_test", RUNNER_PATH)

    manifest = module.default_submission_manifest_path(
        "special_case_reruns/option13-14-exact"
    )

    assert manifest == (
        REPO_ROOT
        / "results"
        / "special_case_submissions"
        / "special_case_reruns__option13-14-exact.json"
    )


def test_option13_row_reconstructs_levels_from_standard_baseline():
    module = _load_module("build_latesthf_14option_delivery_test", BUILDER_PATH)

    option13_raw = {
        "year": 2035,
        "baseline_income_tax": 4_733_311_731_000.0,
        "reform_income_tax": 4_707_518_915_500.0,
        "income_tax_impact": -25_792_815_500.0,
        "tob_oasdi_impact": -14_799_809_302.985077,
        "tob_hi_impact": -10_992_222_122.872375,
        "rate_increase_ss_revenue": 252_347_760_028.20483,
        "rate_increase_hi_revenue": 167_315_029_647.49268,
        "tob_oasdi_loss": 14_799_809_302.985077,
        "tob_hi_loss": 10_992_222_122.872375,
        "benefit_cut": 222_748_019_043.32764,
    }
    baseline = {
        "year": 2035,
        "baseline_revenue": 5_317.543278196444,
        "baseline_tob_oasdi": 173.7881756511995,
        "baseline_tob_medicare_hi": 128.74066162906573,
        "baseline_tob_total": 302.52883728026523,
        "scoring_type": "static",
    }

    row = module.option13_row(option13_raw, baseline, "fallback-run")

    assert row["baseline_revenue"] == baseline["baseline_revenue"]
    assert math.isclose(
        row["reform_revenue"],
        baseline["baseline_revenue"] + option13_raw["income_tax_impact"] / 1e9,
        rel_tol=0,
        abs_tol=1e-9,
    )
    assert row["baseline_tob_oasdi"] == baseline["baseline_tob_oasdi"]
    assert row["baseline_tob_medicare_hi"] == baseline["baseline_tob_medicare_hi"]
    assert math.isclose(
        row["reform_tob_oasdi"],
        baseline["baseline_tob_oasdi"] + option13_raw["tob_oasdi_impact"] / 1e9,
        rel_tol=0,
        abs_tol=1e-9,
    )
    assert math.isclose(
        row["reform_tob_medicare_hi"],
        baseline["baseline_tob_medicare_hi"] + option13_raw["tob_hi_impact"] / 1e9,
        rel_tol=0,
        abs_tol=1e-9,
    )
    assert math.isclose(
        row["baseline_tob_oasdi"] + row["tob_oasdi_impact"],
        row["reform_tob_oasdi"],
        rel_tol=0,
        abs_tol=1e-9,
    )
    assert math.isclose(
        row["baseline_tob_medicare_hi"] + row["tob_medicare_hi_impact"],
        row["reform_tob_medicare_hi"],
        rel_tol=0,
        abs_tol=1e-9,
    )
    assert row["run_id"] == "fallback-run"


def test_option13_row_enforces_standard_static_baseline():
    module = _load_module("build_latesthf_14option_delivery_option13_baseline", BUILDER_PATH)

    option13_raw = {
        "year": 2035,
        "baseline_income_tax": 5_144_104_641_973.289,
        "reform_income_tax": 5_119_905_577_124.184,
        "income_tax_impact": -24_199_064_849.10547,
        "tob_oasdi_impact": -14_571_385_234.390778,
        "tob_hi_impact": -9_627_055_030.69548,
        "rate_increase_ss_revenue": 254_485_587_687.72977,
        "rate_increase_hi_revenue": 165_263_786_900.198,
        "tob_oasdi_loss": 14_571_385_234.390778,
        "tob_hi_loss": 9_627_055_030.69548,
        "benefit_cut": 239_914_188_899.12354,
    }
    standard_baseline = {
        "baseline_revenue": 5_317.543278196444,
        "baseline_tob_oasdi": 145.8450006894274,
        "baseline_tob_medicare_hi": 111.68300042779506,
        "baseline_tob_total": 257.52800111722246,
        "scoring_type": "static",
    }

    row = module.option13_row(
        option13_raw,
        standard_baseline,
        "fallback-run",
    )

    assert row["baseline_revenue"] == standard_baseline["baseline_revenue"]
    assert row["baseline_tob_oasdi"] == standard_baseline["baseline_tob_oasdi"]
    assert row["baseline_tob_medicare_hi"] == standard_baseline["baseline_tob_medicare_hi"]
    assert math.isclose(
        row["baseline_tob_oasdi"] + row["tob_oasdi_impact"],
        row["reform_tob_oasdi"],
        rel_tol=0,
        abs_tol=1e-9,
    )


def test_option14_row_uses_recovered_special_case_levels():
    module = _load_module("build_latesthf_14option_delivery_test2", BUILDER_PATH)

    raw = {
        "year": 2035,
        "baseline_income_tax": 5_119_905_577_124.184,
        "reform_income_tax": 5_377_938_150_000.0,
        "income_tax_impact": 258_032_572_875.816,
        "baseline_tob_oasdi": 126_402_746_000.0,
        "baseline_tob_hi": 91_951_161_000.0,
        "reform_tob_oasdi": 90_601_452_000.0,
        "reform_tob_hi": 99_963_805_000.0,
        "tob_oasdi_impact": -35_801_294_000.0,
        "tob_hi_impact": 8_012_644_000.0,
        "employer_ss_tax_revenue": 220_782_793_000.0,
        "employer_hi_tax_revenue": 68_717_378_000.0,
        "oasdi_gain": 220_782_793_000.0,
        "hi_gain": 68_717_378_000.0,
        "oasdi_loss": 35_801_294_000.0,
        "hi_loss": -8_012_644_000.0,
        "oasdi_net_impact": 184_981_499_000.0,
        "hi_net_impact": 76_730_022_000.0,
        "special_case_run_id": "option14-run",
    }

    row = module.option14_row(raw, "fallback-run")

    assert row["baseline_revenue"] == raw["baseline_income_tax"] / 1e9
    assert row["reform_revenue"] == raw["reform_income_tax"] / 1e9
    assert row["revenue_impact"] == raw["income_tax_impact"] / 1e9
    assert row["baseline_tob_oasdi"] == raw["baseline_tob_oasdi"] / 1e9
    assert row["reform_tob_oasdi"] == raw["reform_tob_oasdi"] / 1e9
    assert row["baseline_tob_medicare_hi"] == raw["baseline_tob_hi"] / 1e9
    assert row["reform_tob_medicare_hi"] == raw["reform_tob_hi"] / 1e9
    assert row["oasdi_net_impact"] == raw["oasdi_net_impact"] / 1e9
    assert row["hi_net_impact"] == raw["hi_net_impact"] / 1e9
    assert row["run_id"] == "option14-run"


def test_option14_raw_path_avoids_cross_lineage_standard_splice():
    module = _load_module("build_latesthf_14option_delivery_test3", BUILDER_PATH)

    option13_raw = {
        "year": 2035,
        "baseline_income_tax": 5_144_104_641_973.289,
        "reform_income_tax": 5_119_905_577_124.184,
        "income_tax_impact": -24_199_064_849.10547,
        "tob_oasdi_impact": -14_571_385_234.390778,
        "tob_hi_impact": -9_627_055_030.69548,
        "rate_increase_ss_revenue": 254_485_587_687.72977,
        "rate_increase_hi_revenue": 165_263_786_900.198,
        "tob_oasdi_loss": 14_571_385_234.390778,
        "tob_hi_loss": 9_627_055_030.69548,
        "benefit_cut": 239_914_188_899.12354,
    }
    option14_raw = {
        "year": 2035,
        "baseline_income_tax": 5_119_905_577_124.184,
        "reform_income_tax": 5_377_938_150_000.0,
        "income_tax_impact": 258_032_572_875.816,
        "baseline_tob_oasdi": 126_402_746_000.0,
        "baseline_tob_hi": 91_951_161_000.0,
        "reform_tob_oasdi": 90_601_452_000.0,
        "reform_tob_hi": 99_963_805_000.0,
        "tob_oasdi_impact": -35_801_294_000.0,
        "tob_hi_impact": 8_012_644_000.0,
        "employer_ss_tax_revenue": 220_782_793_000.0,
        "employer_hi_tax_revenue": 68_717_378_000.0,
        "oasdi_gain": 220_782_793_000.0,
        "hi_gain": 68_717_378_000.0,
        "oasdi_loss": 35_801_294_000.0,
        "hi_loss": -8_012_644_000.0,
        "oasdi_net_impact": 184_981_499_000.0,
        "hi_net_impact": 76_730_022_000.0,
    }
    standard = {
        "year": 2035,
        "reform_name": "option1",
        "baseline_revenue": 5_317.543278196444,
        "baseline_tob_oasdi": 145.8450006894274,
        "baseline_tob_medicare_hi": 111.68300042779506,
        "baseline_tob_total": 257.52800111722246,
        "scoring_type": "static",
    }
    option12_standard = dict(standard)
    option12_standard.update(
        {
            "reform_name": "option12",
            "reform_revenue": 5_560.776495863254,
            "reform_tob_oasdi": 93.87973824189643,
            "reform_tob_medicare_hi": 108.41530344717678,
            "revenue_impact": 243.23321766680992,
        }
    )

    option13 = module.option13_row(option13_raw, standard, "fallback-run")
    option14 = module.option14_row(option14_raw, "fallback-run")

    assert option13["baseline_revenue"] == standard["baseline_revenue"]
    assert option14["baseline_revenue"] == option14_raw["baseline_income_tax"] / 1e9
    assert option14["baseline_revenue"] != option13["reform_revenue"]
    assert option14["reform_revenue"] != option12_standard["reform_revenue"]
    assert option14["revenue_impact"] != (
        option12_standard["reform_revenue"] - option13["reform_revenue"]
    )
