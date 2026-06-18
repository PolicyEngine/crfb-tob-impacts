from __future__ import annotations

from pathlib import Path


def test_run_panel_redo_flags_force_overwrite_paths_without_modal_import():
    source = Path("modal_batch/run_panel.py").read_text(encoding="utf-8")

    assert "force: bool = False" in source
    assert "if sentinel_path.exists() and not force:" in source
    assert "if force:" in source
    assert "score_path.unlink()" in source
    assert "score_cell.spawn(reform_id, year, scoring_type, force)" in source
    assert "score_cell.spawn(r, y, st, redo_scores)" in source
    assert (
        "build_one_year.spawn(y, reform_list, scoring_types, redo_baselines)" in source
    )


def test_run_panel_uses_modal_free_panel_spec_helpers():
    source = Path("modal_batch/run_panel.py").read_text(encoding="utf-8")

    assert "from modal_batch.panel_spec import" in source
    assert "needed_baseline_years(year_list, scoring_types)" in source
    assert "wanted_cell_keys(reform_list, year_list, scoring_types)" in source
    assert "validate_scoring_year(scoring_type, year)" in source
