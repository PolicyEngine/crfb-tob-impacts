from __future__ import annotations

import csv
import json
from pathlib import Path

from src import cli
from src.selected_cells import (
    STANDARD_REFORMS,
    build_selected_cells,
    default_selected_years,
    metadata_path_for_cells,
    write_selected_cells,
)


def test_default_selected_years_include_budget_window_five_years_and_junctures():
    years = default_selected_years()

    assert years[:10] == tuple(range(2026, 2036))
    assert 2040 in years
    assert 2100 in years
    assert 2048 in years
    assert 2049 in years
    assert 2062 in years
    assert 2063 in years
    assert years == tuple(sorted(set(years)))


def test_build_selected_cells_defaults_to_standard_reforms():
    selected = build_selected_cells()

    assert selected.reforms == STANDARD_REFORMS
    assert len(selected.cells) == len(STANDARD_REFORMS) * len(default_selected_years())
    assert selected.cells[0] == ("option1", 2026)
    assert selected.cells[-1] == ("option12", 2100)
    assert selected.metadata["cell_count"] == len(selected.cells)


def test_write_selected_cells_outputs_csv_and_metadata(tmp_path: Path):
    output = tmp_path / "cells.csv"

    selected = write_selected_cells(
        output,
        reforms="option1,option12",
        years="2026-2027,2100",
    )

    with output.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    metadata = json.loads(metadata_path_for_cells(output).read_text(encoding="utf-8"))
    assert rows == [
        {"reform_id": "option1", "year": "2026"},
        {"reform_id": "option1", "year": "2027"},
        {"reform_id": "option1", "year": "2100"},
        {"reform_id": "option12", "year": "2026"},
        {"reform_id": "option12", "year": "2027"},
        {"reform_id": "option12", "year": "2100"},
    ]
    assert metadata["reforms"] == ["option1", "option12"]
    assert metadata["years"] == [2026, 2027, 2100]
    assert metadata["cell_count"] == len(selected.cells)


def test_cli_write_selected_cells_subcommand(tmp_path: Path):
    output = tmp_path / "cells.csv"

    assert (
        cli.main(
            [
                "write-selected-cells",
                "--output",
                str(output),
                "--reforms",
                "option7",
                "--years",
                "2030",
            ]
        )
        == 0
    )

    assert output.read_text(encoding="utf-8") == "reform_id,year\noption7,2030\n"


def test_cli_reform_full_h5_artifacts_subcommand(tmp_path: Path):
    output = tmp_path / "manifest.json"
    h5 = tmp_path / "scenario.h5"
    import pandas as pd

    with pd.HDFStore(h5, mode="w") as store:
        store.put(
            "person",
            pd.DataFrame({"person_id": [1], "person_weight": [1.0]}),
            format="table",
        )

    assert (
        cli.main(
            [
                "reform-full-h5-artifacts",
                "inspect",
                "--h5",
                str(h5),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    metadata = json.loads(output.read_text(encoding="utf-8"))
    assert metadata["entities"]["person"]["rows"] == 1
