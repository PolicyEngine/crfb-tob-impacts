from pathlib import Path

import numpy as np
import pytest

from scripts.recover_modal_scenario_artifacts import (
    combine_scenario_artifacts,
    validate_expected_scenario_artifacts,
)


def _write_scenario(
    output_dir: Path,
    *,
    year: int,
    scenario_id: str,
    revenue: float,
    volume_prefix: str = "run-prefix",
    scoring: str = "static",
) -> None:
    artifact_dir = output_dir / "scenarios" / f"year={year}" / f"scenario={scenario_id}"
    artifact_dir.mkdir(parents=True)
    np.savez_compressed(
        artifact_dir / "metrics.npz",
        household_ids=np.array([1]),
        income_tax=np.array([revenue]),
        tob_medicare_hi=np.array([2.0]),
        tob_oasdi=np.array([3.0]),
        social_security=np.array([100.0]),
        taxable_payroll=np.array([200.0]),
        employer_ss_tax_revenue=np.array([4.0]),
        employer_medicare_tax_revenue=np.array([5.0]),
    )
    np.savez_compressed(
        artifact_dir / "weights.npz",
        household_ids=np.array([1]),
        household_weights=np.array([1.0]),
    )
    (artifact_dir / "aggregates.json").write_text(
        "\n".join(
            [
                "{",
                f'  "revenue": {revenue},',
                '  "tob_medicare_hi": 2.0,',
                '  "tob_oasdi": 3.0,',
                '  "tob_total": 5.0,',
                '  "social_security": 100.0,',
                '  "taxable_payroll": 200.0,',
                '  "employer_ss_tax_revenue": 4.0,',
                '  "employer_medicare_tax_revenue": 5.0',
                "}",
            ]
        ),
        encoding="utf-8",
    )
    (artifact_dir / "metadata.json").write_text(
        "\n".join(
            [
                "{",
                '  "artifact_version": 1,',
                f'  "volume_prefix": "{volume_prefix}",',
                f'  "year": {year},',
                f'  "scenario_id": "{scenario_id}",',
                f'  "scoring_type": "{scoring}",',
                '  "tax_assumption": {"name": null, "active": false}',
                "}",
            ]
        ),
        encoding="utf-8",
    )


def test_validate_expected_scenario_artifacts_rejects_stale_volume_prefix(tmp_path):
    _write_scenario(
        tmp_path,
        year=2026,
        scenario_id="baseline",
        revenue=10.0,
        volume_prefix="old-run",
    )

    with pytest.raises(RuntimeError, match="volume_prefix"):
        validate_expected_scenario_artifacts(
            output_dir=tmp_path,
            scenarios=["baseline"],
            years=[2026],
            scoring="static",
            volume_prefix="new-run",
        )


def test_combine_scenario_artifacts_derives_delta_from_saved_aggregates(tmp_path):
    _write_scenario(tmp_path, year=2026, scenario_id="baseline", revenue=10.0)
    _write_scenario(tmp_path, year=2026, scenario_id="option1", revenue=15.0)

    validate_expected_scenario_artifacts(
        output_dir=tmp_path,
        scenarios=["baseline", "option1"],
        years=[2026],
        scoring="static",
        volume_prefix="run-prefix",
    )

    output = tmp_path / "combined.csv"
    combine_scenario_artifacts(
        output_dir=tmp_path,
        combined_output=output,
        reforms=["option1"],
        years=[2026],
        scoring="static",
    )

    assert "revenue_impact" in output.read_text(encoding="utf-8")
    assert ",5.0," in output.read_text(encoding="utf-8")
