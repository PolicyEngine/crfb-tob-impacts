from __future__ import annotations

import numpy as np

from src.tob_baseline import (
    build_tob_baseline_tr2026,
    HI_METHOD_CURRENT_LAW,
    HI_METHOD_MATCH_OASDI_PCT_CHANGE,
    POST_OBBBA_SCENARIO_ID,
    build_tob_baseline,
    validate_generated_baseline,
    validate_tob_baseline_manifest,
    write_tob_baseline,
    write_tob_baseline_manifest,
)


def test_build_tob_baseline_uses_source_backed_oasdi_series() -> None:
    baseline = build_tob_baseline(HI_METHOD_MATCH_OASDI_PCT_CHANGE)

    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["current_law_oasdi_billions"], 76.7901)
    assert np.isclose(row_2026["oasdi_nominal_delta_billions"], -16.2)
    assert np.isclose(row_2026["tob_oasdi_billions"], 60.5901)


def test_hi_bridge_can_hold_current_law_constant() -> None:
    baseline = build_tob_baseline(HI_METHOD_CURRENT_LAW)
    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["tob_hi_billions"], 52.1990)


def test_hi_bridge_can_match_oasdi_percentage_change() -> None:
    baseline = build_tob_baseline(HI_METHOD_MATCH_OASDI_PCT_CHANGE)
    row_2026 = baseline.loc[baseline["year"] == 2026].iloc[0]
    assert np.isclose(row_2026["tob_hi_billions"], 41.1868539030)
    assert np.isclose(row_2026["oasdi_share"], 0.5953219833)


def test_generated_baseline_validates() -> None:
    baseline = build_tob_baseline_tr2026()
    validate_generated_baseline(baseline)


def test_generated_baseline_manifest_marks_target_not_law(tmp_path) -> None:
    baseline_path = tmp_path / "ssa_tob_baseline_75year.csv"
    manifest_path = tmp_path / "ssa_tob_baseline_75year.manifest.json"
    baseline = build_tob_baseline_tr2026()
    write_tob_baseline(baseline, baseline_path)

    manifest = write_tob_baseline_manifest(baseline_path, manifest_path)
    validated = validate_tob_baseline_manifest(baseline_path, manifest_path)

    assert validated == manifest
    assert manifest["scenario_id"] == POST_OBBBA_SCENARIO_ID
    assert manifest["baseline_kind"] == "calibration_target"
    # TR2026 current law carries OBBBA natively; the series is law-based.
    assert manifest["not_law"] is False
    assert manifest["artifact_contract"]["reject_raw_current_law_substitution"] is True
