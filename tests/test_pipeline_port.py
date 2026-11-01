"""The year builder on PolicyEngine US 2.x: name resolution, growth caps,
income guards and the economic assumption hook.

build_year runs here against the deterministic fake engine in
tests/pipeline_fakes.py, so these tests need no microdata and no country
model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import h5py
import numpy as np
import pandas as pd
import pytest

from src import pipeline
from tests import pipeline_fakes as fakes
from tests.pipeline_fakes import (
    FakeCapMovingTaxReform,
    FakeEconomicReform,
    FakeEngine,
    FakeParameters,
    FakeTaxReform,
    FakeVariable,
)

# The 1.x lists, as they stood before the port.
PRE_2X_LISTS = {
    "EARNINGS_SCALE_CANDIDATES": (
        "employment_income_before_lsr",
        "self_employment_income_before_lsr",
        "sstb_self_employment_income_before_lsr",
        "partnership_se_income",
        "farm_operations_income",
        "hourly_wage",
    ),
    "SOCIAL_SECURITY_SCALE_CANDIDATES": (
        "social_security_retirement",
        "social_security_disability",
        "social_security_survivors",
        "social_security_dependents",
    ),
    "OTHER_INCOME_SCALE_CANDIDATES": (
        "taxable_interest_income",
        "tax_exempt_interest_income",
        "qualified_dividend_income",
        "non_qualified_dividend_income",
        "long_term_capital_gains",
        "short_term_capital_gains",
        "non_sch_d_capital_gains",
        "taxable_ira_distributions",
        "taxable_pension_income",
        "tax_exempt_pension_income",
        "rental_income",
        "farm_rent_income",
        "estate_income",
        "partnership_s_corp_income",
        "miscellaneous_income",
    ),
    "GROWTH_CAP_VARIABLES": (
        "taxable_interest_income",
        "tax_exempt_interest_income",
        "qualified_dividend_income",
        "non_qualified_dividend_income",
        "long_term_capital_gains",
        "short_term_capital_gains",
        "non_sch_d_capital_gains",
        "taxable_ira_distributions",
        "taxable_pension_income",
        "tax_exempt_pension_income",
        "rental_income",
        "farm_rent_income",
        "estate_income",
        "partnership_s_corp_income",
        "miscellaneous_income",
        "qualified_bdc_income",
        "qualified_reit_and_ptp_income",
    ),
}
CURRENT_LISTS = {
    **pipeline.SCALE_LISTS,
    "GROWTH_CAP_VARIABLES": pipeline.GROWTH_CAP_VARIABLES,
}


# ---------------------------------------------------------------------------
# The lists themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("list_name", list(PRE_2X_LISTS))
def test_each_list_replaces_pre_2x_names_with_their_stored_leaves(list_name):
    expected = []
    for name in PRE_2X_LISTS[list_name]:
        expected.extend(pipeline.PRE_2X_NAME_LEAVES.get(name, (name,)))
    if list_name in ("OTHER_INCOME_SCALE_CANDIDATES", "GROWTH_CAP_VARIABLES"):
        index = expected.index("taxable_ira_distributions") + 1
        expected[index:index] = [
            "taxable_sep_distributions",
            "taxable_401k_distributions",
            "taxable_403b_distributions",
            "keogh_distributions",
        ]
    assert list(CURRENT_LISTS[list_name]) == expected


def test_no_pre_2x_aggregate_name_remains_in_any_list():
    stale = set(pipeline.PRE_2X_NAME_LEAVES)
    for list_name, names in CURRENT_LISTS.items():
        assert not stale.intersection(names), list_name
    for components in pipeline.INCOME_GUARD_GROUPS.values():
        assert "partnership_se_income" not in components


def test_known_absent_inputs_are_named_by_some_list_and_give_reasons():
    named = {name for names in CURRENT_LISTS.values() for name in names}
    for name, reason in pipeline.KNOWN_ABSENT_INPUTS.items():
        assert name in named
        assert reason.strip()


def test_scale_lists_are_disjoint_and_free_of_repeats():
    pipeline.assert_scale_lists_disjoint()


def test_overlapping_scale_lists_raise():
    with pytest.raises(ValueError, match="scaled twice"):
        pipeline.assert_scale_lists_disjoint(
            {"A": ("rental_income",), "B": ("estate_income", "rental_income")}
        )
    with pytest.raises(ValueError, match="scaled twice"):
        pipeline.assert_scale_lists_disjoint({"A": ("rental_income", "rental_income")})


def test_guards_leave_out_partnership_earnings_and_collectibles():
    components = {
        name for names in pipeline.INCOME_GUARD_GROUPS.values() for name in names
    }
    assert "partnership_self_employment_net_earnings" not in components
    assert "long_term_capital_gains_on_collectibles" not in components
    assert "partnership_s_corp_income" in components


# ---------------------------------------------------------------------------
# resolve_frame_columns
# ---------------------------------------------------------------------------


def _frame(year, names):
    return pd.DataFrame({f"{name}__{year}": [1.0, 2.0] for name in names})


def test_resolver_returns_columns_in_list_order():
    df = _frame(2050, ["b", "a", "c"])
    columns, absent = pipeline.resolve_frame_columns(
        df, ("a", "b", "c"), 2050, list_name="L"
    )
    assert columns == ["a__2050", "b__2050", "c__2050"]
    assert absent == {}


def test_resolver_names_every_unresolved_name_and_its_2x_leaves():
    df = _frame(2050, ["rental_income"])
    with pytest.raises(ValueError) as error:
        pipeline.resolve_frame_columns(
            df,
            ("rental_income", "partnership_s_corp_income", "not_a_thing"),
            2050,
            list_name="OTHER_INCOME_SCALE_CANDIDATES",
        )
    message = str(error.value)
    assert "OTHER_INCOME_SCALE_CANDIDATES" in message
    assert "partnership_s_corp_income" in message
    assert "partnership_income, s_corp_income" in message
    assert "not_a_thing" in message
    assert "rental_income (" not in message


def test_resolver_skips_known_absent_inputs_with_their_reason():
    name = "taxable_public_pension_income"
    df = _frame(2050, ["rental_income"])
    variables = {name: FakeVariable(uprating="x")}
    columns, absent = pipeline.resolve_frame_columns(
        df, ("rental_income", name), 2050, list_name="L", variables=variables
    )
    assert columns == ["rental_income__2050"]
    assert absent == {name: pipeline.KNOWN_ABSENT_INPUTS[name]}


@pytest.mark.parametrize(
    "variable",
    [
        None,
        FakeVariable(formulas={"2020-01-01": object()}),
        FakeVariable(adds=["a", "b"]),
    ],
)
def test_resolver_rejects_an_absent_input_the_engine_would_compute(variable):
    name = "taxable_public_pension_income"
    variables = {} if variable is None else {name: variable}
    with pytest.raises(ValueError, match="KNOWN_ABSENT_INPUTS"):
        pipeline.resolve_frame_columns(
            _frame(2050, []), (name,), 2050, list_name="L", variables=variables
        )


def test_resolver_rejects_a_repeated_name():
    with pytest.raises(ValueError, match="twice"):
        pipeline.resolve_frame_columns(
            _frame(2050, ["a"]), ("a", "a"), 2050, list_name="L"
        )


def test_a_frame_storing_a_pre_2x_aggregate_raises():
    df = _frame(2050, ["partnership_income", "partnership_s_corp_income"])
    with pytest.raises(ValueError, match="partnership_s_corp_income"):
        pipeline.reject_pre_2x_names_in_frame(df, 2050)
    pipeline.reject_pre_2x_names_in_frame(_frame(2050, ["partnership_income"]), 2050)


# ---------------------------------------------------------------------------
# Growth cap
# ---------------------------------------------------------------------------


def _cap_sim(growth_rates, *, variables=None):
    names = pipeline.GROWTH_CAP_VARIABLES
    variables = variables or {
        name: FakeVariable(uprating=f"calibration.fake.{name}") for name in names
    }
    return SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables=variables, parameters=FakeParameters(1.0, growth_rates)
        )
    )


def _cap_frame(year):
    names = [
        name
        for name in pipeline.GROWTH_CAP_VARIABLES
        if name not in pipeline.KNOWN_ABSENT_INPUTS
    ]
    return pd.DataFrame(
        {f"{name}__{year}": [100.0, 0.0, 50.0] for name in names + ["age"]}
    )


def test_growth_cap_scales_only_categories_growing_faster_than_gdp(monkeypatch):
    monkeypatch.setattr(pipeline, "_tr2026_gdp_growth", lambda a, b: 1.5)
    growth = {
        f"calibration.fake.{name}": 0.01 for name in pipeline.GROWTH_CAP_VARIABLES
    }
    fast = "qualified_dividend_income"
    growth[f"calibration.fake.{fast}"] = 0.05
    year = 2060
    df = _cap_frame(year)
    before = df.copy()
    audit: dict = {}

    factors = pipeline.cap_longrun_income_growth(df, _cap_sim(growth), year, audit)

    category_growth = 1.05 ** (year - pipeline.GROWTH_CAP_BASE_YEAR)
    assert factors == {fast: pytest.approx(1.5 / category_growth)}
    np.testing.assert_allclose(
        df[f"{fast}__{year}"], before[f"{fast}__{year}"] * 1.5 / category_growth
    )
    others = [c for c in df.columns if c != f"{fast}__{year}"]
    pd.testing.assert_frame_equal(df[others], before[others])
    assert audit[fast]["uprating_parameter"] == f"calibration.fake.{fast}"
    assert audit["rental_income"]["factor"] == 1.0
    assert set(audit) == set(pipeline.GROWTH_CAP_VARIABLES) - set(
        pipeline.KNOWN_ABSENT_INPUTS
    )


def test_growth_cap_raises_for_a_capped_variable_without_uprating(monkeypatch):
    monkeypatch.setattr(pipeline, "_tr2026_gdp_growth", lambda a, b: 1.5)
    variables = {
        name: FakeVariable(uprating=f"calibration.fake.{name}")
        for name in pipeline.GROWTH_CAP_VARIABLES
    }
    variables["partnership_income"] = FakeVariable(uprating=None)
    with pytest.raises(ValueError, match="partnership_income has no uprating"):
        pipeline.cap_longrun_income_growth(
            _cap_frame(2060), _cap_sim({}, variables=variables), 2060
        )


def test_growth_cap_compares_the_total_behind_a_per_capita_series(monkeypatch):
    monkeypatch.setattr(pipeline, "_tr2026_gdp_growth", lambda a, b: 1.5)
    year = 2060
    variables, growth, metadata = {}, {}, {}
    for name in pipeline.GROWTH_CAP_VARIABLES:
        total = f"calibration.gov.irs.soi.{name}"
        per_capita = f"{total}_per_capita"
        variables[name] = FakeVariable(uprating=per_capita)
        metadata[per_capita] = {"derived_from": total}
        # Per-capita growth stays under GDP's; the total grows faster.
        growth[per_capita] = 0.01
        growth[total] = 0.01
    fast = "partnership_income"
    growth[f"calibration.gov.irs.soi.{fast}"] = 0.05
    sim = SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables=variables,
            parameters=FakeParameters(1.0, growth, metadata),
        )
    )
    audit: dict = {}

    factors = pipeline.cap_longrun_income_growth(_cap_frame(year), sim, year, audit)

    total_growth = 1.05 ** (year - pipeline.GROWTH_CAP_BASE_YEAR)
    assert factors == {fast: pytest.approx(1.5 / total_growth)}
    assert audit[fast]["uprating_parameter"].endswith(f"{fast}_per_capita")
    assert audit[fast]["growth_parameter"] == f"calibration.gov.irs.soi.{fast}"


def test_growth_cap_raises_for_a_per_capita_series_without_its_total():
    variables = {
        name: FakeVariable(uprating=f"calibration.fake.{name}_per_capita")
        for name in pipeline.GROWTH_CAP_VARIABLES
    }
    with pytest.raises(ValueError, match="no derived_from total"):
        pipeline.cap_longrun_income_growth(
            _cap_frame(2030), _cap_sim({}, variables=variables), 2030
        )


def test_growth_cap_checks_names_and_uprating_even_before_2035():
    df = _cap_frame(2030).drop(columns=["s_corp_income__2030"])
    with pytest.raises(ValueError, match="s_corp_income"):
        pipeline.cap_longrun_income_growth(df, _cap_sim({}), 2030)
    assert (
        pipeline.cap_longrun_income_growth(_cap_frame(2030), _cap_sim({}), 2030) == {}
    )


# ---------------------------------------------------------------------------
# Income guards
# ---------------------------------------------------------------------------


class _GuardSim:
    def __init__(self, variables, values):
        self.tax_benefit_system = SimpleNamespace(variables=variables)
        self.values = values

    def calculate(self, variable, period, map_to):
        return SimpleNamespace(values=self.values.get(variable, np.zeros(2)))


def test_income_guards_raise_on_a_component_the_engine_lacks():
    components = {
        name for names in pipeline.INCOME_GUARD_GROUPS.values() for name in names
    }
    variables = {name: object() for name in components - {"estate_income"}}
    with pytest.raises(ValueError, match="estate_income"):
        pipeline._income_guard_vectors(_GuardSim(variables, {}), 2050)


def test_income_guards_sum_components_and_leave_out_zero_groups():
    components = {
        name for names in pipeline.INCOME_GUARD_GROUPS.values() for name in names
    }
    variables = {name: object() for name in components}
    values = {
        "short_term_capital_gains": np.array([1.0, 2.0]),
        "partnership_s_corp_income": np.array([10.0, 0.0]),
    }
    groups = pipeline._income_guard_vectors(_GuardSim(variables, values), 2050)
    assert list(groups) == ["income_guard_ordinary_nonpayroll_income"]
    np.testing.assert_array_equal(
        groups["income_guard_ordinary_nonpayroll_income"], [11.0, 2.0]
    )


# ---------------------------------------------------------------------------
# Economic assumption reform: loading and composition
# ---------------------------------------------------------------------------


def test_compose_reforms_keeps_order_and_drops_none():
    assert pipeline.compose_reforms(None, None) is None
    assert pipeline.compose_reforms("economic", None) == "economic"
    assert pipeline.compose_reforms(None, "tax") == "tax"
    assert pipeline.compose_reforms("economic", "tax") == ("economic", "tax")


def test_load_economic_assumption_reform_accepts_reform_classes_and_dicts(
    monkeypatch, tmp_path
):
    from policyengine_core.reforms import Reform

    module = tmp_path / "fake_assumption_module.py"
    module.write_text(
        "from policyengine_core.reforms import Reform\n"
        "class trustees(Reform):\n"
        "    def apply(self):\n"
        "        pass\n"
        "class Namespace:\n"
        "    reform = trustees\n"
        "def factory():\n"
        "    return trustees\n"
        "PAIR = (trustees, trustees)\n"
        "CAP = {'gov.irs.payroll.social_security.cap': {'2030-01-01': 250000}}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    loaded = pipeline.load_economic_assumption_reform("fake_assumption_module:trustees")
    assert isinstance(loaded, type) and issubclass(loaded, Reform)
    assert (
        pipeline.load_economic_assumption_reform(
            "fake_assumption_module:Namespace.reform"
        )
        is loaded
    )
    assert pipeline.load_economic_assumption_reform("fake_assumption_module:PAIR") == (
        loaded,
        loaded,
    )
    from_dict = pipeline.load_economic_assumption_reform("fake_assumption_module:CAP")
    assert isinstance(from_dict, type) and issubclass(from_dict, Reform)
    with pytest.raises(TypeError, match="factory"):
        pipeline.load_economic_assumption_reform("fake_assumption_module:factory")
    with pytest.raises(ValueError, match="module:attribute"):
        pipeline.load_economic_assumption_reform("fake_assumption_module")

    provenance = pipeline.economic_assumption_provenance(
        "fake_assumption_module:trustees"
    )
    assert provenance["reform"] == "fake_assumption_module:trustees"
    assert provenance["module_file"] == str(module)
    assert len(provenance["module_sha256"]) == 64


# ---------------------------------------------------------------------------
# build_year on the fake engine
# ---------------------------------------------------------------------------


def _growth_rates(fast=("qualified_dividend_income",)):
    rates = {
        f"calibration.fake.{name}": 0.02
        for name in fakes.frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)
    }
    for name in fast:
        rates[f"calibration.fake.{name}"] = 0.09
    return rates


def _build(monkeypatch, tmp_path, year, *, economic=None, tax=None, seed=0):
    engine = FakeEngine(year, fakes.make_frame(year, seed=seed), _growth_rates())
    fakes.install(monkeypatch, engine, tax_reform=tax)
    sentinel = pipeline.build_year(
        year,
        "fake-base",
        tmp_path,
        base_dataset_label="fake-base",
        economic_assumption_reform=economic,
    )
    metadata = json.loads((tmp_path / f"{year}.h5.metadata.json").read_text())
    with h5py.File(tmp_path / f"{year}.h5", "r") as handle:
        weights = handle[f"household_weight/{year}"][...]
    return engine, sentinel, metadata, weights


def test_build_year_scales_every_list_and_records_what_it_scaled(monkeypatch, tmp_path):
    year = 2040
    engine, sentinel, metadata, _ = _build(monkeypatch, tmp_path, year)
    scaling = metadata["value_scaling"]

    def resolved(names):
        return [
            f"{name}__{year}"
            for name in names
            if name not in pipeline.KNOWN_ABSENT_INPUTS
        ]

    assert scaling["earnings_columns"] == resolved(pipeline.EARNINGS_SCALE_CANDIDATES)
    assert scaling["social_security_columns"] == resolved(
        pipeline.SOCIAL_SECURITY_SCALE_CANDIDATES
    )
    assert scaling["other_income_columns"] == resolved(
        pipeline.OTHER_INCOME_SCALE_CANDIDATES
    )
    assert set(scaling["absent_inputs_left_unscaled"]) == set(
        pipeline.KNOWN_ABSENT_INPUTS
    )
    assert scaling["payroll_cap"] == fakes.CAP
    assert metadata["longrun_growth_caps"] == {
        "qualified_dividend_income": pytest.approx(
            metadata["longrun_growth_cap_audit"]["qualified_dividend_income"]["factor"]
        )
    }
    assert sentinel["gates_passed"] is True

    written = engine.written[str(tmp_path / f"{year}.h5")]
    base = engine.frame
    beneficiary = written[f"person_household_id__{year}"].isin(
        base.loc[
            base[[f"{n}__{year}" for n in pipeline.SOCIAL_SECURITY_SCALE_CANDIDATES]]
            .sum(axis=1)
            .gt(0),
            f"person_household_id__{year}",
        ]
    )
    gamma = scaling["gamma_other_income_scale"]
    for column in scaling["other_income_columns"]:
        expected = base[column].where(~beneficiary, base[column] * gamma)
        if column == f"qualified_dividend_income__{year}":
            expected = (
                expected * metadata["longrun_growth_caps"]["qualified_dividend_income"]
            )
        np.testing.assert_allclose(written[column], expected)
    for column in scaling["earnings_columns"]:
        np.testing.assert_allclose(
            written[column], base[column] * scaling["alpha_earnings_scale"]
        )


def test_build_year_raises_when_a_scaled_input_is_missing(monkeypatch, tmp_path):
    year = 2030
    frame = fakes.make_frame(year).drop(columns=[f"s_corp_income__{year}"])
    engine = FakeEngine(year, frame, _growth_rates())
    fakes.install(monkeypatch, engine)
    with pytest.raises(ValueError, match="s_corp_income"):
        pipeline.build_year(year, "fake-base", tmp_path)
    assert not (tmp_path / f"{year}.h5").exists()


def test_build_year_raises_when_the_frame_stores_a_pre_2x_aggregate(
    monkeypatch, tmp_path
):
    year = 2030
    frame = fakes.make_frame(year)
    frame[f"partnership_s_corp_income__{year}"] = 1.0
    fakes.install(monkeypatch, FakeEngine(year, frame, _growth_rates()))
    with pytest.raises(ValueError, match="partnership_s_corp_income"):
        pipeline.build_year(year, "fake-base", tmp_path)


def test_tax_only_paths_refuse_a_dataset_built_with_the_economic_reform():
    # Scorers load both reforms with load_scoring_assumption_reform_for_metadata
    # (tests/test_scoring_economic_assumption.py); a path that rebuilds only the
    # tax assumption still refuses the dataset.
    from src.tax_assumption_loader import (
        load_tax_assumption_reform_for_metadata,
        tax_assumption_contract_from_metadata,
    )

    metadata = {
        "economic_assumption": {"active": True, "reform": "pkg.mod:trustees_2026"},
        "tax_assumption": {"name": None},
    }
    with pytest.raises(ValueError, match="trustees_2026"):
        tax_assumption_contract_from_metadata(metadata, 2050)
    with pytest.raises(ValueError, match="does not apply"):
        load_tax_assumption_reform_for_metadata(metadata, 2050)
    metadata["economic_assumption"]["active"] = False
    assert tax_assumption_contract_from_metadata(metadata, 2050).active is False


@pytest.mark.parametrize("year,tax", [(2030, None), (2040, FakeTaxReform)])
def test_economic_reform_reaches_every_simulation_ahead_of_tax(
    monkeypatch, tmp_path, year, tax
):
    engine, sentinel, metadata, _ = _build(
        monkeypatch, tmp_path, year, economic=FakeEconomicReform, tax=tax
    )
    stages = {stage for stage, _ in engine.constructed}
    assert stages == {"stage_a", "writer", "vectors", "dataset"}
    for stage, reform in engine.constructed:
        parts = fakes.flatten_reform(reform)
        assert parts[0] is FakeEconomicReform, stage
        if stage in ("stage_a", "writer"):
            assert parts == (FakeEconomicReform,)
        else:
            assert parts == (FakeEconomicReform, *fakes.flatten_reform(tax))
    assert metadata["economic_assumption"]["active"] is True
    assert metadata["economic_assumption"]["reform"].endswith(":FakeEconomicReform")
    assert metadata["economic_assumption"]["inputs_aged_under_assumption"] is True
    assert metadata["economic_assumption"]["input_aging_end_year"] == year
    from src.tax_assumption_loader import H5_ECONOMIC_ASSUMPTION_ATTR

    with h5py.File(tmp_path / f"{year}.h5", "r") as handle:
        assert json.loads(handle.attrs[H5_ECONOMIC_ASSUMPTION_ATTR]) == metadata[
            "economic_assumption"
        ]
    assert sentinel["economic_assumption_reform"].endswith(":FakeEconomicReform")


def test_without_the_hook_the_build_is_unchanged(monkeypatch, tmp_path):
    engine, _, metadata, _ = _build(monkeypatch, tmp_path, 2040, tax=FakeTaxReform)
    for stage, reform in engine.constructed:
        expected = () if stage in ("stage_a", "writer") else (FakeTaxReform,)
        assert fakes.flatten_reform(reform) == expected, stage
    assert metadata["economic_assumption"] == {
        "active": False,
        "applies_before": "tax_assumption",
        "reform": None,
    }


def test_economic_marker_precedes_final_build_validation(monkeypatch, tmp_path):
    from src.tax_assumption_loader import (
        H5_ECONOMIC_ASSUMPTION_ATTR,
        load_tax_assumption_metadata_for_dataset,
    )

    engine = FakeEngine(2030, fakes.make_frame(2030), _growth_rates())
    fakes.install(monkeypatch, engine)
    monkeypatch.setattr(
        pipeline,
        "evaluate_publication_gates",
        lambda *args: {"passed": False, "failures": ["validation failed"]},
    )
    with pytest.raises(RuntimeError, match="publication gates failed"):
        pipeline.build_year(
            2030,
            "fake-base",
            tmp_path,
            economic_assumption_reform=FakeEconomicReform,
            economic_assumption_metadata={"module_sha256": "a" * 64},
        )
    assert not (tmp_path / "2030.h5.metadata.json").exists()
    with h5py.File(tmp_path / "2030.h5", "r") as handle:
        record = json.loads(handle.attrs[H5_ECONOMIC_ASSUMPTION_ATTR])
    assert record["active"] is True
    assert record["inputs_aged_under_assumption"] is True
    assert record["input_aging_end_year"] == 2030
    with pytest.raises(FileNotFoundError, match="sidecar"):
        load_tax_assumption_metadata_for_dataset(tmp_path / "2030.h5")


def test_cap_read_sees_the_economic_reform(monkeypatch, tmp_path):
    year = 2040
    base_dir, reform_dir = tmp_path / "base", tmp_path / "reform"
    _, base, base_meta, _ = _build(monkeypatch, base_dir, year, tax=FakeTaxReform)
    _, moved, moved_meta, _ = _build(
        monkeypatch,
        reform_dir,
        year,
        economic=FakeEconomicReform,
        tax=FakeTaxReform,
    )
    assert base_meta["value_scaling"]["payroll_cap"] == fakes.CAP
    assert moved_meta["value_scaling"]["payroll_cap"] == fakes.ECONOMIC_CAP
    # A higher cap makes the same payroll target reachable with lower earnings.
    assert moved["alpha_earnings_scale"] < base["alpha_earnings_scale"]
    assert moved["payroll_total_achieved"] == pytest.approx(
        base["payroll_total_achieved"]
    )


def test_a_composed_reform_that_moves_the_cap_raises(monkeypatch, tmp_path):
    with pytest.raises(RuntimeError, match="composed reform"):
        _build(monkeypatch, tmp_path, 2040, tax=FakeCapMovingTaxReform)


def _comparable(metadata):
    metadata = json.loads(json.dumps(metadata))
    metadata["sentinel"].pop("duration_seconds")
    return metadata


DETERMINISM_SCRIPT = """
import hashlib, json, sys
from pathlib import Path
import pytest
from src import pipeline
from tests import pipeline_fakes as fakes
year, out = 2050, Path(sys.argv[1])
rates = {f"calibration.fake.{n}": 0.02
         for n in fakes.frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)}
rates["calibration.fake.qualified_dividend_income"] = 0.09
engine = fakes.FakeEngine(year, fakes.make_frame(year, seed=7), rates)
with pytest.MonkeyPatch.context() as patch:
    fakes.install(patch, engine)
    pipeline.build_year(year, "fake-base", out,
                        economic_assumption_reform=fakes.FakeEconomicReform)
metadata = json.loads((out / f"{year}.h5.metadata.json").read_text())
metadata["sentinel"].pop("duration_seconds")
written = engine.written[str(out / f"{year}.h5")]
digest = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode())
digest.update(written.to_numpy().tobytes())
print(digest.hexdigest())
"""


def test_build_year_is_deterministic_across_processes(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    digests = []
    for hash_seed in ("1", "2"):
        out = tmp_path / f"seed{hash_seed}"
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        result = subprocess.run(
            [sys.executable, "-c", DETERMINISM_SCRIPT, str(out)],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        digests.append(result.stdout.strip().splitlines()[-1])
    assert digests[0] == digests[1]


def test_build_year_is_deterministic(monkeypatch, tmp_path):
    first = _build(monkeypatch, tmp_path / "a", 2040, economic=FakeEconomicReform)
    second = _build(monkeypatch, tmp_path / "b", 2040, economic=FakeEconomicReform)
    _, sentinel_a, metadata_a, weights_a = first
    _, sentinel_b, metadata_b, weights_b = second
    sentinel_a.pop("duration_seconds")
    sentinel_b.pop("duration_seconds")
    assert sentinel_a == sentinel_b
    assert _comparable(metadata_a) == _comparable(metadata_b)
    np.testing.assert_array_equal(weights_a, weights_b)
    pd.testing.assert_frame_equal(
        first[0].written[str(tmp_path / "a" / "2040.h5")],
        second[0].written[str(tmp_path / "b" / "2040.h5")],
    )
