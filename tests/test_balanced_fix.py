from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import pytest

from src.balanced_fix import (
    BALANCED_FIX_ANCHOR_YEARS,
    BALANCED_FIX_HEAVY_SIMS_PER_YEAR,
    BALANCED_FIX_PUBLISH_ANCHOR_YEARS,
    BALANCED_FIX_REFORMS,
    BALANCED_FIX_SPOT_CHECK_YEARS,
    BaselineResult,
    CrossCheckResult,
    PayrollRates,
    ScenarioAggregate,
    balanced_fix_cost_estimate,
    balanced_fix_sim_count,
    build_rate_reform_dict,
    compute_trust_fund_gap,
    current_law_cross_check,
    result_row_with_split,
    validate_current_law_cross_check,
)
from src.hi_expenditures import get_hi_data


def test_modal_balanced_fix_defaults_are_endpoint_safe_and_nonpreemptible():
    import modal_batch.balanced_fix as modal_balanced_fix

    assert modal_balanced_fix.DEFAULT_RUN_PREFIX.startswith("balanced_fix_")
    assert "crfb-longrun-v2pop-tr2026-noclone-20260612" in (
        modal_balanced_fix.DEFAULT_DATASET_TEMPLATE
    )
    assert modal_balanced_fix.DEFAULT_DATASET_TEMPLATE.endswith("/{year}.h5")
    assert modal_balanced_fix.DEFAULT_SENTINEL_TEMPLATE.endswith(
        "/{year}.h5.metadata.json"
    )
    assert modal_balanced_fix.DEFAULT_BASELINE_MANIFEST.endswith(
        "baseline-dataset-manifest-v2pop-noclone.json"
    )
    assert modal_balanced_fix.RESOLVED_RUNTIME_ENV["CRFB_POLICYENGINE_VERSION"] == (
        "4.5.1"
    )
    assert modal_balanced_fix.RESOLVED_RUNTIME_ENV["CRFB_POLICYENGINE_US_SPEC"] == (
        "policyengine-us==1.700.2"
    )
    assert modal_balanced_fix._policyengine_package_spec() == "policyengine==4.5.1"
    assert modal_balanced_fix._container_project_path(
        modal_balanced_fix.LOCAL_PROJECT_ROOT
        / "docs/current/schemas/reform-full-h5-expected-schema-v2pop-2026-option1-local-proof.json"
    ) == (
        "/app/docs/current/schemas/"
        "reform-full-h5-expected-schema-v2pop-2026-option1-local-proof.json"
    )
    assert modal_balanced_fix._env_bool("not_set_for_test", True) is True


def test_modal_balanced_fix_write_json_handles_nested_timestamps(tmp_path):
    import modal_batch.balanced_fix as modal_balanced_fix

    path = tmp_path / "metadata.json"
    modal_balanced_fix._write_json(
        path,
        {
            "created_at": datetime(2026, 6, 18, 18, 30),
            "nested": {"source_date": date(2026, 6, 18)},
        },
    )

    assert json.loads(path.read_text()) == {
        "created_at": "2026-06-18T18:30:00",
        "nested": {"source_date": "2026-06-18"},
    }


def test_modal_balanced_fix_resolves_live_static_baseline_provenance(tmp_path):
    import modal_batch.balanced_fix as modal_balanced_fix

    static_cells = tmp_path / "static_cells.csv"
    pd.DataFrame(
        [
            {
                "year": 2035,
                "reform_name": "option1",
                "scoring_type": "static",
                "run_prefix": "early",
            },
            {
                "year": 2075,
                "reform_name": "option1",
                "scoring_type": "static",
                "run_prefix": "late",
            },
        ]
    ).to_csv(static_cells, index=False)
    early_manifest = tmp_path / "early.json"
    late_manifest = tmp_path / "late.json"
    early_manifest.write_text(
        json.dumps(
            {
                "run_id": "early-run",
                "source_sha": "early-sha",
                "dataset_template": "/baselines/early/{year}.h5",
                "datasets": [
                    {
                        "year": 2035,
                        "h5_path": "/baselines/early/2035.h5",
                        "h5_sha256": "h" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    late_manifest.write_text(
        json.dumps(
            {
                "run_id": "late-run",
                "source_sha": "late-sha",
                "dataset_template": "/baselines/late/{year}.h5",
                "datasets": [
                    {
                        "year": 2075,
                        "h5_path": "/baselines/late/2075.h5",
                        "h5_sha256": "a" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rel_map = {
        "early": str(early_manifest.relative_to(modal_balanced_fix.LOCAL_PROJECT_ROOT))
        if early_manifest.is_relative_to(modal_balanced_fix.LOCAL_PROJECT_ROOT)
        else str(early_manifest),
        "late": str(late_manifest.relative_to(modal_balanced_fix.LOCAL_PROJECT_ROOT))
        if late_manifest.is_relative_to(modal_balanced_fix.LOCAL_PROJECT_ROOT)
        else str(late_manifest),
    }

    records = modal_balanced_fix._baseline_records_for_years(
        [2035, 2075],
        static_cells_path=static_cells,
        run_prefix_manifest_map=rel_map,
    )

    assert records[2035]["dataset_path"] == "/baselines/early/2035.h5"
    assert records[2035]["expected_h5_sha256"] == "h" * 64
    assert records[2035]["live_static_run_prefix"] == "early"
    assert records[2075]["dataset_path"] == "/baselines/late/2075.h5"
    assert records[2075]["expected_h5_sha256"] == "a" * 64
    assert records[2075]["live_static_run_prefix"] == "late"


def test_modal_balanced_fix_refuses_runtime_mismatched_baseline_metadata(
    tmp_path,
    monkeypatch,
):
    import modal_batch.balanced_fix as modal_balanced_fix

    dataset = tmp_path / "2035.h5"
    dataset.write_bytes(b"not-a-real-h5")
    dataset.with_suffix(".h5.metadata.json").write_text(
        json.dumps({"policyengine_us": {"version": "1.700.2"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        modal_balanced_fix.package_metadata,
        "version",
        lambda package: "1.729.0" if package == "policyengine-us" else "unknown",
    )

    with pytest.raises(RuntimeError, match="runtime mismatch"):
        modal_balanced_fix._require_dataset_runtime_match(dataset)


def test_balanced_fix_endpoints_first_scope_and_sim_count():
    assert BALANCED_FIX_ANCHOR_YEARS == (2035, 2050, 2075, 2100)
    assert BALANCED_FIX_SPOT_CHECK_YEARS == (2065,)
    assert BALANCED_FIX_PUBLISH_ANCHOR_YEARS == (2035, 2050, 2065, 2075, 2100)
    assert BALANCED_FIX_REFORMS == ("option1", "option2", "option8", "option12")
    assert BALANCED_FIX_HEAVY_SIMS_PER_YEAR == 7
    assert balanced_fix_sim_count([2035]) == 7
    assert balanced_fix_sim_count(BALANCED_FIX_ANCHOR_YEARS) == 28

    estimate = balanced_fix_cost_estimate(BALANCED_FIX_ANCHOR_YEARS)
    assert estimate["heavy_sims"] == 28
    assert 40 <= estimate["low_usd"] < estimate["high_usd"] <= 120


def test_tr2026_hi_expenditures_cover_solvent_anchor_years():
    hi = get_hi_data()
    assert hi["year"].min() == 2035
    assert hi["year"].max() == 2100
    assert set(BALANCED_FIX_ANCHOR_YEARS).issubset(set(hi["year"]))

    anchors = hi[hi["year"].isin(BALANCED_FIX_ANCHOR_YEARS)].copy()
    reconstructed = anchors["cost_rate"] * anchors["hi_taxable_payroll"]
    relative_error = (reconstructed - anchors["hi_expenditures"]).abs() / anchors[
        "hi_expenditures"
    ]
    assert relative_error.max() < 1e-12


def test_rate_reform_dict_applies_half_gap_to_employee_and_employer_rates():
    reform = build_rate_reform_dict(
        year=2035,
        base_rates=PayrollRates(
            ss_employee=0.062,
            ss_employer=0.062,
            hi_employee=0.0145,
            hi_employer=0.0145,
        ),
        ss_rate_increase=0.02,
        hi_rate_increase=-0.004,
    )

    assert reform == {
        "gov.irs.payroll.social_security.rate.employee": {
            "2035-01-01.2035-12-31": 0.072
        },
        "gov.irs.payroll.social_security.rate.employer": {
            "2035-01-01.2035-12-31": 0.072
        },
        "gov.irs.payroll.medicare.rate.employee": {"2035-01-01.2035-12-31": 0.0125},
        "gov.irs.payroll.medicare.rate.employer": {"2035-01-01.2035-12-31": 0.0125},
    }


def test_trust_fund_gap_materializes_tob_pair_before_microseries_sums(monkeypatch):
    import src.balanced_fix as balanced_fix

    calls: list[int] = []
    monkeypatch.setattr(
        balanced_fix,
        "materialize_tob_revenue_pair",
        lambda sim, *, year, progress=None: calls.append(year),
    )

    class WeightedValue:
        def __init__(self, value: float):
            self.value = value

        def sum(self) -> float:
            return self.value

    class FakeSim:
        values = {
            "employee_social_security_tax": 1.0,
            "employer_social_security_tax": 2.0,
            "self_employment_social_security_tax": 3.0,
            "tob_revenue_oasdi": 4.0,
            "social_security": 11.0,
            "employee_medicare_tax": 5.0,
            "employer_medicare_tax": 6.0,
            "self_employment_medicare_tax": 7.0,
            "additional_medicare_tax": 8.0,
            "tob_revenue_medicare_hi": 9.0,
        }

        def calculate(
            self, variable_name: str, *, period: int, map_to: str | None = None
        ):
            assert period == 2035
            assert map_to is None
            return WeightedValue(self.values[variable_name])

    gap = compute_trust_fund_gap(FakeSim(), year=2035, hi_expenditures=40.0)

    assert calls == [2035]
    assert gap.ss_income == 10.0
    assert gap.ss_gap == -1.0
    assert gap.hi_income == 35.0
    assert gap.hi_gap == -5.0


def test_trust_fund_gap_can_reuse_materialized_tob_pair(monkeypatch):
    import src.balanced_fix as balanced_fix

    calls: list[int] = []
    monkeypatch.setattr(
        balanced_fix,
        "materialize_tob_revenue_pair",
        lambda sim, *, year, progress=None: calls.append(year),
    )

    class WeightedValue:
        def __init__(self, value: float):
            self.value = value

        def sum(self) -> float:
            return self.value

    class FakeSim:
        values = {
            "employee_social_security_tax": 1.0,
            "employer_social_security_tax": 2.0,
            "self_employment_social_security_tax": 3.0,
            "tob_revenue_oasdi": 4.0,
            "social_security": 11.0,
            "employee_medicare_tax": 5.0,
            "employer_medicare_tax": 6.0,
            "self_employment_medicare_tax": 7.0,
            "additional_medicare_tax": 8.0,
            "tob_revenue_medicare_hi": 9.0,
        }

        def calculate(
            self, variable_name: str, *, period: int, map_to: str | None = None
        ):
            assert period == 2035
            assert map_to is None
            return WeightedValue(self.values[variable_name])

    gap = compute_trust_fund_gap(
        FakeSim(),
        year=2035,
        hi_expenditures=40.0,
        materialize_tob=False,
    )

    assert calls == []
    assert gap.ss_income == 10.0
    assert gap.hi_income == 35.0


def test_current_law_cross_check_uses_live_static_baseline_columns(tmp_path):
    results = tmp_path / "results.csv"
    pd.DataFrame(
        [
            {
                "reform_name": "option1",
                "year": 2035,
                "scoring_type": "static",
                "baseline_revenue": 100.0,
                "baseline_tob_oasdi": 10.0,
            }
        ]
    ).to_csv(results, index=False)
    aggregate = ScenarioAggregate(
        revenue=100e9,
        tob_medicare_hi=1,
        tob_oasdi=10e9,
        tob_total=10e9 + 1,
        social_security=0,
        taxable_payroll=0,
        employer_ss_tax_revenue=0,
        employer_medicare_tax_revenue=0,
    )

    check = current_law_cross_check(
        year=2035,
        current_law_aggregate=aggregate,
        results_csv=results,
    )
    validate_current_law_cross_check(check)

    failed = CrossCheckResult(
        year=check.year,
        current_law_revenue_billions=90.0,
        live_baseline_revenue_billions=check.live_baseline_revenue_billions,
        current_law_oasdi_billions=check.current_law_oasdi_billions,
        live_baseline_oasdi_billions=check.live_baseline_oasdi_billions,
        revenue_relative_error=0.1,
        oasdi_relative_error=check.oasdi_relative_error,
        tolerance=check.tolerance,
    )
    with pytest.raises(ValueError, match="cross-check failed"):
        validate_current_law_cross_check(failed)


def test_option12_split_uses_employer_revenue_and_reconciles_general_fund():
    baseline = BaselineResult(
        revenue=1_000.0,
        tob_medicare_hi=50.0,
        tob_oasdi=100.0,
        tob_total=150.0,
        social_security=1_000.0,
        taxable_payroll=10_000.0,
        tax_assumption_name="trustees-2025-core-thresholds-v1",
        tax_assumption_active=True,
    )
    reform = ScenarioAggregate(
        revenue=920.0,
        tob_medicare_hi=20.0,
        tob_oasdi=30.0,
        tob_total=50.0,
        social_security=1_000.0,
        taxable_payroll=10_000.0,
        employer_ss_tax_revenue=40.0,
        employer_medicare_tax_revenue=10.0,
    )

    row = result_row_with_split(
        reform_id="option12",
        year=2035,
        baseline=baseline,
        reform_aggregate=reform,
    )

    assert row["revenue_impact"] == -80.0
    assert row["solvent_oasdi_impact"] == -30.0
    assert row["solvent_medicare_hi_impact"] == -20.0
    assert row["solvent_general_fund_impact"] == -30.0
    assert (
        row["solvent_oasdi_impact"]
        + row["solvent_medicare_hi_impact"]
        + row["solvent_general_fund_impact"]
        == row["revenue_impact"]
    )
