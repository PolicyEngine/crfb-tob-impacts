from __future__ import annotations

import pytest

from modal_batch.panel_spec import (
    PANEL_REFORMS,
    cell_key,
    needed_baseline_years,
    validate_scoring_year,
    wanted_cell_keys,
    years_for_scoring,
)
from src.selected_cells import default_selected_years


def test_behavioral_scoring_is_endpoint_only_on_canonical_years():
    years = list(default_selected_years())

    assert years_for_scoring("conventional", years) == [2026, 2100]
    assert years_for_scoring("behavioral", years) == [2026, 2100]
    assert years_for_scoring("static", years) == years


def test_static_plus_conventional_cell_count_is_not_per_year_behavioral():
    years = list(default_selected_years())
    cells = wanted_cell_keys(PANEL_REFORMS, years, ("static", "conventional"))

    assert len(PANEL_REFORMS) == 14
    assert len(years) == 27
    assert len(cells) == 378 + 28


def test_conventional_only_needs_only_endpoint_baselines():
    years = list(default_selected_years())

    assert needed_baseline_years(years, ("conventional",)) == [2026, 2100]
    assert needed_baseline_years(years, ("static", "conventional")) == years


def test_non_endpoint_behavioral_cell_is_refused():
    with pytest.raises(ValueError, match="endpoint-only"):
        validate_scoring_year("conventional", 2030)

    validate_scoring_year("conventional", 2026)
    validate_scoring_year("conventional", 2100)
    validate_scoring_year("static", 2030)


def test_cell_keys_keep_static_and_behavioral_outputs_separate():
    assert cell_key("option1", 2026, "static") == "option1_2026"
    assert cell_key("option1", 2026, "conventional") == "option1_2026_conventional"
