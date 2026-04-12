from pathlib import Path

from src.modal_batch_helpers import (
    cell_output_paths,
    default_submission_manifest_path,
    parse_cells_file,
    parse_years,
)


def test_parse_years_supports_range_and_list():
    assert parse_years("2026-2028") == [2026, 2027, 2028]
    assert parse_years("2026, 2035,2100") == [2026, 2035, 2100]


def test_cell_output_paths_suffixes_scoring_and_creates_dir(tmp_path: Path):
    output_path, stem, output_dir = cell_output_paths(
        str(tmp_path / "dynamic_probe.csv"), "dynamic"
    )

    assert output_path == tmp_path / "dynamic_probe.csv"
    assert stem == "dynamic_probe_dynamic"
    assert output_dir == tmp_path / "dynamic_probe_dynamic"
    assert output_dir.exists()


def test_default_submission_manifest_path_uses_modal_submissions():
    manifest_path = default_submission_manifest_path(
        Path("/tmp/project"),
        "dynamic_probe_dynamic",
        "demo",
    )

    assert manifest_path.name == "dynamic_probe_dynamic_demo.json"
    assert manifest_path.parent.name == "modal_submissions"


def test_parse_cells_file_supports_reform_name_and_dedupes(tmp_path: Path):
    cells_file = tmp_path / "cells.csv"
    cells_file.write_text(
        "reform_name,year\noption1,2026\noption1,2026\noption7,2100\n",
        encoding="utf-8",
    )

    assert parse_cells_file(cells_file) == [("option1", 2026), ("option7", 2100)]
