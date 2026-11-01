"""Fakes for driving the scorers on datasets that record an economic assumption.

The scorers read a dataset's metadata, load the reforms it records and hand a
composed reform to the engine. These fakes stand in for the engine with rules
that depend on the order reforms apply in:

- the economic assumption reform sets the contribution cap and a wage index;
- the tax assumption reform indexes the benefit-taxation threshold by the wage
  index in force when it applies, so it must follow the economic assumption;
- the policy reform scales whatever cap it finds.

A scorer that drops any of the three reforms, or swaps two of them, reports
different totals whenever both the economic and the tax assumption apply.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

from src import tax_assumption_loader as loader
from tests import pipeline_fakes as fakes
from tests.pipeline_fakes import FakeEconomicReform, FakeTaxReform, flatten_reform

ECONOMIC_SPEC = "tests.pipeline_fakes:FakeEconomicReform"
TAX_NAME = loader.TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION
POLICY_CAP_SCALE = 1.1
ECONOMIC_WAGE_INDEX = 1.3
LABOR_RESPONSE_PER_CAP_DOLLAR = 0.01


class FakePolicyReform:
    """Marker policy reform: scales the cap in force when it applies."""


class FakeRateReform:
    """Marker solvency payroll-rate reform."""


def parameters_after(reform) -> tuple[float, float]:
    """The cap and the benefit-taxation threshold once each reform has
    applied, left to right."""
    cap = fakes.CAP
    wage_index = 1.0
    threshold = fakes.SS_THRESHOLD
    for part in flatten_reform(reform):
        if part is FakeEconomicReform:
            cap = fakes.ECONOMIC_CAP
            wage_index = ECONOMIC_WAGE_INDEX
        elif part is FakeTaxReform:
            threshold = fakes.SS_THRESHOLD * wage_index
        elif part is FakePolicyReform:
            cap *= POLICY_CAP_SCALE
    return cap, threshold


def cap_after(reform) -> float:
    return parameters_after(reform)[0]


def person_tob(frame, year: int, threshold: float):
    """pipeline_fakes.person_tob with the threshold as a parameter."""
    ss = fakes._social_security(frame, year)
    provisional = fakes._other_income(frame, year) + 0.5 * ss
    included = np.minimum(0.85 * ss, 0.5 * np.maximum(provisional - threshold, 0))
    return 0.12 * included, 0.05 * included


class SequencedSimulation(fakes.FakeSimulation):
    """The pipeline fake with the order-sensitive rules.

    Like a reform simulation in the engine, it has a baseline branch built under
    no reform unless a scorer installs one.
    """

    def __init__(self, frame, year, reform, growth_rates=None):
        super().__init__(frame, year, reform, growth_rates or {})
        self.cap, self.threshold = parameters_after(reform)
        self.baseline = (
            SimpleNamespace(reform=None, _bind_to_tax_benefit_system=lambda: None)
            if reform is not None
            else None
        )

    @staticmethod
    def default_tax_benefit_system(reform=None):
        return SimpleNamespace(reform=reform)

    def _person_values(self, variable: str):
        if variable in ("tob_revenue_oasdi", "tob_revenue_medicare_hi"):
            oasdi, hi = person_tob(self.frame, self.year, self.threshold)
            return oasdi if variable == "tob_revenue_oasdi" else hi
        return super()._person_values(variable)


def fake_aggregate(frame, year: int, reform, *, baseline_reform=None):
    """Totals a simulation under ``reform`` reports on ``frame``.

    ``baseline_reform`` stands for the reform on a behavioral simulation's
    baseline branch: earnings respond to the cap the policy moves relative to
    that branch, as a labor supply response does.
    """
    # Imported here: src.year_runner needs policyengine.py, which the
    # worker and balanced-fix tests do not.
    from src.year_runner import ScenarioAggregate

    sim = SequencedSimulation(frame, year, reform)
    weights = frame[f"household_weight__{year}"].to_numpy(dtype=float)

    def total(variable: str) -> float:
        return float((sim._person_values(variable) * weights).sum())

    payroll = total("taxable_earnings_for_social_security") + total(
        "social_security_taxable_self_employment_income"
    )
    response = 0.0
    if baseline_reform is not None:
        response = LABOR_RESPONSE_PER_CAP_DOLLAR * (
            cap_after(reform) - cap_after(baseline_reform)
        )
    oasdi = total("tob_revenue_oasdi")
    hi = total("tob_revenue_medicare_hi")
    return ScenarioAggregate(
        revenue=total("income_tax") + response * float(weights.sum()),
        tob_medicare_hi=hi,
        tob_oasdi=oasdi,
        tob_total=oasdi + hi,
        social_security=total("social_security"),
        taxable_payroll=payroll,
        employer_ss_tax_revenue=0.062 * payroll,
        employer_medicare_tax_revenue=0.0145 * total("payroll_tax_gross_wages"),
    )


def economic_record(*, module_sha256: str | None = None) -> dict:
    """The record build_year writes for FakeEconomicReform."""
    provenance = loader.economic_assumption_provenance(ECONOMIC_SPEC)
    if module_sha256 is not None:
        provenance["module_sha256"] = module_sha256
    return {"active": True, "applies_before": "tax_assumption", **provenance}


INACTIVE_RECORD = {"active": False, "applies_before": "tax_assumption", "reform": None}


def dataset_metadata(year: int, *, economic: dict | None) -> dict:
    return {
        "year": year,
        "economic_assumption": economic if economic is not None else INACTIVE_RECORD,
        "tax_assumption": {
            "name": TAX_NAME,
            "start_year": 2035,
            "end_year": 2100,
            "active": year >= 2035,
        },
    }


def write_dataset(directory: Path, year: int, *, economic: dict | None) -> Path:
    """A placeholder year file with its metadata sidecar."""
    directory.mkdir(parents=True, exist_ok=True)
    dataset = directory / f"{year}.h5"
    dataset.write_bytes(b"placeholder year dataset")
    Path(f"{dataset}.metadata.json").write_text(
        json.dumps(dataset_metadata(year, economic=economic)), encoding="utf-8"
    )
    return dataset


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def engine_module(frame, year: int, constructed: list) -> ModuleType:
    """A stand-in for src.engine whose simulations use the sequenced rule."""
    module = ModuleType("src.engine")

    def dataset_microsimulation(dataset, reform=None, **kwargs):
        sim = SequencedSimulation(frame, year, reform)
        constructed.append(sim)
        return sim

    module.dataset_microsimulation = dataset_microsimulation
    module.frame_microsimulation = dataset_microsimulation
    module.base_microsimulation = dataset_microsimulation
    return module


def patch_worker(monkeypatch, worker, *, frame, year: int) -> list:
    """Run the full-H5 worker on fake simulations; returns them as built."""
    import sys

    constructed: list = []
    monkeypatch.setitem(
        sys.modules, "src.engine", engine_module(frame, year, constructed)
    )
    monkeypatch.setattr(
        worker, "build_policy_reform", lambda reform_id, scoring_type: FakePolicyReform
    )
    monkeypatch.setattr(
        worker,
        "runtime_provenance_from_environment",
        lambda **kwargs: {"pip_freeze": {"available": False}},
    )

    def save(build_simulation, dataset_path, path, *, year):
        build_simulation(dataset_path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"scenario")
        return {"sha256": "0" * 64, "size_bytes": 8}

    monkeypatch.setattr(worker, "save_chunked_microsimulation_h5", save)
    return constructed


def run_worker(worker, dataset: Path, year: int, scoring_type: str, output: Path, **kw):
    return worker.run_reform_full_h5_cell(
        year=year,
        reform_id="option1",
        scoring_type=scoring_type,
        dataset_path=dataset,
        output_root=output,
        run_prefix="test",
        **kw,
    )


def patch_tax_reform(monkeypatch) -> None:
    """Make every scorer load FakeTaxReform as the tax assumption reform."""
    monkeypatch.setattr(
        loader,
        "load_tax_assumption_reform_by_name",
        lambda name, **kwargs: FakeTaxReform,
    )
