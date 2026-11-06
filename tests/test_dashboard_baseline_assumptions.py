from __future__ import annotations

import importlib.metadata as metadata
import ast
import json
from pathlib import Path
import re

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
import pandas as pd

from src import cli
from src.dashboard_baseline_assumptions import build_calibration_targets

# PyPI no longer lists policyengine-us 1.729.0, the release that
# policyengine[us]==4.17.5 pins, so CI installs it from an archive of its
# version-bump commit. The guard accepts that one archive by its exact URL:
# other commits carry the same version label with different code.
POLICYENGINE_US_RELEASE_ARCHIVE = (
    "https://github.com/PolicyEngine/policyengine-us/archive/"
    "180410fe35209fb8201378c1b32dadd38051c342.tar.gz"
)


def _direct_url(package_name: str) -> dict | None:
    text = metadata.distribution(package_name).read_text("direct_url.json")
    return json.loads(text) if text else None


def _is_policyengine_us_release_archive(direct_url: dict) -> bool:
    return (
        "archive_info" in direct_url
        and direct_url.get("url") == POLICYENGINE_US_RELEASE_ARCHIVE
    )


def test_runtime_guard_accepts_only_the_release_archive():
    assert _is_policyengine_us_release_archive(
        {"url": POLICYENGINE_US_RELEASE_ARCHIVE, "archive_info": {}}
    )
    # A commit that carries the same version label with different code.
    other_commit = POLICYENGINE_US_RELEASE_ARCHIVE.replace(
        "180410fe35209fb8201378c1b32dadd38051c342",
        "91eb36576e" + "0" * 30,
    )
    assert not _is_policyengine_us_release_archive(
        {"url": other_commit, "archive_info": {}}
    )
    assert not _is_policyengine_us_release_archive(
        {"url": POLICYENGINE_US_RELEASE_ARCHIVE, "vcs_info": {}}
    )
    assert not _is_policyengine_us_release_archive(
        {"url": "file:///tmp/policyengine-us", "dir_info": {"editable": True}}
    )


def test_ci_installs_the_archive_the_guard_accepts():
    workflow = Path(".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert f"policyengine-us @ {POLICYENGINE_US_RELEASE_ARCHIVE}" in workflow


def test_package_runtime_uses_policyengine_py_with_trustees_assumption():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    pinned_policyengine = re.search(
        r'"policyengine\[us\]==(?P<version>[^"]+)"',
        pyproject,
    )
    assert pinned_policyengine is not None
    assert metadata.version("policyengine") == pinned_policyengine.group("version")
    assert Version(metadata.version("policyengine-us")) >= Version("1.691.10")
    assert Version(metadata.version("policyengine-core")) >= Version("3.26.1")
    # The installed policyengine-us must be the release policyengine pins,
    # however it was installed.
    us_requirements = [
        requirement
        for requirement in map(Requirement, metadata.requires("policyengine") or [])
        if canonicalize_name(requirement.name) == "policyengine-us"
    ]
    assert us_requirements
    for requirement in us_requirements:
        assert requirement.specifier.contains(
            metadata.version("policyengine-us"), prereleases=True
        )
    policyengine_direct_url = _direct_url("policyengine")
    if policyengine_direct_url is not None:
        assert (policyengine_direct_url.get("dir_info") or {}).get("editable") is True
    policyengine_us_direct_url = _direct_url("policyengine-us")
    if policyengine_us_direct_url is not None:
        assert _is_policyengine_us_release_archive(policyengine_us_direct_url)
    assert _direct_url("policyengine-core") is None

    distribution = metadata.distribution("policyengine-us")
    module_file = "policyengine_us/reforms/ssa/trustees_core_thresholds.py"
    assert module_file in {str(path) for path in distribution.files or []}

    module_source = distribution.locate_file(module_file).read_text(encoding="utf-8")
    module_ast = ast.parse(module_source)
    assumption_assignment = next(
        (
            node
            for node in module_ast.body
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "TRUSTEES_CORE_THRESHOLD_ASSUMPTION"
                    for target in node.targets
                )
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "TRUSTEES_CORE_THRESHOLD_ASSUMPTION"
            )
        ),
        None,
    )
    assert assumption_assignment is not None
    assumption_value = assumption_assignment.value
    assert isinstance(assumption_value, ast.Dict)
    assumption_name = next(
        (
            value.value
            for key, value in zip(assumption_value.keys, assumption_value.values)
            if isinstance(key, ast.Constant)
            and key.value == "name"
            and isinstance(value, ast.Constant)
        ),
        None,
    )
    assert assumption_name == ("trustees-2025-core-thresholds-v1")


def test_cli_help_exposes_dashboard_baseline_metadata_root(capsys):
    try:
        cli.main(["build-dashboard-baseline-assumptions", "--help"])
    except SystemExit as error:
        assert error.code == 0

    captured = capsys.readouterr()
    assert "--metadata-root" in captured.out
    assert "--policyengine-us-path" in captured.out


def test_cli_exposes_dashboard_baseline_assumption_builder(monkeypatch):
    calls: list[list[str]] = []

    def fake_main(argv: list[str] | None = None) -> int:
        calls.append(list(argv or []))
        return 0

    monkeypatch.setattr(cli.dashboard_baseline_assumptions, "main", fake_main)

    assert (
        cli.main(
            [
                "build-dashboard-baseline-assumptions",
                "--metadata-root",
                "tmp/projected-datasets",
                "--policyengine-us-path",
                "/tmp/policyengine-us",
            ]
        )
        == 0
    )
    assert calls == [
        [
            "--metadata-root",
            "tmp/projected-datasets",
            "--policyengine-us-path",
            "/tmp/policyengine-us",
        ]
    ]


def test_calibration_targets_prefer_h5_metadata_and_fill_public_fallbacks(tmp_path):
    metadata_path = tmp_path / "2026.h5.metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "year": 2026,
                "target_source": {
                    "name": "trustees_2025_current_law",
                    "sha256": "abc123",
                },
                "tax_assumption": {"name": "trustees-2025-core-thresholds-v1"},
                "calibration_audit": {
                    "calibration_quality": "exact",
                    "constraints": {
                        "ss_total": {
                            "target": 1_000_000_000,
                            "achieved": 999_999_000,
                            "error": -1_000,
                            "pct_error": -0.0001,
                        },
                        "oasdi_tob": {
                            "target": 60_000_000_000,
                            "achieved": 60_000_000_000,
                            "error": 0,
                            "pct_error": 0,
                        },
                    },
                    "constraint_provenance": {
                        "ss_total": {
                            "source": "metadata",
                            "classification": "hard",
                            "scoring_contract": "match annual SS benefits",
                        },
                        "oasdi_tob": {
                            "source": "metadata",
                            "classification": "hard",
                            "scoring_contract": "match annual OASDI TOB",
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = pd.DataFrame(
        [
            {
                "year": 2026,
                "oasdi_taxable_payroll": 11_129.0,
                "tob_oasdi": 60.59,
                "tob_hi": 41.19,
                "tax_assumption": "trustees-2025-core-thresholds-v1",
                "scenario_id": "crfb_post_obbba_tob_75y",
                "baseline_sha256": "def456",
            }
        ]
    )

    targets = build_calibration_targets(baseline, metadata_roots=[tmp_path])
    indexed = targets.set_index("constraint_name")

    assert indexed.loc["ss_total", "target"] == 1.0
    assert indexed.loc["ss_total", "achieved"] == 0.999999
    assert indexed.loc["ss_total", "source"] == "metadata"
    assert bool(indexed.loc["ss_total", "used_in_year_runner_reconciliation"])

    assert indexed.loc["oasdi_tob", "source"] == "metadata"
    assert (
        indexed.loc["payroll_total", "source"] == "dashboard_public_baseline_artifact"
    )
    assert indexed.loc["payroll_total", "target"] == 11_129.0
    assert indexed.loc["hi_tob", "target"] == 41.19
    assert targets["constraint_name"].value_counts()["oasdi_tob"] == 1
