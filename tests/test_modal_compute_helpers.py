from pathlib import Path

from src.modal_batch_helpers import (
    cell_output_paths,
    default_submission_manifest_path,
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
