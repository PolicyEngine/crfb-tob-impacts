"""Properties of mapping a variable from its native entity to a manifest entity."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("hypothesis")
pytest.importorskip("policyengine_core")
from hypothesis import given, settings
from hypothesis import strategies as st
from policyengine_core.entities import Entity, GroupEntity
from policyengine_core.populations import GroupPopulation, Population
from policyengine_core.simulations import Simulation

from src.reform_full_h5_worker import _values_on_entity

AMOUNTS = st.floats(-1e6, 1e6, allow_nan=False, width=32)
# Ids from here on collapse together if anything casts them to float32.
FIRST_ID = 2**24 + 1
GROUPS = ("tax_unit", "spm_unit", "household")
PAIRS = (
    ("person", "tax_unit"),
    ("person", "household"),
    ("tax_unit", "household"),
    ("tax_unit", "spm_unit"),
    ("spm_unit", "tax_unit"),
    ("tax_unit", "person"),
    ("household", "person"),
    ("tax_unit", "tax_unit"),
    ("person", "person"),
)
# Each kind of column a variable can hold, with its awkward values.
COLUMNS = (
    (
        np.float32,
        st.one_of(st.just(float("nan")), AMOUNTS, st.just(float(2**24))),
    ),
    (np.float64, st.floats(-1e12, 1e12, allow_nan=False)),
    (np.int64, st.integers(2**24, 2**40)),
    (np.int32, st.integers(-(2**31), 2**31 - 1)),
    (np.bool_, st.booleans()),
)


@st.composite
def populations(draw):
    """People in tax units nested in households, and in SPM units that cross
    both, with ids in shuffled order."""
    sizes = draw(st.lists(st.integers(1, 3), min_size=1, max_size=6))
    households, tax_units = [], []
    next_unit = 0
    for household, size in enumerate(sizes):
        for _ in range(draw(st.integers(1, 2))):
            households.extend([household] * size)
            tax_units.extend([next_unit] * size)
            next_unit += 1
    order = np.array(draw(st.permutations(range(len(households)))))
    relabel = np.array(draw(st.permutations(range(FIRST_ID, FIRST_ID + next_unit))))
    spm_units = draw(
        st.lists(
            st.integers(FIRST_ID, FIRST_ID + 3),
            min_size=len(households),
            max_size=len(households),
        )
    )
    people = pd.DataFrame(
        {
            "person_id": FIRST_ID + np.arange(len(households)),
            "person_household_id": FIRST_ID + np.array(households)[order],
            "person_tax_unit_id": relabel[np.array(tax_units)[order]],
            "person_spm_unit_id": spm_units,
        }
    )
    return people


def core_map_result(values, native, target, people, tables):
    """Core's own mapping, on Core's own populations."""
    person = Population(Entity("person", "people", "Person", ""))
    person.count = len(people)
    populations = {"person": person}
    for entity, ids in tables.items():
        group = GroupPopulation(
            GroupEntity(entity, f"{entity}s", entity, "", [dict(key="member")]), person
        )
        group.count = len(ids)
        group.members_entity_id = pd.Index(ids).get_indexer(
            people[f"person_{entity}_id"]
        )
        populations[entity] = group
    simulation = SimpleNamespace(
        populations=populations,
        tax_benefit_system=SimpleNamespace(
            group_entity_keys=list(tables), person_entity=person.entity
        ),
    )
    simulation.map_result = lambda *args, **kwargs: Simulation.map_result(
        simulation, *args, **kwargs
    )
    return Simulation.map_result(simulation, values, native, target)


@settings(max_examples=300, deadline=None)
@given(populations(), st.sampled_from(PAIRS), st.data())
def test_mapping_agrees_with_core(people, pair, data):
    native, target = pair
    tables = {
        entity: np.array(data.draw(st.permutations(people[column].unique().tolist())))
        for entity, column in ((g, f"person_{g}_id") for g in GROUPS)
    }
    tables_with_people = {**tables, "person": people.person_id.to_numpy()}
    size = len(tables_with_people[native])
    dtype, amounts = data.draw(st.sampled_from(COLUMNS))
    values = np.array(
        data.draw(st.lists(amounts, min_size=size, max_size=size)), dtype=dtype
    )
    mapped = _values_on_entity(
        values,
        tables_with_people[native],
        native=native,
        target=target,
        people=people,
        target_ids=tables_with_people[target],
    )
    expected = core_map_result(values, native, target, people, tables)
    assert mapped.dtype == expected.dtype
    np.testing.assert_array_equal(mapped, expected)


@pytest.mark.parametrize(
    "values, expected",
    [
        ([16777216, 1, 0], [16777217, 0]),
        ([np.nan, 1, 0], [np.nan, 0]),
        ([np.nan, np.nan, np.nan], [np.nan, np.nan]),
    ],
)
def test_group_totals_keep_double_precision_and_nans(values, expected):
    people = pd.DataFrame({"person_id": [1, 2, 3], "person_tax_unit_id": [20, 20, 30]})
    mapped = _values_on_entity(
        np.array(values, dtype=np.float32),
        people.person_id.to_numpy(),
        native="person",
        target="tax_unit",
        people=people,
        target_ids=np.array([20, 30]),
    )
    np.testing.assert_array_equal(mapped, expected)


def test_a_group_without_people_holds_zero():
    people = pd.DataFrame({"person_id": [1, 2], "person_tax_unit_id": [20, 20]})
    mapped = _values_on_entity(
        np.array([1.0, 2.0]),
        people.person_id.to_numpy(),
        native="person",
        target="tax_unit",
        people=people,
        target_ids=np.array([20, 30]),
    )
    np.testing.assert_array_equal(mapped, [3.0, 0.0])


@pytest.mark.parametrize(
    "native, target",
    [("person", "tax_unit"), ("tax_unit", "person")],
)
def test_a_person_outside_every_group_stops_the_mapping(native, target):
    people = pd.DataFrame({"person_id": [1, 2], "person_tax_unit_id": [20, 99]})
    groups = np.array([20])
    with pytest.raises(ValueError, match="missing from its table"):
        _values_on_entity(
            np.array([1.0, 2.0]) if native == "person" else np.array([1.0]),
            people.person_id.to_numpy() if native == "person" else groups,
            native=native,
            target=target,
            people=people,
            target_ids=groups if target == "tax_unit" else people.person_id.to_numpy(),
        )


@settings(max_examples=200, deadline=None)
@given(populations(), st.data())
def test_people_sum_into_groups_and_totals_hold(people, data):
    values = np.array(
        data.draw(st.lists(AMOUNTS, min_size=len(people), max_size=len(people))),
        dtype=float,
    )
    ids = people.person_tax_unit_id.unique()[::-1]
    mapped = _values_on_entity(
        values,
        people.person_id.to_numpy(),
        native="person",
        target="tax_unit",
        people=people,
        target_ids=ids,
    )
    assert mapped.sum() == pytest.approx(values.sum(), abs=1e-3)
    for position, unit in enumerate(ids):
        members = people.person_tax_unit_id.to_numpy() == unit
        assert mapped[position] == pytest.approx(values[members].sum(), abs=1e-3)


@settings(max_examples=200, deadline=None)
@given(populations(), st.data())
def test_groups_sum_into_the_households_that_hold_them(people, data):
    ids = people.person_tax_unit_id.unique()
    values = np.array(
        data.draw(st.lists(AMOUNTS, min_size=len(ids), max_size=len(ids))), dtype=float
    )
    households = people.person_household_id.unique()[::-1]
    mapped = _values_on_entity(
        values,
        ids,
        native="tax_unit",
        target="household",
        people=people,
        target_ids=households,
    )
    assert mapped.sum() == pytest.approx(values.sum(), abs=1e-3)


@settings(max_examples=200, deadline=None)
@given(populations(), st.data())
def test_people_see_their_groups_value(people, data):
    ids = people.person_tax_unit_id.unique()
    values = np.array(
        data.draw(st.lists(AMOUNTS, min_size=len(ids), max_size=len(ids))), dtype=float
    )
    mapped = _values_on_entity(
        values,
        ids,
        native="tax_unit",
        target="person",
        people=people,
        target_ids=people.person_id.to_numpy(),
    )
    lookup = dict(zip(ids, values))
    assert mapped.tolist() == [lookup[unit] for unit in people.person_tax_unit_id]
