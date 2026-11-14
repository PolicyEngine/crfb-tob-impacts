from __future__ import annotations

import ast
import importlib.metadata as metadata
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from src import cli
from src import dashboard_baseline_assumptions as assumptions
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
        "91eb36576e364074ccd891a8e3096b587ba643a0",
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


# These stand-ins contain MOCK data only. They never import a country model or
# construct a microsimulation; the numbers do not represent tax amounts.
class Parameter:
    def __init__(self, name, uprating, mock_value=1.0):
        self.name = name
        self.metadata = {"uprating": uprating}
        self.mock_value = mock_value

    def __call__(self, instant):
        return self.mock_value


class _MockParameterGroup:
    def __init__(self, name, descendants=()):
        self.name = name
        self.descendants = list(descendants)

    def get_descendants(self):
        return list(self.descendants)


def _mock_indexed_parameter_data(monkeypatch):
    def forbid_model_construction():
        raise AssertionError("MOCK table tests must not construct a microsimulation")

    monkeypatch.setattr(
        assumptions, "_build_trustees_parameters", forbid_model_construction
    )
    parameters = SimpleNamespace()

    def set_path(path, value):
        current = parameters
        parts = path.split(".")
        for part in parts[:-1]:
            if not hasattr(current, part):
                setattr(current, part, SimpleNamespace())
            current = getattr(current, part)
        setattr(current, parts[-1], value)

    group_names = [
        "gov.irs.income.bracket.thresholds",
        "gov.irs.deductions.standard.amount",
        "gov.irs.deductions.standard.aged_or_blind.amount",
        "gov.irs.capital_gains.thresholds",
        "gov.irs.income.amt.brackets",
        "gov.irs.income.amt.exemption.amount",
        "gov.irs.income.amt.exemption.phase_out.start",
        "gov.irs.income.amt.exemption.separate_limit",
    ]
    groups = {name: _MockParameterGroup(name) for name in group_names}
    for name, group in groups.items():
        set_path(name, group)

    standard = "gov.irs.deductions.standard.amount"
    single = Parameter(f"{standard}.SINGLE", "gov.irs.uprating", 1.0)
    joint = Parameter(f"{standard}.JOINT", f"{standard}.SINGLE", 2.0)
    surviving = Parameter(f"{standard}.SURVIVING_SPOUSE", f"{standard}.SINGLE", 2.0)
    not_selected = Parameter(
        f"{standard}.MOCK_NOT_IN_REFORM", {"parameter": "gov.irs.uprating"}, 3.0
    )
    new_index = Parameter(
        "gov.irs.income.bracket.thresholds.MOCK_NEW_INDEX",
        "gov.irs.indexing.c_cpi_u",
        4.0,
    )
    outside_group = Parameter(
        "gov.irs.deductions.hsa.MOCK_OUTSIDE_GROUP",
        "gov.irs.indexing.hsa_c_cpi_u",
        5.0,
    )
    prefix_collision = Parameter(
        "gov.irs.deductions.standard.amount_extra.MOCK_PREFIX_COLLISION",
        "gov.irs.uprating",
        6.0,
    )
    groups[standard].descendants = [single, joint, surviving, not_selected, single]
    groups[group_names[0]].descendants = [new_index]
    # Preserve the selector's scalar-root contract: this selected display root
    # is a Parameter with no get_descendants method, rather than a group node.
    leaf = Parameter(group_names[-1], "gov.irs.indexing.c_cpi_u", 7.0)
    groups[group_names[-1]] = leaf
    set_path(group_names[-1], leaf)
    set_path("gov.irs.uprating", Parameter("gov.irs.uprating", None))
    set_path("gov.ssa.nawi", Parameter("gov.ssa.nawi", None))
    return SimpleNamespace(
        parameters=parameters,
        groups=groups,
        single=single,
        joint=joint,
        surviving=surviving,
        not_selected=not_selected,
        new_index=new_index,
        outside_group=outside_group,
        prefix_collision=prefix_collision,
        leaf=leaf,
    )


def _assert_mock_indexed_table_contract(tables, expected_names):
    long, summary, growth = tables
    assert list(long.columns) == [
        "parameter_group",
        "parameter_group_label",
        "parameter_name",
        "parameter_label",
        "uprating_parameter",
        "rounding",
        "year",
        "value",
    ]
    assert long["parameter_name"].drop_duplicates().tolist() == expected_names
    assert summary["parameter_name"].tolist() == expected_names
    assert not long.duplicated(["parameter_name", "year"]).any()
    assert set(long["year"]) == set(range(2026, 2101))
    assert len(long) == len(expected_names) * 75
    assert list(growth.columns) == ["year", "indexing_source", "growth_rate_pct"]
    assert growth["year"].tolist() == list(range(2026, 2101))
    assert growth["growth_rate_pct"].eq(0.0).all()


def test_indexed_tables_prefer_complete_reform_membership(monkeypatch):
    data = _mock_indexed_parameter_data(monkeypatch)
    calls = []

    def complete_membership(parameters):
        assert parameters is data.parameters
        calls.append(parameters)
        # Deliberately not display order: membership must not reorder the
        # existing groups or their parameter-tree order.
        return [
            data.surviving,
            data.outside_group,
            data.new_index,
            data.single,
            data.joint,
            data.single,
            data.prefix_collision,
            data.leaf,
        ]

    def legacy_selector(*args, **kwargs):
        raise AssertionError("Complete membership must take precedence")

    module = SimpleNamespace(
        trustees_core_threshold_parameters=complete_membership,
        iter_updatable_parameters=legacy_selector,
        _iter_updatable_parameters=legacy_selector,
    )
    tables = assumptions.build_indexed_parameter_tables(module, data.parameters)
    expected = [
        data.new_index.name,
        data.single.name,
        data.joint.name,
        data.surviving.name,
        data.leaf.name,
    ]
    _assert_mock_indexed_table_contract(tables, expected)
    assert calls == [data.parameters]
    long, _, _ = tables
    assert long["parameter_group"].drop_duplicates().tolist() == [
        "ordinary_income_brackets",
        "standard_deduction",
        "amt_separate_limit",
    ]
    assert (
        long.loc[long["parameter_name"].eq(data.joint.name), "uprating_parameter"]
        .eq(data.single.name)
        .all()
    )


@pytest.mark.parametrize(
    "helper_name", ["iter_updatable_parameters", "_iter_updatable_parameters"]
)
@pytest.mark.parametrize("accepts_keyword", [True, False])
def test_indexed_tables_keep_legacy_module_selectors(
    monkeypatch, helper_name, accepts_keyword
):
    data = _mock_indexed_parameter_data(monkeypatch)
    calls = []

    def select(root):
        calls.append(root.name)
        if root.name == "gov.irs.deductions.standard.amount":
            return [data.single, data.not_selected, data.single]
        return []

    def keyword_selector(root, *, uprating_parameter):
        assert uprating_parameter == "gov.irs.uprating"
        return select(root)

    module = SimpleNamespace(
        **{helper_name: keyword_selector if accepts_keyword else select}
    )
    tables = assumptions.build_indexed_parameter_tables(module, data.parameters)
    _assert_mock_indexed_table_contract(
        tables, [data.single.name, data.not_selected.name]
    )
    assert calls == list(data.groups)


def test_indexed_tables_keep_local_legacy_selector(monkeypatch):
    data = _mock_indexed_parameter_data(monkeypatch)
    tables = assumptions.build_indexed_parameter_tables(
        SimpleNamespace(), data.parameters
    )
    _assert_mock_indexed_table_contract(
        tables, [data.single.name, data.not_selected.name]
    )


def test_complete_membership_errors_do_not_fall_back(monkeypatch):
    data = _mock_indexed_parameter_data(monkeypatch)

    def complete_membership(parameters):
        assert parameters is data.parameters
        raise TypeError("MOCK complete membership failed")

    def legacy_selector(root, **kwargs):
        return [data.single]

    module = SimpleNamespace(
        trustees_core_threshold_parameters=complete_membership,
        iter_updatable_parameters=legacy_selector,
    )
    with pytest.raises(TypeError, match="MOCK complete membership failed"):
        assumptions.build_indexed_parameter_tables(module, data.parameters)
