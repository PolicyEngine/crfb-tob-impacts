"""Scorers apply the economic assumption reform a dataset was built under.

Invariants, each named by the tests that check it:

1. Order: on every scoring path the dataset's economic assumption reform
   applies first, its tax assumption reform second, and anything else (the
   solvency rates, the policy) after them.
2. Same assumptions on both sides: a reform simulation's reforms begin with
   exactly the baseline's, and a behavioral simulation's baseline branch
   carries the baseline's reforms, so the difference carries no assumption.
3. Identity: a recorded module hash that differs from the loaded module's,
   or an active record without a reform path or a hash, raises.
4. No assumption, no change: a dataset without an economic assumption is
   scored with exactly the reforms it was scored with before.
5. Paths that apply only the tax assumption still refuse such a dataset.

The year runner and the differential against hand-composed reforms are in
tests/test_year_runner_economic_assumption.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from src import balanced_fix
from src import reform_full_h5_worker as worker
from src import tax_assumption_loader as loader
from tests import pipeline_fakes as fakes
from tests import scoring_fakes as sf
from tests.pipeline_fakes import FakeEconomicReform, FakeTaxReform, flatten_reform
from tests.scoring_fakes import FakePolicyReform, FakeRateReform

YEAR = 2050
WRONG_SHA = "0" * 64


@pytest.fixture(autouse=True)
def _fake_tax_reform(monkeypatch):
    sf.patch_tax_reform(monkeypatch)


def _metadata(year=YEAR, *, economic=None):
    return sf.dataset_metadata(year, economic=economic)


# ---------------------------------------------------------------------------
# The loader
# ---------------------------------------------------------------------------


def test_compose_reforms_moved_to_the_loader_and_pipeline_reexports_it():
    from src import pipeline

    assert pipeline.compose_reforms is loader.compose_reforms
    assert pipeline.load_economic_assumption_reform is (
        loader.load_economic_assumption_reform
    )
    assert pipeline.economic_assumption_provenance is (
        loader.economic_assumption_provenance
    )


@pytest.mark.parametrize("year", [2030, 2050])
def test_scoring_reform_is_economic_then_tax(year):
    reform = loader.load_scoring_assumption_reform_for_metadata(
        _metadata(year, economic=sf.economic_record()), year
    )
    expected = (
        (FakeEconomicReform, FakeTaxReform) if year >= 2035 else (FakeEconomicReform,)
    )
    assert flatten_reform(reform) == expected


@pytest.mark.parametrize(
    "economic",
    [None, {}, sf.INACTIVE_RECORD, {"active": False}],
    ids=["missing", "empty", "built-without", "bare-inactive"],
)
def test_without_an_economic_assumption_the_scoring_reform_is_the_tax_reform(
    economic,
):
    metadata = _metadata(economic=sf.INACTIVE_RECORD)
    if economic is None:
        del metadata["economic_assumption"]
    else:
        metadata["economic_assumption"] = economic
    scoring = loader.load_scoring_assumption_reform_for_metadata(metadata, YEAR)
    assert scoring is loader.load_tax_assumption_reform_for_metadata(metadata, YEAR)
    assert scoring is FakeTaxReform
    assert loader.scoring_assumptions_from_metadata(
        metadata, YEAR
    ).economic_assumption == loader.EconomicAssumptionContract(active=False)


def test_economic_record_names_the_reform_and_its_hash():
    contract = loader.economic_assumption_contract_from_metadata(
        _metadata(economic=sf.economic_record())
    )
    assert contract == loader.EconomicAssumptionContract(
        active=True,
        reform=sf.ECONOMIC_SPEC,
        module_sha256=sf.sha256(Path(fakes.__file__)),
    )


@pytest.mark.parametrize(
    "record,message",
    [
        ({"active": True}, "no module:attribute"),
        ({"active": True, "reform": None, "module_sha256": "a"}, "no module:attr"),
        ({"active": True, "reform": "pkg.mod", "module_sha256": "a"}, "no module"),
        ({"active": True, "reform": ":attr", "module_sha256": "a"}, "no module"),
        ({"active": True, "reform": "pkg.mod:attr"}, "records no module_sha256"),
        (
            {"active": True, "reform": "pkg.mod:attr", "module_sha256": ""},
            "records no module_sha256",
        ),
        (
            {
                "active": True,
                "reform": "pkg.mod:attr",
                "module_sha256": "a",
                "applies_before": "policy",
            },
            "applies before 'policy'",
        ),
        ({"active": "yes", "reform": "pkg.mod:attr"}, "true or false"),
        ({"active": 1, "reform": "pkg.mod:attr"}, "true or false"),
        ({"active": False, "reform": "pkg.mod:attr"}, "inactive but names"),
        (["pkg.mod:attr"], "Malformed"),
    ],
)
def test_malformed_economic_records_fail_closed(record, message):
    metadata = _metadata()
    metadata["economic_assumption"] = record
    with pytest.raises(ValueError, match=message):
        loader.economic_assumption_contract_from_metadata(metadata)
    with pytest.raises(ValueError, match=message):
        loader.load_scoring_assumption_reform_for_metadata(metadata, YEAR)


def test_a_changed_module_hash_raises_naming_both_hashes():
    metadata = _metadata(economic=sf.economic_record(module_sha256=WRONG_SHA))
    actual = sf.sha256(Path(fakes.__file__))
    with pytest.raises(ValueError) as error:
        loader.load_scoring_assumption_reform_for_metadata(metadata, YEAR)
    assert WRONG_SHA in str(error.value)
    assert actual in str(error.value)


def test_editing_the_module_after_the_build_raises(monkeypatch, tmp_path):
    module = tmp_path / "edited_assumption_module.py"
    module.write_text(
        "from policyengine_core.reforms import Reform\n"
        "class trustees(Reform):\n"
        "    pass\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = "edited_assumption_module:trustees"
    metadata = _metadata(
        economic={
            "active": True,
            "applies_before": "tax_assumption",
            **loader.economic_assumption_provenance(spec),
        }
    )
    built_sha = metadata["economic_assumption"]["module_sha256"]
    loaded = loader.load_economic_assumption_reform_for_metadata(metadata)
    assert loaded.__name__ == "trustees"

    module.write_text(module.read_text() + "# edited after the build\n")
    try:
        with pytest.raises(ValueError, match=built_sha):
            loader.load_economic_assumption_reform_for_metadata(metadata)
        # A run that loaded the reform before the edit still records what it
        # applied: the output record does not hash the file again.
        contract = loader.economic_assumption_contract_from_metadata(metadata)
        record = loader.economic_assumption_output_metadata(contract)
        assert record["module_sha256"] == built_sha
        assert record["loaded_module_file"] == str(module)
    finally:
        sys.modules.pop("edited_assumption_module", None)


def test_a_mismatched_module_is_never_run(monkeypatch, tmp_path):
    marker = tmp_path / "ran"
    module = tmp_path / "unrun_assumption_module.py"
    module.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('ran')\n"
        "from policyengine_core.reforms import Reform\n"
        "class trustees(Reform):\n"
        "    pass\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    metadata = _metadata(
        economic={
            "active": True,
            "applies_before": "tax_assumption",
            "reform": "unrun_assumption_module:trustees",
            "module_sha256": WRONG_SHA,
        }
    )
    with pytest.raises(ValueError, match=WRONG_SHA):
        loader.load_economic_assumption_reform_for_metadata(metadata)
    assert not marker.exists()
    assert "unrun_assumption_module" not in sys.modules


def test_a_module_that_cannot_be_found_raises():
    metadata = _metadata(
        economic={
            "active": True,
            "reform": "no_such_assumption_module_anywhere:trustees",
            "module_sha256": WRONG_SHA,
        }
    )
    with pytest.raises(ValueError, match="cannot find the file"):
        loader.load_economic_assumption_reform_for_metadata(metadata)


def test_output_metadata_records_the_reform_and_hash():
    contract = loader.economic_assumption_contract_from_metadata(
        _metadata(economic=sf.economic_record())
    )
    assert loader.economic_assumption_output_metadata(contract) == {
        "active": True,
        "applies_before": "tax_assumption",
        "reform": sf.ECONOMIC_SPEC,
        "module_sha256": sf.sha256(Path(fakes.__file__)),
        "loaded_module_file": fakes.__file__,
    }
    assert loader.economic_assumption_output_metadata(
        loader.EconomicAssumptionContract(active=False)
    ) == {"active": False, "reform": None}


def test_tax_only_paths_still_refuse_a_dataset_with_an_economic_assumption(
    tmp_path,
):
    metadata = _metadata(economic=sf.economic_record())
    with pytest.raises(ValueError, match="does not apply"):
        loader.tax_assumption_contract_from_metadata(metadata, YEAR)
    with pytest.raises(ValueError, match="does not apply"):
        loader.load_tax_assumption_reform_for_metadata(metadata, YEAR)
    dataset = sf.write_dataset(tmp_path, YEAR, economic=sf.economic_record())
    with pytest.raises(ValueError, match="does not apply"):
        loader.tax_assumption_contract_for_dataset(dataset, YEAR)
    with pytest.raises(ValueError, match="does not apply"):
        loader.load_tax_assumption_reform_for_dataset(dataset, YEAR)


def test_scoring_assumptions_for_dataset_refuse_missing_post_2034_metadata(
    tmp_path,
):
    dataset = tmp_path / f"{YEAR}.h5"
    dataset.write_bytes(b"no sidecar")
    with pytest.raises(FileNotFoundError, match="metadata missing"):
        loader.scoring_assumptions_for_dataset(dataset, YEAR)


# ---------------------------------------------------------------------------
# The full-H5 worker
# ---------------------------------------------------------------------------


@pytest.fixture
def frame():
    return fakes.make_frame(YEAR, seed=11)


def test_worker_static_reform_is_economic_then_tax_then_policy(
    monkeypatch, tmp_path, frame
):
    dataset = sf.write_dataset(tmp_path / "data", YEAR, economic=sf.economic_record())
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)

    metadata = sf.run_worker(worker, dataset, YEAR, "static", tmp_path / "out")

    (sim,) = constructed
    assert flatten_reform(sim.reform) == (
        FakeEconomicReform,
        FakeTaxReform,
        FakePolicyReform,
    )
    assert metadata["behavioral_baseline_installation"] is None
    assert metadata["economic_assumption"]["reform"] == sf.ECONOMIC_SPEC
    assert metadata["economic_assumption"]["module_sha256"] == sf.sha256(
        Path(fakes.__file__)
    )
    written = json.loads(
        (
            worker.reform_full_h5_artifact_dir(
                tmp_path / "out" / "test", year=YEAR, reform_id="option1"
            )
            / "metadata.json"
        ).read_text()
    )
    assert written["economic_assumption"] == metadata["economic_assumption"]


def test_worker_behavioral_baseline_branch_carries_the_same_assumptions(
    monkeypatch, tmp_path, frame
):
    dataset = sf.write_dataset(tmp_path / "data", YEAR, economic=sf.economic_record())
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)

    metadata = sf.run_worker(worker, dataset, YEAR, "behavioral", tmp_path / "out")

    (sim,) = constructed
    branch = flatten_reform(sim.baseline.reform)
    scored = flatten_reform(sim.reform)
    assert branch == (FakeEconomicReform, FakeTaxReform)
    assert scored == (FakeEconomicReform, FakeTaxReform, FakePolicyReform)
    assert scored[: len(branch)] == branch
    assert sim.baseline.tax_benefit_system.reform == sim.baseline.reform
    assert metadata["behavioral_baseline_installation"]["installed"] is True
    assert metadata["economic_assumption"]["active"] is True


def test_worker_reads_the_assumption_from_the_approved_metadata(
    monkeypatch, tmp_path, frame
):
    # The approved metadata file is not the sidecar, and no sidecar exists, so
    # the run can only succeed by reading the economic assumption from it.
    directory = tmp_path / "data"
    directory.mkdir()
    dataset = directory / f"{YEAR}.h5"
    dataset.write_bytes(b"placeholder year dataset")
    approved = directory / f"approved-{YEAR}.json"
    approved.write_text(json.dumps(_metadata(economic=sf.economic_record())))
    manifest = directory / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "years": {
                    str(YEAR): {
                        "h5_sha256": sf.sha256(dataset),
                        "metadata_path": approved.name,
                        "metadata_sha256": sf.sha256(approved),
                    }
                }
            }
        )
    )
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)

    metadata = sf.run_worker(
        worker,
        dataset,
        YEAR,
        "behavioral",
        tmp_path / "out",
        baseline_dataset_manifest_path=manifest,
    )

    (sim,) = constructed
    assert flatten_reform(sim.baseline.reform) == (FakeEconomicReform, FakeTaxReform)
    assert flatten_reform(sim.reform)[-1] is FakePolicyReform
    assert metadata["economic_assumption"]["reform"] == sf.ECONOMIC_SPEC


@pytest.mark.parametrize("scoring_type", ["static", "behavioral"])
def test_worker_refuses_a_changed_module_hash(
    monkeypatch, tmp_path, frame, scoring_type
):
    dataset = sf.write_dataset(
        tmp_path / "data", YEAR, economic=sf.economic_record(module_sha256=WRONG_SHA)
    )
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)
    with pytest.raises(ValueError, match=WRONG_SHA):
        sf.run_worker(worker, dataset, YEAR, scoring_type, tmp_path / "out")
    assert constructed == []


@pytest.mark.parametrize(
    "scoring_type,expected_reform,expected_branch",
    [
        ("static", (FakeTaxReform, FakePolicyReform), None),
        ("behavioral", (FakeTaxReform, FakePolicyReform), FakeTaxReform),
    ],
)
def test_worker_without_an_economic_assumption_scores_as_before(
    monkeypatch, tmp_path, frame, scoring_type, expected_reform, expected_branch
):
    dataset = sf.write_dataset(tmp_path / "data", YEAR, economic=None)
    constructed = sf.patch_worker(monkeypatch, worker, frame=frame, year=YEAR)

    metadata = sf.run_worker(worker, dataset, YEAR, scoring_type, tmp_path / "out")

    (sim,) = constructed
    assert sim.reform == expected_reform
    assert sim.baseline.reform is expected_branch
    assert metadata["economic_assumption"] == {"active": False, "reform": None}
    assert metadata["tax_assumption"]["name"] == sf.TAX_NAME


# ---------------------------------------------------------------------------
# Balanced fix
# ---------------------------------------------------------------------------


class _Series:
    def __init__(self, values):
        self.values = np.asarray(values, dtype=float)

    def sum(self):
        return float(self.values.sum())


class _BalancedFixSim:
    def __init__(self, reform):
        self.reform = reform
        self.inputs = {}

    def calculate(self, variable, period=None, map_to=None):
        return _Series([100.0, 200.0])

    def set_input(self, variable, period, values):
        self.inputs[variable] = values


def _patch_balanced_fix(monkeypatch) -> list:
    built: list = []

    def dataset_microsimulation(dataset, reform=None, **kwargs):
        sim = _BalancedFixSim(reform)
        built.append(sim)
        return sim

    monkeypatch.setattr(
        balanced_fix, "dataset_microsimulation", dataset_microsimulation
    )
    monkeypatch.setattr(
        balanced_fix,
        "compute_scenario_aggregate_from_sim",
        lambda sim, *, year, progress=None: balanced_fix.ScenarioAggregate(
            *([1.0] * 8)
        ),
    )
    monkeypatch.setattr(
        balanced_fix,
        "compute_trust_fund_gap",
        lambda sim, *, year, hi_expenditures, progress=None: balanced_fix.TrustFundGap(
            ss_income=90.0,
            ss_benefits=100.0,
            ss_gap=-10.0,
            hi_income=50.0,
            hi_expenditures=60.0,
            hi_gap=-10.0,
        ),
    )
    monkeypatch.setattr(
        balanced_fix,
        "_calculate_sum",
        lambda sim, name, *, year, map_to=None: 1_000.0,
    )
    monkeypatch.setattr(
        balanced_fix,
        "payroll_rates_from_sim",
        lambda sim, *, year: balanced_fix.PayrollRates(0.062, 0.062, 0.0145, 0.0145),
    )
    monkeypatch.setattr(balanced_fix, "rate_reform_from_dict", lambda d: FakeRateReform)
    return built


def test_balanced_fix_stacks_economic_tax_rates_then_policy(monkeypatch, tmp_path):
    dataset = sf.write_dataset(tmp_path, YEAR, economic=sf.economic_record())
    built = _patch_balanced_fix(monkeypatch)

    state = balanced_fix.build_solvent_baseline_state(
        year=YEAR, dataset_path=dataset, hi_expenditures=60.0
    )
    balanced_fix.build_solvent_sim_from_state(state, extra_reform=FakePolicyReform)

    reforms = [flatten_reform(sim.reform) for sim in built]
    assumptions = (FakeEconomicReform, FakeTaxReform)
    assert reforms == [
        assumptions,  # current law
        assumptions,  # Stage-1 benefit cut
        (*assumptions, FakeRateReform),  # solvent baseline
        (*assumptions, FakeRateReform, FakePolicyReform),  # reform
    ]
    assert state.economic_assumption_contract.reform == sf.ECONOMIC_SPEC
    recorded = state.metadata_dict()["economic_assumption"]
    assert recorded["reform"] == sf.ECONOMIC_SPEC
    assert recorded["module_sha256"] == sf.sha256(Path(fakes.__file__))


def test_balanced_fix_refuses_a_changed_module_hash(monkeypatch, tmp_path):
    dataset = sf.write_dataset(
        tmp_path, YEAR, economic=sf.economic_record(module_sha256=WRONG_SHA)
    )
    built = _patch_balanced_fix(monkeypatch)
    with pytest.raises(ValueError, match=WRONG_SHA):
        balanced_fix.build_solvent_baseline_state(
            year=YEAR, dataset_path=dataset, hi_expenditures=60.0
        )
    assert built == []


def test_balanced_fix_without_an_economic_assumption_scores_as_before(
    monkeypatch, tmp_path
):
    dataset = sf.write_dataset(tmp_path, YEAR, economic=None)
    built = _patch_balanced_fix(monkeypatch)

    state = balanced_fix.build_solvent_baseline_state(
        year=YEAR, dataset_path=dataset, hi_expenditures=60.0
    )
    balanced_fix.build_solvent_sim_from_state(state, extra_reform=FakePolicyReform)

    assert [sim.reform for sim in built] == [
        FakeTaxReform,
        FakeTaxReform,
        (FakeTaxReform, FakeRateReform),
        (FakeTaxReform, FakeRateReform, FakePolicyReform),
    ]
    assert state.current_law_reform is FakeTaxReform
    assert state.metadata_dict()["economic_assumption"] == {
        "active": False,
        "reform": None,
    }


# ---------------------------------------------------------------------------
# Diagnostics scripts that build simulations on year datasets
# ---------------------------------------------------------------------------


class _Stop(Exception):
    pass


def _patch_microsimulation(monkeypatch) -> list:
    from scripts import audit_longrun_business_income
    from src import pipeline

    reforms: list = []

    class Microsimulation:
        def __init__(self, dataset=None, reform=None):
            reforms.append(reform)
            raise _Stop

    module = ModuleType("policyengine_us")
    module.Microsimulation = Microsimulation
    monkeypatch.setitem(sys.modules, "policyengine_us", module)
    # The audit script binds Microsimulation when it is imported.
    monkeypatch.setattr(
        audit_longrun_business_income, "Microsimulation", Microsimulation
    )
    monkeypatch.setattr(pipeline, "_tax_assumption_reform", lambda year: FakeTaxReform)
    return reforms


@pytest.mark.parametrize(
    "economic,expected",
    [
        (sf.economic_record, (FakeEconomicReform, FakeTaxReform)),
        (lambda: None, (FakeTaxReform,)),
    ],
    ids=["economic", "none"],
)
def test_diagnostics_scripts_apply_the_recorded_economic_reform_first(
    monkeypatch, tmp_path, economic, expected
):
    from scripts import (
        audit_longrun_business_income,
        build_baseline_diagnostics,
        build_tob_explainer_data,
    )

    reforms = _patch_microsimulation(monkeypatch)
    dataset = sf.write_dataset(tmp_path, YEAR, economic=economic())
    with pytest.raises(_Stop):
        build_baseline_diagnostics.year_aggregates(dataset, YEAR)
    with pytest.raises(_Stop):
        build_tob_explainer_data.build_context(tmp_path)
    with pytest.raises(_Stop):
        # The audit applies no tax assumption, before and after this change.
        audit_longrun_business_income.audit_h5(dataset, YEAR, ["income_tax"])
    audited = expected[:-1]
    assert [flatten_reform(reform) for reform in reforms] == [
        expected,
        expected,
        audited,
    ]
    if economic() is None:
        assert reforms == [FakeTaxReform, FakeTaxReform, None]
