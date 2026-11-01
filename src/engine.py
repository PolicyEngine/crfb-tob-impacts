"""Construct PolicyEngine US microsimulations through policyengine.py.

Certified-base simulations use policyengine.py's managed release bundle or
its dataset-resolution helpers. Project-built and explicit local datasets
retain the certified runtime version gate. The managed path enforces the
model<->data version pairing recorded in the release manifest: a populace dataset run under a model
version it was not calibrated for silently produces wrong aggregates. (Loaded
through bare ``policyengine_us`` on a mismatched runtime, the certified base's
income tax landed at 75% of the CBO target; through the managed path on the
matched version it lands at 99%.)
"""

from __future__ import annotations

import importlib.metadata as _metadata
from pathlib import Path
from typing import Any

from policyengine.tax_benefit_models.us import managed_microsimulation, us_latest


def base_microsimulation(reform: Any = None, **kwargs: Any):
    """A Microsimulation on the certified populace base.

    The base is the dataset pinned by the bundled release manifest, loaded
    through policyengine.py's managed path so the runtime model version must
    match the version the data was certified for (the gate raises otherwise).
    """
    return managed_microsimulation(reform=reform, **kwargs)


def dataset_microsimulation(dataset: Any, reform: Any = None, **kwargs: Any):
    """A Microsimulation on a project-built dataset (a Stage A-D year file or a
    scenario H5).

    policyengine.py's managed path resolves only manifest dataset names and
    ``hf://`` URIs, not local build artifacts, so the country-package
    simulation is constructed directly here. That is safe precisely because the
    dataset is the project's own output: it was built under the certified model
    version and is scored under it. ``_require_certified_runtime`` asserts that
    pairing still holds — the managed gate's protection, applied locally — so a
    build can never be silently scored under a mismatched model.
    """
    _require_certified_runtime()
    from policyengine_us import Microsimulation

    return Microsimulation(dataset=str(dataset), reform=reform, **kwargs)


def frame_microsimulation(dataset: Any, reform: Any = None):
    """A Microsimulation on a year frame's in-memory Core dataset.

    The frame supplies every entity, so no base file loads. The project's
    runtime gate applies as it does to ``dataset_microsimulation``.
    """
    _require_certified_runtime()
    from policyengine_us import Microsimulation

    return Microsimulation(dataset=dataset, reform=reform)


def _certified_base_source() -> tuple[str, str]:
    """Resolve the same pinned source and local mirror as the managed loader."""
    from policyengine.provenance.dataset_sources import materialize_dataset_source
    from policyengine.provenance.manifest import (
        resolve_local_managed_dataset_source,
        resolve_managed_dataset_reference,
    )

    uri = resolve_managed_dataset_reference("us")
    source = resolve_local_managed_dataset_source("us", uri)
    return uri, str(materialize_dataset_source(source))


def _is_single_year_entity_file(source: str) -> bool:
    import pandas as pd

    with pd.HDFStore(source, mode="r") as store:
        keys = set(store.keys())
    return {"/person", "/household", "/tax_unit"}.issubset(keys) and not any(
        key.startswith(("/person/", "/household/", "/tax_unit/")) for key in keys
    )


def stage_a_microsimulation(base_dataset: Any, reform: Any = None):
    """Load Stage A with only the base year stored.

    Each stored year holds its own copy of the inputs it changes, so storing
    every year through 2100 would not fit in memory on the full base. The
    constructor's default extension would also age inputs on default parameters
    through its last year. Instead, Core uprates each input from the base year
    with the simulation's own parameters. Certified bases use the managed
    loader's resolution helpers and bundle record; explicit local bases retain
    the project runtime gate.
    """
    _require_certified_runtime()
    local = bool(base_dataset) and Path(str(base_dataset)).is_file()
    uri, source = (None, str(base_dataset)) if local else _certified_base_source()
    single_year = _is_single_year_entity_file(source)
    if reform is not None and not single_year:
        raise ValueError(
            f"Economic input aging requires an entity-level single-year base: {source}. "
            "A multi-year base may already contain values aged on another path."
        )
    from policyengine_us import Microsimulation

    dataset = source
    if single_year:
        from policyengine_us.data.dataset_schema import (
            USMultiYearDataset,
            USSingleYearDataset,
        )

        # The constructor extends a single-year file but takes a multi-year
        # dataset as it stands.
        dataset = USMultiYearDataset(datasets=[USSingleYearDataset(file_path=source)])
    sim = Microsimulation(dataset=dataset, reform=reform)
    if reform is not None and not getattr(
        sim.tax_benefit_system, "_per_capita_uprating_built", False
    ):
        raise RuntimeError(
            "Economic input aging requires the simulation's system to run "
            "add_per_capita_uprating after applying the reform."
        )
    if uri is not None:
        from policyengine.tax_benefit_models.us.model import _managed_release_bundle

        sim.policyengine_bundle = _managed_release_bundle(uri, source)
    return sim


def certified_base_uri() -> str:
    """HF URI (pinned to a revision) of the certified populace base."""
    return us_latest.default_dataset_uri


def certified_base_build_id() -> str:
    """Build id of the certified populace base, for provenance records."""
    return us_latest.data_certification.data_build_id


def certified_model_version() -> str | None:
    """policyengine-us version the certified base was built and certified for."""
    return us_latest.data_certification.certified_for_model_version


def _require_certified_runtime() -> None:
    want = certified_model_version()
    have = _metadata.version("policyengine-us")
    if want and have != want:
        raise RuntimeError(
            f"policyengine-us {have} is installed, but the certified populace "
            f"base requires {want}. Pin policyengine-us=={want} (via a "
            f"policyengine[us] release whose manifest certifies it). Running "
            f"built datasets under a mismatched model version silently produces "
            f"wrong aggregates."
        )
