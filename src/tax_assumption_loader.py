from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
DEFAULT_TAX_ASSUMPTION_FACTORY = "create_wage_indexed_core_thresholds_reform"
TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION = "trustees-2025-core-thresholds-v1"
LEGACY_TRUSTEES_CORE_THRESHOLDS_ASSUMPTION = "trustees-core-thresholds-v1"
CURRENT_LAW_LITERAL_ASSUMPTION = "current-law-literal"
TRUSTEES_CORE_THRESHOLDS_MODULE = "policyengine_us.reforms.ssa.trustees_core_thresholds"
TRUSTEES_CORE_THRESHOLDS_FACTORY = "create_trustees_core_thresholds_reform"
SUPPORTED_TAX_ASSUMPTION_NAMES = frozenset(
    {
        TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
        LEGACY_TRUSTEES_CORE_THRESHOLDS_ASSUMPTION,
    }
)
TAX_ASSUMPTION_FACTORY_BY_NAME = {
    TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION: TRUSTEES_CORE_THRESHOLDS_FACTORY,
    LEGACY_TRUSTEES_CORE_THRESHOLDS_ASSUMPTION: TRUSTEES_CORE_THRESHOLDS_FACTORY,
}
TAX_ASSUMPTION_FACTORY_ALIASES = {
    DEFAULT_TAX_ASSUMPTION_FACTORY: "create_trustees_core_thresholds_reform",
    "create_trustees_core_thresholds_reform": DEFAULT_TAX_ASSUMPTION_FACTORY,
}
H5_LONG_TERM_CONTRACT_ATTR = "policyengine_long_term_contract"
H5_TAX_ASSUMPTION_ATTR = "policyengine_long_term_tax_assumption"
DEFAULT_REQUIRED_TARGET_SOURCE = "trustees_2025_current_law"
DEFAULT_MINIMUM_CALIBRATION_QUALITY = "exact"
ALLOW_EXTERNAL_TAX_ASSUMPTION_ENV = "CRFB_ALLOW_EXTERNAL_TAX_ASSUMPTION_MODULE"
ECONOMIC_ASSUMPTION_APPLIES_BEFORE = "tax_assumption"


@dataclass(frozen=True)
class TaxAssumptionContract:
    name: str | None
    active: bool
    start_year: int | None
    end_year: int | None


@dataclass(frozen=True)
class EconomicAssumptionContract:
    """The economic assumption reform a dataset was calibrated under.

    ``reform`` is the ``module:attribute`` path the build recorded and
    ``module_sha256`` the hash of that module's file at build time.
    """

    active: bool
    reform: str | None = None
    module_sha256: str | None = None


@dataclass(frozen=True)
class ScoringAssumptions:
    """Everything a scorer must apply to a dataset, read from its metadata.

    Every simulation on the dataset, baseline and reform alike, applies the
    economic assumption reform first and the tax assumption reform second.
    """

    tax_assumption: TaxAssumptionContract
    economic_assumption: EconomicAssumptionContract

    @property
    def active(self) -> bool:
        return self.tax_assumption.active or self.economic_assumption.active


def candidate_tax_assumption_modules() -> list[Path]:
    return []


def _tax_assumption_module_can_load(path: Path) -> bool:
    spec = importlib.util.spec_from_file_location(
        f"tax_assumptions_probe_{abs(hash(path))}",
        path,
    )
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError:
        return False
    return True


def resolve_tax_assumption_module(module_path: str | Path | None = None) -> Path:
    if module_path is None:
        module_path = os.environ.get("CRFB_TAX_ASSUMPTION_MODULE")

    if module_path:
        path = Path(module_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    raise FileNotFoundError(
        "External tax-assumption modules are diagnostic-only. Pass an explicit "
        "module path or set CRFB_TAX_ASSUMPTION_MODULE; production Trustees "
        "scoring imports the implementation from the packaged PolicyEngine-US "
        "runtime."
    )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _file_sha256(path: str | Path | None) -> str | None:
    if path is None:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    import hashlib

    digest = hashlib.sha256()
    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_tax_assumption_module(contract_name: str):
    if contract_name not in SUPPORTED_TAX_ASSUMPTION_NAMES:
        raise ValueError(f"Unsupported tax assumption: {contract_name!r}")
    try:
        return importlib.import_module(TRUSTEES_CORE_THRESHOLDS_MODULE)
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "The Trustees long-run tax assumption must come from the packaged "
            f"PolicyEngine-US runtime module {TRUSTEES_CORE_THRESHOLDS_MODULE!r}. "
            "Install or package a PolicyEngine-US version that includes it."
        ) from error


def canonical_tax_assumption_implementation_metadata(contract_name: str) -> dict:
    module = _canonical_tax_assumption_module(contract_name)
    module_file = getattr(module, "__file__", None)
    return {
        "source": "policyengine-us",
        "module": TRUSTEES_CORE_THRESHOLDS_MODULE,
        "factory": TRUSTEES_CORE_THRESHOLDS_FACTORY,
        "module_file": str(module_file) if module_file else None,
        "module_sha256": _file_sha256(module_file),
    }


def load_canonical_tax_assumption_reform(
    contract_name: str,
    *,
    start_year: int,
    end_year: int,
):
    module = _canonical_tax_assumption_module(contract_name)
    factory = getattr(module, TRUSTEES_CORE_THRESHOLDS_FACTORY)
    return factory(start_year=start_year, end_year=end_year)


def load_tax_assumption_reform(
    module_path: Path,
    factory_name: str,
    start_year: int,
    end_year: int,
):
    spec = importlib.util.spec_from_file_location("tax_assumptions", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tax assumption module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, factory_name):
        alias = TAX_ASSUMPTION_FACTORY_ALIASES.get(factory_name)
        if alias and hasattr(module, alias):
            factory_name = alias
        else:
            raise AttributeError(
                f"Tax assumption module {module_path} has no factory {factory_name!r}."
            )
    factory = getattr(module, factory_name)
    return factory(start_year=start_year, end_year=end_year)


def load_tax_assumption_reform_by_name(
    contract_name: str,
    *,
    start_year: int,
    end_year: int,
    module_path: str | Path | None = None,
    factory_name: str | None = None,
):
    if module_path is None and factory_name is None:
        return load_canonical_tax_assumption_reform(
            contract_name,
            start_year=start_year,
            end_year=end_year,
        )

    if not _env_bool(ALLOW_EXTERNAL_TAX_ASSUMPTION_ENV):
        raise ValueError(
            "Refusing external tax-assumption implementation for "
            f"{contract_name!r}. The production path must use "
            f"{TRUSTEES_CORE_THRESHOLDS_MODULE}:{TRUSTEES_CORE_THRESHOLDS_FACTORY} "
            "from the packaged PolicyEngine-US runtime. Set "
            f"{ALLOW_EXTERNAL_TAX_ASSUMPTION_ENV}=1 only for an explicit "
            "diagnostic sensitivity run."
        )

    module = resolve_tax_assumption_module(module_path)
    factory = factory_name or TAX_ASSUMPTION_FACTORY_BY_NAME.get(
        contract_name,
        DEFAULT_TAX_ASSUMPTION_FACTORY,
    )
    return load_tax_assumption_reform(
        module,
        factory,
        start_year=start_year,
        end_year=end_year,
    )


def compose_reforms(*reforms):
    """Compose reforms in the order given, dropping ``None``.

    PolicyEngine applies a tuple of reforms left to right, so the first
    reform's parameter changes are in place before the next one runs.
    """
    active = tuple(reform for reform in reforms if reform is not None)
    if not active:
        return None
    if len(active) == 1:
        return active[0]
    return active


def _validated_reform(candidate, spec: str):
    from policyengine_core.reforms import Reform

    if isinstance(candidate, type) and issubclass(candidate, Reform):
        return candidate
    if isinstance(candidate, dict):
        return Reform.from_dict(candidate, country_id="us")
    if isinstance(candidate, tuple) and candidate:
        return tuple(_validated_reform(item, spec) for item in candidate)
    raise TypeError(
        f"{spec} is a {type(candidate).__name__}; an economic assumption "
        "reform must be a Reform subclass, a parameter dict, or a tuple of "
        "those. Point at the reform itself, not at a factory that builds it."
    )


def load_economic_assumption_reform(spec: str):
    """Import the reform named by ``module:attribute`` (attribute may be
    dotted) and check that it is a reform."""
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError(f"Expected module:attribute, got {spec!r}.")
    target = importlib.import_module(module_name)
    for part in attribute.split("."):
        target = getattr(target, part)
    return _validated_reform(target, spec)


def economic_assumption_provenance(spec: str) -> dict:
    """The ``module:attribute`` path, plus the module file and its hash."""
    module = importlib.import_module(spec.partition(":")[0])
    module_file = getattr(module, "__file__", None)
    return {
        "reform": spec,
        "module_file": module_file,
        "module_sha256": _file_sha256(module_file),
    }


def metadata_path_for_dataset(dataset_name: Any) -> Path | None:
    dataset_path = dataset_path_for_contract(dataset_name)
    if dataset_path is None:
        return None
    return Path(f"{dataset_path}.metadata.json")


def dataset_path_for_contract(dataset_name: Any) -> Path | None:
    if isinstance(dataset_name, (str, Path)):
        path = Path(dataset_name).expanduser()
        if path.exists():
            return path

    file_path = getattr(dataset_name, "file_path", None)
    if file_path:
        path = Path(file_path).expanduser()
        if path.exists():
            return path

    return None


def _load_json_h5_attr(attrs: Any, key: str) -> dict:
    raw_value = attrs.get(key)
    if raw_value is None:
        return {}
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")
    if not isinstance(raw_value, str):
        return {}
    return json.loads(raw_value)


def _load_embedded_h5_tax_assumption_metadata(dataset_path: Path) -> dict:
    try:
        import h5py
    except ImportError:  # pragma: no cover - h5py is present in scoring envs
        return {}

    try:
        with h5py.File(dataset_path, "r") as store:
            contract = _load_json_h5_attr(store.attrs, H5_LONG_TERM_CONTRACT_ATTR)
            if contract:
                return contract

            tax_assumption = _load_json_h5_attr(
                store.attrs,
                H5_TAX_ASSUMPTION_ATTR,
            )
            if tax_assumption:
                return {"tax_assumption": tax_assumption}
    except OSError:
        return {}

    return {}


def load_tax_assumption_metadata_for_dataset(dataset_name: Any) -> dict:
    metadata_path = metadata_path_for_dataset(dataset_name)
    if metadata_path is not None and metadata_path.exists():
        return json.loads(metadata_path.read_text(encoding="utf-8"))

    dataset_path = dataset_path_for_contract(dataset_name)
    if dataset_path is None:
        return {}
    return _load_embedded_h5_tax_assumption_metadata(dataset_path)


def tax_assumption_contract_from_metadata(
    metadata: dict,
    year: int,
) -> TaxAssumptionContract:
    """The tax assumption contract, for a path that applies nothing else.

    A path that rebuilds only the tax assumption reform would score a dataset
    calibrated under an economic assumption reform without it, so it drifts
    off its targets; this refuses such a dataset. Scorers that apply both read
    ``scoring_assumptions_from_metadata`` instead.
    """
    economic_assumption = metadata.get("economic_assumption") or {}
    if economic_assumption.get("active"):
        raise ValueError(
            "Dataset was built with the economic assumption reform "
            f"{economic_assumption.get('reform')!r}, which this path does not "
            "apply; refusing to score it under the tax assumption alone. Load "
            "its reforms with load_scoring_assumption_reform_for_metadata."
        )
    return _tax_assumption_contract_from_metadata(metadata, year)


def _tax_assumption_contract_from_metadata(
    metadata: dict,
    year: int,
) -> TaxAssumptionContract:
    tax_assumption = metadata.get("tax_assumption") or {}
    name = tax_assumption.get("name")
    if name in (None, "", CURRENT_LAW_LITERAL_ASSUMPTION):
        return TaxAssumptionContract(
            name=name,
            active=False,
            start_year=None,
            end_year=None,
        )

    if name not in SUPPORTED_TAX_ASSUMPTION_NAMES:
        raise ValueError(f"Unsupported tax assumption metadata: {tax_assumption!r}")

    start_year = int(tax_assumption.get("start_year", 2035))
    end_year = int(tax_assumption.get("end_year", 2100))
    return TaxAssumptionContract(
        name=name,
        active=start_year <= int(year) <= end_year,
        start_year=start_year,
        end_year=end_year,
    )


def tax_assumption_contract_for_dataset(
    dataset_name: Any,
    year: int,
) -> TaxAssumptionContract:
    metadata = load_tax_assumption_metadata_for_dataset(dataset_name)
    if not metadata and int(year) >= 2035 and dataset_path_for_contract(dataset_name):
        raise FileNotFoundError(
            "Tax-assumption contract metadata missing for post-2034 dataset "
            f"{dataset_path_for_contract(dataset_name)}. Refusing ambiguous "
            "long-run scoring artifact."
        )
    return tax_assumption_contract_from_metadata(metadata, year)


def set_required_long_run_contract_env(
    year: int,
    *,
    require_tax_assumption_contract: bool = True,
    required_target_source: str = DEFAULT_REQUIRED_TARGET_SOURCE,
    required_tax_assumption: str = TRUSTEES_2025_CORE_THRESHOLDS_ASSUMPTION,
    minimum_calibration_quality: str = DEFAULT_MINIMUM_CALIBRATION_QUALITY,
    start_year: int = 2035,
    end_year: int = 2100,
) -> None:
    os.environ.setdefault("CRFB_REQUIRED_TARGET_SOURCE", required_target_source)
    os.environ["CRFB_MIN_CALIBRATION_QUALITY"] = minimum_calibration_quality
    if require_tax_assumption_contract and start_year <= int(year) <= end_year:
        os.environ.setdefault("CRFB_REQUIRED_TAX_ASSUMPTION", required_tax_assumption)
    else:
        os.environ.pop("CRFB_REQUIRED_TAX_ASSUMPTION", None)


def load_tax_assumption_reform_for_metadata(
    metadata: dict,
    year: int,
    *,
    module_path: str | Path | None = None,
    factory_name: str | None = None,
):
    contract = tax_assumption_contract_from_metadata(metadata, year)
    if not contract.active:
        return None
    if contract.name is None:
        return None

    return load_tax_assumption_reform_by_name(
        contract.name,
        start_year=contract.start_year or 2035,
        end_year=contract.end_year or 2100,
        module_path=module_path,
        factory_name=factory_name,
    )


def load_tax_assumption_reform_for_dataset(
    dataset_name: Any,
    year: int,
    *,
    module_path: str | Path | None = None,
    factory_name: str | None = None,
):
    return load_tax_assumption_reform_for_metadata(
        load_tax_assumption_metadata_for_dataset(dataset_name),
        year,
        module_path=module_path,
        factory_name=factory_name,
    )


def economic_assumption_contract_from_metadata(
    metadata: dict,
) -> EconomicAssumptionContract:
    """Read and check the dataset's economic assumption record.

    Fails closed on any record that does not pin one reform: an active record
    must name a ``module:attribute`` path, carry the hash of that module, and
    apply before the tax assumption; an inactive record must name no reform.
    """
    record = metadata.get("economic_assumption")
    if record is None or record == {}:
        return EconomicAssumptionContract(active=False)
    if not isinstance(record, dict):
        raise ValueError(f"Malformed economic assumption metadata: {record!r}")
    active = record.get("active", False)
    if active is not True and active is not False:
        raise ValueError(
            "Economic assumption metadata must set active to true or false, "
            f"got {active!r}."
        )
    reform = record.get("reform")
    if not active:
        if reform is not None:
            raise ValueError(
                "Economic assumption metadata is inactive but names the reform "
                f"{reform!r}; refusing an ambiguous dataset."
            )
        return EconomicAssumptionContract(active=False)
    module_name, separator, attribute = (
        reform.partition(":") if isinstance(reform, str) else ("", "", "")
    )
    if not (module_name and separator and attribute):
        raise ValueError(
            "Economic assumption metadata is active but records no "
            f"module:attribute reform path (got {reform!r}); refusing to guess "
            "which reform the dataset was calibrated under."
        )
    applies_before = record.get("applies_before", ECONOMIC_ASSUMPTION_APPLIES_BEFORE)
    if applies_before != ECONOMIC_ASSUMPTION_APPLIES_BEFORE:
        raise ValueError(
            f"Economic assumption reform {reform!r} applies before "
            f"{applies_before!r}; scorers apply it only before "
            f"{ECONOMIC_ASSUMPTION_APPLIES_BEFORE!r}."
        )
    module_sha256 = record.get("module_sha256")
    if not module_sha256:
        raise ValueError(
            f"Economic assumption reform {reform!r} records no module_sha256, "
            "so its identity cannot be checked; rebuild the dataset with "
            "economic_assumption_provenance recorded."
        )
    return EconomicAssumptionContract(
        active=True,
        reform=reform,
        module_sha256=str(module_sha256),
    )


def verify_economic_assumption_identity(
    contract: EconomicAssumptionContract,
) -> dict | None:
    """Check that the module the scorer would load is the one the build used.

    Returns the loaded module's provenance, or ``None`` when the contract is
    inactive. Raises, naming both hashes, when the module file changed.
    """
    if not contract.active:
        return None
    provenance = economic_assumption_provenance(contract.reform)
    if provenance["module_sha256"] != contract.module_sha256:
        raise ValueError(
            f"Economic assumption reform {contract.reform!r} does not match the "
            "module the dataset was built with: the dataset records "
            f"module_sha256 {contract.module_sha256}, the loaded module "
            f"{provenance['module_file']} hashes to "
            f"{provenance['module_sha256']}."
        )
    return provenance


def load_economic_assumption_reform_for_metadata(metadata: dict):
    """The dataset's economic assumption reform, or ``None`` if it has none.

    The module is hashed and checked against the recorded hash before the
    reform is imported from it.
    """
    contract = economic_assumption_contract_from_metadata(metadata)
    if not contract.active:
        return None
    verify_economic_assumption_identity(contract)
    return load_economic_assumption_reform(contract.reform)


def load_economic_assumption_reform_for_dataset(dataset_name: Any):
    return load_economic_assumption_reform_for_metadata(
        load_tax_assumption_metadata_for_dataset(dataset_name)
    )


def economic_assumption_output_metadata(
    contract: EconomicAssumptionContract,
) -> dict:
    """The record a scorer writes into its output metadata."""
    if not contract.active:
        return {"active": False, "reform": None}
    provenance = verify_economic_assumption_identity(contract)
    return {
        "active": True,
        "applies_before": ECONOMIC_ASSUMPTION_APPLIES_BEFORE,
        "reform": contract.reform,
        "module_sha256": contract.module_sha256,
        "loaded_module_file": provenance["module_file"],
    }


def scoring_assumptions_from_metadata(
    metadata: dict,
    year: int,
) -> ScoringAssumptions:
    return ScoringAssumptions(
        tax_assumption=_tax_assumption_contract_from_metadata(metadata, year),
        economic_assumption=economic_assumption_contract_from_metadata(metadata),
    )


def scoring_assumptions_for_dataset(
    dataset_name: Any,
    year: int,
) -> ScoringAssumptions:
    metadata = load_tax_assumption_metadata_for_dataset(dataset_name)
    if not metadata and int(year) >= 2035 and dataset_path_for_contract(dataset_name):
        raise FileNotFoundError(
            "Tax-assumption contract metadata missing for post-2034 dataset "
            f"{dataset_path_for_contract(dataset_name)}. Refusing ambiguous "
            "long-run scoring artifact."
        )
    return scoring_assumptions_from_metadata(metadata, year)


def load_scoring_assumption_reform_for_metadata(
    metadata: dict,
    year: int,
    *,
    module_path: str | Path | None = None,
    factory_name: str | None = None,
):
    """The reform every simulation on the dataset applies before any policy:
    the economic assumption reform, then the tax assumption reform.

    Compose a policy reform after it, ``compose_reforms(this, policy)``, so the
    baseline and the reform carry the same assumptions. ``None`` when the
    dataset carries neither.
    """
    economic = load_economic_assumption_reform_for_metadata(metadata)
    contract = _tax_assumption_contract_from_metadata(metadata, year)
    tax = None
    if contract.active and contract.name is not None:
        tax = load_tax_assumption_reform_by_name(
            contract.name,
            start_year=contract.start_year or 2035,
            end_year=contract.end_year or 2100,
            module_path=module_path,
            factory_name=factory_name,
        )
    return compose_reforms(economic, tax)


def load_scoring_assumption_reform_for_dataset(
    dataset_name: Any,
    year: int,
    *,
    module_path: str | Path | None = None,
    factory_name: str | None = None,
):
    return load_scoring_assumption_reform_for_metadata(
        load_tax_assumption_metadata_for_dataset(dataset_name),
        year,
        module_path=module_path,
        factory_name=factory_name,
    )
