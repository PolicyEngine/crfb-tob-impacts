"""Properties of mapping a variable from its native entity to a manifest entity."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from src.reform_full_h5_worker import _values_on_entity

AMOUNTS = st.floats(-1e6, 1e6, allow_nan=False, width=32)


@st.composite
def populations(draw):
    """People in tax units nested in households, with ids in shuffled order."""
    sizes = draw(st.lists(st.integers(1, 3), min_size=1, max_size=6))
    households, tax_units = [], []
    next_unit = 0
    for household, size in enumerate(sizes):
        for _ in range(draw(st.integers(1, 2))):
            households.extend([household] * size)
            tax_units.extend([next_unit] * size)
            next_unit += 1
    order = np.array(draw(st.permutations(range(len(households)))))
    relabel = np.array(draw(st.permutations(range(1000, 1000 + next_unit))))
    people = pd.DataFrame(
        {
            "person_id": np.arange(len(households)),
            "person_household_id": np.array(households)[order],
            "person_tax_unit_id": relabel[np.array(tax_units)[order]],
        }
    )
    return people


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
