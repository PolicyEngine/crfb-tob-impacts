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


@dataclass(frozen=True)
class TaxAssumptionContract:
    name: str | None
    active: bool
    start_year: int | None
    end_year: int | None


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
