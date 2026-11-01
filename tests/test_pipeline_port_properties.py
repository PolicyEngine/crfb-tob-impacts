"""Property tests for the year builder's invariants.

Invariants (each holds for every input the strategies draw):

1. Every scaling and cap name resolves to its frame column, sits on
   KNOWN_ABSENT_INPUTS, or raises an error naming it.
2. Scaling a list by a factor multiplies each listed column's weighted total
   (over the scaled rows) by that factor and leaves every other column and
   every other row bit-for-bit unchanged.
3. No leaf can be scaled twice: the disjointness check raises exactly when a
   name repeats within or across the scale lists.
4. The growth cap never raises a value, scales exactly the categories growing
   faster than GDP, and brings each one's growth down to GDP's.
5. build_year is deterministic: the same inputs give the same sentinel,
   metadata, weights and written frame.
6. Reusing the accepted probe's vectors gives what a fresh pass over the final
   file gives.
"""

from __future__ import annotations

import itertools
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("hypothesis")

from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from src import pipeline  # noqa: E402
from tests import pipeline_fakes as fakes  # noqa: E402

YEAR = 2060
UNIVERSE = (
    "rental_income",
    "estate_income",
    "s_corp_income",
    "partnership_income",
    *pipeline.KNOWN_ABSENT_INPUTS,
    *pipeline.PRE_2X_NAME_LEAVES,
)


@settings(max_examples=200, deadline=None)
@given(
    names=st.lists(st.sampled_from(UNIVERSE), unique=True, max_size=len(UNIVERSE)),
    present=st.sets(st.sampled_from(UNIVERSE)),
)
def test_every_name_resolves_is_known_absent_or_raises(names, present):
    df = pd.DataFrame({f"{name}__{YEAR}": [1.0] for name in present})
    missing = [
        name
        for name in names
        if name not in present and name not in pipeline.KNOWN_ABSENT_INPUTS
    ]
    if missing:
        with pytest.raises(ValueError) as error:
            pipeline.resolve_frame_columns(df, names, YEAR, list_name="L")
        message = str(error.value)
        listed = message.split("frame column for ", 1)[1].split(". Add each", 1)[0]
        reported = [item.split(" (", 1)[0] for item in listed.split("; ")]
        assert reported == missing
        return
    columns, absent = pipeline.resolve_frame_columns(df, names, YEAR, list_name="L")
    assert columns == [f"{name}__{YEAR}" for name in names if name in present]
    assert set(absent) == {name for name in names if name not in present}
    assert len(columns) == len(set(columns))


finite = st.floats(min_value=-1e7, max_value=1e7, allow_nan=False)


@st.composite
def scaling_cases(draw):
    rows = draw(st.integers(min_value=1, max_value=30))
    width = draw(st.integers(min_value=1, max_value=6))
    data = {
        f"c{j}__{YEAR}": draw(st.lists(finite, min_size=rows, max_size=rows))
        for j in range(width)
    }
    df = pd.DataFrame(data)
    columns = draw(
        st.lists(st.sampled_from(list(df.columns)), unique=True, max_size=width)
    )
    factor = draw(st.floats(min_value=0.05, max_value=20))
    mask = draw(
        st.none() | st.lists(st.booleans(), min_size=rows, max_size=rows).map(np.array)
    )
    weights = np.array(
        draw(
            st.lists(
                st.floats(min_value=0.1, max_value=1e4), min_size=rows, max_size=rows
            )
        )
    )
    return df, columns, factor, mask, weights


@settings(max_examples=300, deadline=None)
@given(case=scaling_cases())
def test_scaling_multiplies_weighted_totals_and_touches_nothing_else(case):
    df, columns, factor, mask, weights = case
    before = df.copy()
    pipeline.scale_frame_columns(df, columns, factor, rows=mask)
    rows = np.ones(len(df), dtype=bool) if mask is None else mask
    for column in df.columns:
        if column not in columns:
            pd.testing.assert_series_equal(df[column], before[column])
            continue
        old = before[column].to_numpy()
        new = df[column].to_numpy()
        np.testing.assert_array_equal(new[~rows], old[~rows])
        np.testing.assert_allclose(
            (new[rows] * weights[rows]).sum(),
            factor * (old[rows] * weights[rows]).sum(),
            rtol=1e-9,
            atol=1e-6 * max(1.0, float(np.abs(old[rows] * weights[rows]).sum())),
        )


@settings(max_examples=300, deadline=None)
@given(
    lists=st.dictionaries(
        st.sampled_from(["A", "B", "C"]),
        st.lists(st.sampled_from(UNIVERSE), max_size=5).map(tuple),
        max_size=3,
    )
)
def test_disjointness_check_raises_exactly_when_a_name_would_scale_twice(lists):
    flat = [name for names in lists.values() for name in names]
    if len(flat) == len(set(flat)):
        pipeline.assert_scale_lists_disjoint(lists)
    else:
        with pytest.raises(ValueError, match="scaled twice"):
            pipeline.assert_scale_lists_disjoint(lists)


CAP_NAMES = [
    name
    for name in pipeline.GROWTH_CAP_VARIABLES
    if name not in pipeline.KNOWN_ABSENT_INPUTS
]


@settings(max_examples=200, deadline=None)
@given(
    rates=st.lists(
        st.floats(min_value=-0.02, max_value=0.12),
        min_size=len(CAP_NAMES),
        max_size=len(CAP_NAMES),
    ),
    gdp_growth=st.floats(min_value=0.5, max_value=20),
    year=st.integers(min_value=2035, max_value=2100),
    values=st.lists(st.floats(min_value=0, max_value=1e7), min_size=3, max_size=3),
)
def test_growth_cap_only_lowers_values_and_lands_on_gdp(
    rates, gdp_growth, year, values
):
    growth = dict(zip((f"calibration.fake.{n}" for n in CAP_NAMES), rates))
    variables = {
        name: fakes.FakeVariable(uprating=f"calibration.fake.{name}")
        for name in pipeline.GROWTH_CAP_VARIABLES
    }
    sim = SimpleNamespace(
        tax_benefit_system=SimpleNamespace(
            variables=variables, parameters=fakes.FakeParameters(1.0, growth)
        )
    )
    df = pd.DataFrame({f"{name}__{year}": values for name in CAP_NAMES + ["age"]})
    before = df.copy()
    audit: dict = {}
    original = pipeline._tr2026_gdp_growth
    pipeline._tr2026_gdp_growth = lambda a, b: gdp_growth
    try:
        factors = pipeline.cap_longrun_income_growth(df, sim, year, audit)
    finally:
        pipeline._tr2026_gdp_growth = original

    for name, rate in zip(CAP_NAMES, rates):
        category = (1 + rate) ** (year - pipeline.GROWTH_CAP_BASE_YEAR)
        column = f"{name}__{year}"
        assert audit[name]["factor"] <= 1.0
        if category > gdp_growth:
            assert factors[name] == pytest.approx(gdp_growth / category)
            assert category * factors[name] == pytest.approx(gdp_growth)
            np.testing.assert_allclose(
                df[column], before[column] * factors[name], rtol=1e-12
            )
        else:
            assert name not in factors
            pd.testing.assert_series_equal(df[column], before[column])
    pd.testing.assert_series_equal(df[f"age__{year}"], before[f"age__{year}"])


def _fake_build(year, seed, output_dir, economic):
    rates = {
        f"calibration.fake.{name}": 0.02
        for name in fakes.frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)
    }
    rates["calibration.fake.qualified_dividend_income"] = 0.09
    engine = fakes.FakeEngine(year, fakes.make_frame(year, seed=seed), rates)
    with pytest.MonkeyPatch.context() as patch:
        fakes.install(patch, engine)
        sentinel = pipeline.build_year(
            year, "fake-base", output_dir, economic_assumption_reform=economic
        )
    sentinel.pop("duration_seconds")
    metadata = json.loads((output_dir / f"{year}.h5.metadata.json").read_text())
    metadata["sentinel"].pop("duration_seconds")
    written = engine.written[str(output_dir / f"{year}.h5")]
    return sentinel, metadata, written


@settings(max_examples=6, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    year=st.sampled_from([2030, 2050]),
    economic=st.sampled_from([None, fakes.FakeEconomicReform]),
)
def test_build_year_is_deterministic_for_any_seed(seed, year, economic):
    with (
        tempfile.TemporaryDirectory() as first,
        tempfile.TemporaryDirectory() as second,
    ):
        a = _fake_build(year, seed, Path(first), economic)
        b = _fake_build(year, seed, Path(second), economic)
    assert a[0] == b[0]
    assert a[1] == b[1]
    pd.testing.assert_frame_equal(a[2], b[2])


@settings(max_examples=6, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=10_000),
    year=st.sampled_from([2030, 2050]),
    economic=st.sampled_from([None, fakes.FakeEconomicReform]),
)
def test_reusing_the_accepted_probe_changes_nothing(seed, year, economic):
    digests = itertools.count()
    with (
        tempfile.TemporaryDirectory() as first,
        tempfile.TemporaryDirectory() as second,
        pytest.MonkeyPatch.context() as patch,
    ):
        reused = _fake_build(year, seed, Path(first), economic)
        patch.setattr(pipeline, "year_file_digest", lambda path: next(digests))
        computed = _fake_build(year, seed, Path(second), economic)
    assert reused[0] == computed[0]
    assert reused[1] == computed[1]
    pd.testing.assert_frame_equal(reused[2], computed[2])


def _search(total_at_gamma, target=63.0):
    """The gamma search on a stand-in whose TOB follows ``total_at_gamma``."""

    def write(probe, year, path, *, reform=None):
        with h5py.File(path, "w") as handle:
            handle.create_dataset(f"dividends/{year}", data=probe.dividends.to_numpy())

    def vectors(path, year, reform):
        with h5py.File(path, "r") as handle:
            gamma = float(handle[f"dividends/{year}"][()][0]) / 10.0
        return {
            "oasdi_tob": np.array([total_at_gamma(gamma)]),
            "hi_tob": np.array([0.0]),
            "gamma": gamma,
            "digest": pipeline.year_file_digest(path),
        }

    with (
        tempfile.TemporaryDirectory() as folder,
        pytest.MonkeyPatch.context() as patch,
    ):
        patch.setattr(pipeline, "write_year_h5", write)
        patch.setattr(pipeline, "_household_vectors", vectors)
        return pipeline._solve_other_income_gamma(
            pd.DataFrame({"dividends": [10.0]}),
            2040,
            Path(folder) / "2040.h5",
            None,
            None,
            ["dividends"],
            np.array([True]),
            np.array([1.0]),
            np.zeros(1, dtype=int),
            {"oasdi_tob": target, "hi_tob": 0.0},
        )


def _assert_the_search_held(gamma, probes, accepted):
    digest, vectors = accepted
    tried = [probe["gamma"] for probe in probes]
    assert len(set(tried)) == len(tried)
    assert len(tried) <= 1 + pipeline.GAMMA_MAX_PROBES
    assert vectors["gamma"] == pytest.approx(gamma)
    assert digest == vectors["digest"]


def _rising_total(root, elasticities, share, target=63.0):
    """TOB that crosses ``target`` at ``root``, from two rising power laws."""

    def total(gamma):
        ratio = gamma / root
        return target * (
            share * ratio ** elasticities[0] + (1 - share) * ratio ** elasticities[1]
        )

    return total


ROOTS = st.floats(min_value=1 / pipeline.GAMMA_MAX, max_value=pipeline.GAMMA_MAX)


@settings(max_examples=200, deadline=None)
@given(
    root=ROOTS,
    elasticities=st.tuples(
        st.floats(min_value=0.05, max_value=3), st.floats(min_value=0.05, max_value=3)
    ),
    share=st.floats(min_value=0, max_value=1),
)
def test_a_reachable_target_ends_within_tolerance(root, elasticities, share):
    total = _rising_total(root, elasticities, share)
    gamma, probes, accepted = _search(total)
    _assert_the_search_held(gamma, probes, accepted)
    assert abs(total(gamma) / 63.0 - 1) <= pipeline.GAMMA_TOLERANCE


@settings(max_examples=100, deadline=None)
@given(root=ROOTS, elasticity=st.floats(min_value=0.05, max_value=8))
def test_one_power_law_ends_within_tolerance(root, elasticity):
    total = _rising_total(root, (elasticity, elasticity), 1.0)
    gamma, probes, accepted = _search(total)
    _assert_the_search_held(gamma, probes, accepted)
    assert abs(total(gamma) / 63.0 - 1) <= pipeline.GAMMA_TOLERANCE


def test_the_search_can_need_every_probe_it_has():
    total = _rising_total(0.8, (0.05, 8.0), 0.5)
    gamma, probes, accepted = _search(total)
    _assert_the_search_held(gamma, probes, accepted)
    assert len(probes) == 1 + pipeline.GAMMA_MAX_PROBES
    assert abs(total(gamma) / 63.0 - 1) <= pipeline.GAMMA_TOLERANCE


@settings(max_examples=50, deadline=None)
@given(
    gap=st.floats(min_value=1.03, max_value=3),
    elasticity=st.floats(min_value=0.05, max_value=3),
)
def test_a_shortfall_at_the_bound_settles_the_year(gap, elasticity):
    root = pipeline.GAMMA_MAX * gap ** (1 / elasticity)
    total = _rising_total(root, (elasticity, elasticity), 1.0)
    gamma, probes, accepted = _search(total)
    _assert_the_search_held(gamma, probes, accepted)
    assert gamma == pipeline.GAMMA_MAX
    assert len(probes) == 1


@settings(max_examples=50, deadline=None)
@given(
    gap=st.floats(min_value=1.03, max_value=3),
    elasticity=st.floats(min_value=0.05, max_value=3),
)
def test_a_surplus_at_the_lower_bound_stops_there(gap, elasticity):
    root = 1 / pipeline.GAMMA_MAX / gap ** (1 / elasticity)
    total = _rising_total(root, (elasticity, elasticity), 1.0)
    gamma, probes, accepted = _search(total)
    _assert_the_search_held(gamma, probes, accepted)
    assert gamma == 1 / pipeline.GAMMA_MAX


def test_a_year_above_target_at_the_bound_reaches_its_targets():
    with tempfile.TemporaryDirectory() as folder:
        sentinel, _, _ = _fake_build(2030, 2801, Path(folder), None)
    assert 1 < sentinel["gamma_other_income_scale"] < pipeline.GAMMA_MAX
