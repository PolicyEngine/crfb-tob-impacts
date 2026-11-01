"""A deterministic stand-in for the engine, for driving build_year in tests.

The fake engine computes every quantity build_year reads from a person-level
year frame with simple closed-form rules, and records the reform each
simulation was built with. Targets are derived from the same frame so that
every calibration stage is feasible.
"""

from __future__ import annotations

import types
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pandas as pd
from policyengine_core.reforms import Reform

from src import pipeline

CAP = 150_000.0
ECONOMIC_CAP = 180_000.0
SS_THRESHOLD = 25_000.0
PRE_SCALED_TOB_TARGET_FACTOR = 1.03
# Keep enough recipients below the 85% inclusion ceiling for the higher TOB
# target to remain feasible while calibration holds total benefits fixed.
OTHER_INCOME_SAMPLE_FACTOR = 0.2

EARNINGS = (
    "employment_income_before_lsr",
    "self_employment_income_before_lsr",
    "sstb_self_employment_income_before_lsr",
    "partnership_self_employment_net_earnings",
    "farm_operations_income",
)


class FakeEconomicReform(Reform):
    """Marker reform: raises the contribution cap.

    A Reform subclass, so the scorers' loader accepts the module:attribute
    path a build records for it. The fakes never apply it.
    """


class FakeTaxReform:
    """Marker reform: leaves the cap alone (like the tax assumption)."""


class FakeCapMovingTaxReform:
    """Marker reform: moves the cap, which build_year must reject."""


def flatten_reform(reform) -> tuple:
    if reform is None:
        return ()
    if isinstance(reform, tuple):
        return tuple(item for part in reform for item in flatten_reform(part))
    return (reform,)


@dataclass
class FakeVariable:
    uprating: str | None = None
    formulas: dict = field(default_factory=dict)
    adds: list | None = None
    possible_values: object = None


class FakeParameters:
    """Callable parameter tree with uprating series for the growth cap."""

    def __init__(
        self,
        cap: float,
        growth_rates: dict[str, float],
        metadata: dict[str, dict] | None = None,
    ):
        self.cap = cap
        self.growth_rates = growth_rates
        self.metadata = metadata or {}

    def __call__(self, instant: str):
        return SimpleNamespace(
            gov=SimpleNamespace(
                irs=SimpleNamespace(
                    payroll=SimpleNamespace(
                        social_security=SimpleNamespace(cap=self.cap)
                    )
                )
            )
        )

    def get_child(self, path: str):
        if path == "gov.irs.gross_income.sources":
            return lambda instant: [
                name
                for names in pipeline.SCALE_LISTS.values()
                for name in names
            ]
        return FakeSeries(self, path)


class FakeSeries:
    """A parameter growing at a constant rate from 2000, with metadata."""

    def __init__(self, parameters: FakeParameters, path: str):
        self.parameters = parameters
        self.path = path
        self.metadata = parameters.metadata.get(path, {})

    def __call__(self, instant: str) -> float:
        rate = self.parameters.growth_rates[self.path]
        return (1 + rate) ** (int(instant[:4]) - 2000)


def frame_variable_names() -> list[str]:
    names = set(pipeline.PERSON_LEVEL_IDENTITY_INPUTS) | {"age", "household_weight"}
    for names_in_list in pipeline.SCALE_LISTS.values():
        names |= set(names_in_list)
    names |= set(pipeline.GROWTH_CAP_VARIABLES)
    for components in pipeline.INCOME_GUARD_GROUPS.values():
        names |= set(components)
    names -= set(pipeline.KNOWN_ABSENT_INPUTS)
    # Guard aggregates the engine computes rather than stores.
    names -= {"partnership_s_corp_income"}
    return sorted(names)


def make_frame(year: int, *, seed: int = 0, households: int = 120) -> pd.DataFrame:
    """A person-level year frame covering every age bucket."""
    rng = np.random.default_rng(seed)
    sizes = rng.integers(1, 4, size=households)
    person_household = np.repeat(np.arange(1, households + 1) * 10, sizes)
    n = len(person_household)
    ages = np.arange(n) % 90  # every five-year bucket, including 85+
    weights_by_household = rng.uniform(500, 1_500, size=households)
    columns: dict[str, np.ndarray] = {}
    for name in frame_variable_names():
        columns[name] = np.where(
            rng.uniform(size=n) < 0.4, rng.lognormal(9, 1, size=n), 0.0
        )
        if name in pipeline.OTHER_INCOME_SCALE_CANDIDATES:
            columns[name] *= OTHER_INCOME_SAMPLE_FACTOR
    columns["person_id"] = np.arange(n) + 1
    columns["household_id"] = person_household
    columns["person_household_id"] = person_household
    for entity in ("family", "tax_unit", "spm_unit", "marital_unit"):
        columns[f"{entity}_id"] = person_household
        columns[f"person_{entity}_id"] = person_household
    columns["age"] = ages
    elderly = ages >= 62
    for name in pipeline.SOCIAL_SECURITY_SCALE_CANDIDATES:
        columns[name] = np.where(elderly, rng.uniform(5_000, 30_000, size=n), 0.0) / 4
    columns["employment_income_before_lsr"] = np.where(
        (ages >= 18) & (ages < 70), rng.lognormal(10.5, 0.8, size=n), 0.0
    )
    columns["household_weight"] = np.repeat(weights_by_household, sizes)
    return pd.DataFrame({f"{name}__{year}": values for name, values in columns.items()})


def _other_income(frame: pd.DataFrame, year: int) -> np.ndarray:
    columns = [
        f"{name}__{year}"
        for name in pipeline.OTHER_INCOME_SCALE_CANDIDATES
        if f"{name}__{year}" in frame.columns
    ]
    return frame[columns].sum(axis=1).to_numpy()


def _social_security(frame: pd.DataFrame, year: int) -> np.ndarray:
    columns = [f"{name}__{year}" for name in pipeline.SOCIAL_SECURITY_SCALE_CANDIDATES]
    return frame[columns].sum(axis=1).to_numpy()


def _wages(frame: pd.DataFrame, year: int) -> np.ndarray:
    return frame[f"employment_income_before_lsr__{year}"].to_numpy()


def _self_employment(frame: pd.DataFrame, year: int) -> np.ndarray:
    return frame[[f"{name}__{year}" for name in EARNINGS[1:]]].sum(axis=1).to_numpy()


def person_tob(frame: pd.DataFrame, year: int) -> tuple[np.ndarray, np.ndarray]:
    ss = _social_security(frame, year)
    provisional = _other_income(frame, year) + 0.5 * ss
    included = np.minimum(0.85 * ss, 0.5 * np.maximum(provisional - SS_THRESHOLD, 0))
    return 0.12 * included, 0.05 * included


class FakeSimulation:
    def __init__(self, frame: pd.DataFrame, year: int, reform, growth_rates):
        self.frame = frame.reset_index(drop=True)
        self.year = year
        self.reform = reform
        reforms = flatten_reform(reform)
        cap = ECONOMIC_CAP if FakeEconomicReform in reforms else CAP
        if FakeCapMovingTaxReform in reforms:
            cap += 1_000.0
        self.cap = cap
        names = frame_variable_names() + list(pipeline.KNOWN_ABSENT_INPUTS)
        variables = {
            name: FakeVariable(uprating=f"calibration.fake.{name}") for name in names
        }
        variables["partnership_s_corp_income"] = FakeVariable(
            adds=["partnership_income", "s_corp_income"]
        )
        self.tax_benefit_system = SimpleNamespace(
            variables=variables,
            parameters=FakeParameters(cap, growth_rates),
        )

    def _column(self, name: str) -> np.ndarray:
        return self.frame[f"{name}__{self.year}"].to_numpy(dtype=float)

    def _person_values(self, variable: str) -> np.ndarray:
        frame, year = self.frame, self.year
        wages = _wages(frame, year)
        se = _self_employment(frame, year)
        taxable_wages = np.minimum(wages, self.cap)
        oasdi, hi = person_tob(frame, year)
        values = {
            "payroll_tax_gross_wages": lambda: wages,
            "taxable_self_employment_income": lambda: se,
            "social_security": lambda: _social_security(frame, year),
            "taxable_earnings_for_social_security": lambda: taxable_wages,
            "social_security_taxable_self_employment_income": lambda: np.minimum(
                se, np.maximum(self.cap - taxable_wages, 0)
            ),
            "tob_revenue_oasdi": lambda: oasdi,
            "tob_revenue_medicare_hi": lambda: hi,
            "adjusted_gross_income": lambda: (
                wages
                + se
                + _other_income(frame, year)
                + 0.5 * _social_security(frame, year)
            ),
            "partnership_s_corp_income": lambda: (
                self._column("partnership_income") + self._column("s_corp_income")
            ),
        }
        if variable == "income_tax":
            return 0.15 * self._person_values("adjusted_gross_income")
        if variable in values:
            return np.asarray(values[variable](), dtype=float)
        return self._column(variable)

    def calculate(self, variable, period=None, map_to=None):
        assert int(period) == self.year
        household = self.frame[f"person_household_id__{self.year}"].to_numpy()
        ids = np.unique(household)
        if variable == "household_id":
            weights = (
                pd.Series(
                    self.frame[f"household_weight__{self.year}"].to_numpy(),
                    index=household,
                )
                .groupby(level=0)
                .first()
                .reindex(ids)
                .to_numpy()
            )
            return SimpleNamespace(values=ids, weights=weights)
        person = self._person_values(variable)
        if map_to == "household":
            totals = pd.Series(person).groupby(household).sum().reindex(ids)
            return SimpleNamespace(values=totals.to_numpy())
        return SimpleNamespace(values=person)


@dataclass
class FakeEngine:
    """Installs the fake engine and records every simulation's reform."""

    year: int
    frame: pd.DataFrame
    growth_rates: dict[str, float]
    constructed: list[tuple[str, object]] = field(default_factory=list)
    written: dict[str, pd.DataFrame] = field(default_factory=dict)

    def module(self) -> types.ModuleType:
        module = types.ModuleType("src.engine")

        def base_microsimulation(reform=None, **kwargs):
            self.constructed.append(("stage_a", reform))
            return FakeSimulation(self.frame, self.year, reform, self.growth_rates)

        def dataset_microsimulation(dataset, reform=None, **kwargs):
            self.constructed.append(("dataset", reform))
            frame = self.written.get(str(dataset), self.frame)
            return FakeSimulation(frame, self.year, reform, self.growth_rates)

        module.base_microsimulation = base_microsimulation
        module.dataset_microsimulation = dataset_microsimulation
        module.frame_microsimulation = lambda dataset, reform=None: (
            base_microsimulation(reform=reform)
        )

        def household_vectors(path, year, variables, reform=None):
            self.constructed.append(("vectors", reform))
            sim = FakeSimulation(
                self.written[str(path)], year, reform, self.growth_rates
            )
            return {
                name: sim.calculate(name, period=year, map_to="household").values
                for name in variables
            }

        module.household_vectors = household_vectors
        module.stage_a_microsimulation = (
            lambda base_dataset, reform=None: base_microsimulation(reform=reform)
        )
        return module

    def write_year_h5(self, df, year, output_path, *, reform=None):
        self.constructed.append(("writer", reform))
        self.written[str(output_path)] = df.copy()
        household = df[f"person_household_id__{year}"].to_numpy()
        weights = (
            pd.Series(df[f"household_weight__{year}"].to_numpy(), index=household)
            .groupby(level=0)
            .first()
            .to_numpy()
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(output_path, "w") as handle:
            handle.create_dataset(f"household_weight/{year}", data=weights)


def install(monkeypatch, engine: FakeEngine, *, tax_reform=None) -> None:
    """Point build_year at the fake engine and frame-consistent targets."""
    import sys

    year, frame = engine.year, engine.frame
    monkeypatch.setitem(sys.modules, "src.engine", engine.module())
    monkeypatch.setattr(
        pipeline, "materialize_year_frame", lambda sim, y: sim.frame.copy()
    )
    monkeypatch.setattr(pipeline, "write_year_h5", engine.write_year_h5)
    monkeypatch.setattr(pipeline, "_tax_assumption_reform", lambda y: tax_reform)
    monkeypatch.setattr(
        pipeline,
        "evaluate_publication_gates",
        lambda audit, contributors: {"passed": True, "failures": []},
    )

    person_weights = frame[f"household_weight__{year}"].to_numpy()
    base = FakeSimulation(frame, year, None, engine.growth_rates)
    payroll = float(
        (
            (
                base._person_values("taxable_earnings_for_social_security")
                + base._person_values("social_security_taxable_self_employment_income")
            )
            * person_weights
        ).sum()
    )
    ss_total = float((_social_security(frame, year) * person_weights).sum())
    oasdi, hi = person_tob(frame, year)
    tob = {
        "oasdi_tob": float((oasdi * person_weights).sum())
        * PRE_SCALED_TOB_TARGET_FACTOR,
        "hi_tob": float((hi * person_weights).sum()) * PRE_SCALED_TOB_TARGET_FACTOR,
    }
    ages = np.minimum(frame[f"age__{year}"].to_numpy(dtype=int), 85)
    totals = np.bincount(ages, weights=person_weights, minlength=86).astype(float)
    monkeypatch.setattr(
        pipeline,
        "load_economic_targets",
        lambda y: {"ss_total": ss_total, "payroll_total": payroll},
    )
    monkeypatch.setattr(pipeline, "load_tob_targets", lambda y: dict(tob))
    monkeypatch.setattr(
        pipeline, "load_population_age_targets", lambda y: (np.arange(86), totals)
    )
