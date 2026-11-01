"""Stage A's dataset extension uses the same economy as its growth cap."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest


def load_engine(monkeypatch):
    # Keep bundle discovery out of isolated tests; exercise the actual loader.
    managed = types.ModuleType("policyengine.tax_benefit_models.us")
    managed.managed_microsimulation = lambda **kwargs: None
    managed.us_latest = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, managed.__name__, managed)
    spec = importlib.util.spec_from_file_location(
        "stage_a_engine_test", Path(__file__).parents[1] / "src/engine.py"
    )
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def entity_file(path):
    ids = np.array([10, 20, 30])
    people = pd.DataFrame(
        {"person_id": ids, "age": [40, 65, 80], "is_female": [False, True, False]}
    )
    for entity in ("household", "tax_unit", "spm_unit", "family", "marital_unit"):
        people[f"person_{entity}_id"] = ids
    with pd.HDFStore(path, "w") as store:
        store["person"] = people
        for entity in ("household", "tax_unit", "spm_unit", "family", "marital_unit"):
            table = {f"{entity}_id": ids}
            if entity == "household":
                table["household_weight"] = [1.0, 2.0, 3.0]
            store[entity] = pd.DataFrame(table)
        store["_time_period"] = pd.Series([2024])
    return path


def test_stage_a_rejects_multiyear_base_naming_file(monkeypatch, tmp_path):
    engine = load_engine(monkeypatch)
    monkeypatch.setattr(engine, "_require_certified_runtime", lambda: None)
    path = tmp_path / "already_aged.h5"
    with pd.HDFStore(path, "w") as store:
        store["person/2024"] = pd.DataFrame({"person_id": [1]})
        store["person/2050"] = pd.DataFrame({"person_id": [1]})
    with pytest.raises(ValueError, match="already_aged.h5"):
        engine.stage_a_microsimulation(path, 2050, reform=object())


def test_stage_a_preserves_runtime_gate(monkeypatch):
    engine = load_engine(monkeypatch)
    monkeypatch.setattr(engine, "certified_model_version", lambda: "required")
    monkeypatch.setattr(engine._metadata, "version", lambda name: "different")
    with pytest.raises(RuntimeError, match="requires required"):
        engine.stage_a_microsimulation(None, 2050, reform=object())


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("entity_level", [False, True])
def test_no_reform_limits_only_entity_level_sources(
    monkeypatch, tmp_path, local, entity_level
):
    engine = load_engine(monkeypatch)
    gate = []
    monkeypatch.setattr(engine, "_require_certified_runtime", lambda: gate.append(True))
    path = tmp_path / "base.h5"
    if entity_level:
        entity_file(path)
    else:
        with h5py.File(path, "w") as store:
            store.create_dataset("age/2024", data=[40])
    monkeypatch.setattr(
        engine, "_certified_base_source", lambda: ("hf://pinned@revision", str(path))
    )
    country = types.ModuleType("policyengine_us")
    calls = []

    def construct(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace()

    country.Microsimulation = construct
    monkeypatch.setitem(sys.modules, "policyengine_us", country)
    model = types.ModuleType("policyengine.tax_benefit_models.us.model")
    model._managed_release_bundle = lambda uri, source: {"uri": uri, "source": source}
    monkeypatch.setitem(sys.modules, model.__name__, model)
    sim = engine.stage_a_microsimulation(path if local else None, 2030)
    assert gate == [True]
    assert calls == [
        {"dataset": str(path), **({"dataset_end_year": 2030} if entity_level else {})}
    ]
    if not local:
        assert sim.policyengine_bundle == {
            "uri": "hf://pinned@revision",
            "source": str(path),
        }


def test_certified_source_uses_managed_resolution(monkeypatch):
    engine = load_engine(monkeypatch)
    calls = []
    manifest = types.ModuleType("policyengine.provenance.manifest")
    manifest.resolve_managed_dataset_reference = lambda country: (
        calls.append(("pin", country)) or "hf://data@revision"
    )
    manifest.resolve_local_managed_dataset_source = lambda country, uri: (
        calls.append(("mirror", country, uri)) or "/mirror.h5"
    )
    sources = types.ModuleType("policyengine.provenance.dataset_sources")
    sources.materialize_dataset_source = lambda source: (
        calls.append(("materialize", source)) or source
    )
    monkeypatch.setitem(sys.modules, manifest.__name__, manifest)
    monkeypatch.setitem(sys.modules, sources.__name__, sources)
    assert engine._certified_base_source() == ("hf://data@revision", "/mirror.h5")
    assert calls == [
        ("pin", "us"),
        ("mirror", "us", "hf://data@revision"),
        ("materialize", "/mirror.h5"),
    ]


@pytest.mark.parametrize("local", [False, True])
@pytest.mark.parametrize("per_capita_built", [False, True])
def test_reform_reaches_extension_and_simulation(
    monkeypatch, tmp_path, local, per_capita_built
):
    engine = load_engine(monkeypatch)
    monkeypatch.setattr(engine, "_require_certified_runtime", lambda: None)
    path = entity_file(tmp_path / "base.h5")
    monkeypatch.setattr(
        engine, "_certified_base_source", lambda: ("hf://pinned@revision", str(path))
    )
    reform = object()
    system = types.SimpleNamespace(_per_capita_uprating_built=per_capita_built)
    single, multi = object(), object()
    calls = []
    country = types.ModuleType("policyengine_us")
    country.Microsimulation = lambda **kwargs: (
        calls.append(("sim", kwargs)) or types.SimpleNamespace()
    )
    schema = types.ModuleType("policyengine_us.data.dataset_schema")
    schema.USSingleYearDataset = lambda **kwargs: (
        calls.append(("single", kwargs)) or single
    )
    economic = types.ModuleType("policyengine_us.data.economic_assumptions")
    economic.extend_single_year_dataset = lambda dataset, **kwargs: (
        calls.append(("extend", dataset, kwargs)) or multi
    )
    systems = types.ModuleType("policyengine_us.system")
    systems.CountryTaxBenefitSystem = lambda **kwargs: (
        calls.append(("system", kwargs)) or system
    )
    model = types.ModuleType("policyengine.tax_benefit_models.us.model")
    model._managed_release_bundle = lambda uri, source: (uri, source)
    for module in (country, schema, economic, systems, model):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    if not per_capita_built:
        with pytest.raises(RuntimeError, match="add_per_capita_uprating"):
            engine.stage_a_microsimulation(path if local else None, 2050, reform=reform)
        assert calls == [("system", {"reform": reform})]
    else:
        sim = engine.stage_a_microsimulation(
            path if local else None, 2050, reform=reform
        )
        assert calls == [
            ("system", {"reform": reform}),
            ("single", {"file_path": str(path)}),
            ("extend", single, {"end_year": 2050, "system": system}),
            ("sim", {"dataset": multi, "reform": reform}),
        ]
        if not local:
            assert sim.policyengine_bundle == ("hf://pinned@revision", str(path))
