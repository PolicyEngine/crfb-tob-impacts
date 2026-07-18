"""Construct PolicyEngine US microsimulations through policyengine.py.

Every simulation in this project is built through policyengine.py's certified
("managed") release bundle, never by constructing ``policyengine_us``
simulations directly. The managed path enforces the model<->data version
pairing recorded in the release manifest: a populace dataset run under a model
version it was not calibrated for silently produces wrong aggregates. (Loaded
through bare ``policyengine_us`` on a mismatched runtime, the certified base's
income tax landed at 75% of the CBO target; through the managed path on the
matched version it lands at 99%.)
"""

from __future__ import annotations

import importlib.metadata as _metadata
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
