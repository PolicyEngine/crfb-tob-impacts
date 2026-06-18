from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import AbstractSet, Any, Callable, Mapping

import numpy as np
import pandas as pd
from policyengine_core.data import Dataset
from policyengine_core.periods.config import ETERNITY
from policyengine_core.reforms import Reform

try:
    from .engine import dataset_microsimulation
    from .reforms import (
        get_option10_behavioral_dict,
        get_option10_reform,
        get_option11_behavioral_dict,
        get_option11_reform,
        get_option12_behavioral_dict,
        get_option12_reform,
        get_option1_behavioral_dict,
        get_option1_reform,
        get_option2_behavioral_dict,
        get_option2_reform,
        get_option3_behavioral_dict,
        get_option3_reform,
        get_option4_behavioral_dict,
        get_option4_reform,
        get_option5_behavioral_dict,
        get_option5_reform,
        get_option6_behavioral_dict,
        get_option6_reform,
        get_option7_behavioral_dict,
        get_option7_reform,
        get_option8_behavioral_dict,
        get_option8_reform,
        get_option9_behavioral_dict,
        get_option9_reform,
        get_reverse_roth_behavioral_reform,
        get_reverse_roth_reform,
        get_tax93_behavioral_dict,
        get_tax93_reform,
    )
    from .tax_assumption_loader import (
        TaxAssumptionContract,
        load_tax_assumption_reform_for_dataset,
        tax_assumption_contract_for_dataset,
    )
except ImportError:  # pragma: no cover - script execution fallback
    from engine import dataset_microsimulation
    from reforms import (
        get_option10_behavioral_dict,
        get_option10_reform,
        get_option11_behavioral_dict,
        get_option11_reform,
        get_option12_behavioral_dict,
        get_option12_reform,
        get_option1_behavioral_dict,
        get_option1_reform,
        get_option2_behavioral_dict,
        get_option2_reform,
        get_option3_behavioral_dict,
        get_option3_reform,
        get_option4_behavioral_dict,
        get_option4_reform,
        get_option5_behavioral_dict,
        get_option5_reform,
        get_option6_behavioral_dict,
        get_option6_reform,
        get_option7_behavioral_dict,
        get_option7_reform,
        get_option8_behavioral_dict,
        get_option8_reform,
        get_option9_behavioral_dict,
        get_option9_reform,
        get_reverse_roth_behavioral_reform,
        get_reverse_roth_reform,
        get_tax93_behavioral_dict,
        get_tax93_reform,
    )
    from tax_assumption_loader import (
        TaxAssumptionContract,
        load_tax_assumption_reform_for_dataset,
        tax_assumption_contract_for_dataset,
    )


STATIC_REFORM_FUNCTIONS = {
    "option1": get_option1_reform,
    "option2": get_option2_reform,
    "option3": get_option3_reform,
    "option4": get_option4_reform,
    "option5": get_option5_reform,
    "option6": get_option6_reform,
    "option7": get_option7_reform,
    "option8": get_option8_reform,
    "option9": get_option9_reform,
    "option10": get_option10_reform,
    "option11": get_option11_reform,
    "option12": get_option12_reform,
    "reverse_roth": get_reverse_roth_reform,
    "tax93": get_tax93_reform,
}

BEHAVIORAL_REFORM_FUNCTIONS = {
    "option1": get_option1_behavioral_dict,
    "option2": get_option2_behavioral_dict,
    "option3": get_option3_behavioral_dict,
    "option4": get_option4_behavioral_dict,
    "option5": get_option5_behavioral_dict,
    "option6": get_option6_behavioral_dict,
    "option7": get_option7_behavioral_dict,
    "option8": get_option8_behavioral_dict,
    "option9": get_option9_behavioral_dict,
    "option10": get_option10_behavioral_dict,
    "option11": get_option11_behavioral_dict,
    "option12": get_option12_behavioral_dict,
    "reverse_roth": get_reverse_roth_behavioral_reform,
    "tax93": get_tax93_behavioral_dict,
}

OPTION6_PHASE_IN_RATES = {
    2026: 0.1307,
    2027: 0.2614,
    2028: 0.3922,
    2029: 0.5229,
    2030: 0.6536,
    2031: 0.7843,
    2032: 0.9150,
}

BATCH_EMPLOYER_NET_REFORMS = frozenset({"option5", "option6", "option12"})
MODAL_EMPLOYER_NET_REFORMS = frozenset({"option5", "option6", "option12"})
MODAL_UNSUPPORTED_REFORMS = frozenset({"option13", "balanced_fix"})
SPECIAL_BASELINE_REFORMS = frozenset({"option13", "balanced_fix"})


@dataclass(frozen=True)
class BaselineResult:
    revenue: float
    tob_medicare_hi: float
    tob_oasdi: float
    tob_total: float
    social_security: float
    taxable_payroll: float
    tax_assumption_name: str | None = None
    tax_assumption_active: bool = False


@dataclass(frozen=True)
class ScenarioHouseholdMetrics:
    household_ids: np.ndarray
    income_tax: np.ndarray
    tob_medicare_hi: np.ndarray
    tob_oasdi: np.ndarray
    social_security: np.ndarray
    taxable_payroll: np.ndarray
    employer_ss_tax_revenue: np.ndarray
    employer_medicare_tax_revenue: np.ndarray
    household_weight: np.ndarray | None = None


SCENARIO_HOUSEHOLD_METRIC_VARIABLES = (
    "household_ids",
    "income_tax",
    "tob_medicare_hi",
    "tob_oasdi",
    "social_security",
    "taxable_payroll",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
)

SCENARIO_HOUSEHOLD_VALUE_VARIABLES = tuple(
    name for name in SCENARIO_HOUSEHOLD_METRIC_VARIABLES if name != "household_ids"
)

DEFAULT_REFORM_RAW_H5_MATERIALIZE_VARIABLES = (
    "household_id",
    "household_weight",
    "income_tax",
    "tob_revenue_medicare_hi",
    "tob_revenue_oasdi",
    "social_security",
    "taxable_wages_for_social_security",
    "taxable_earnings_for_social_security",
    "taxable_self_employment_income_for_social_security",
    "social_security_taxable_self_employment_income",
    "employer_ss_tax_income_tax_revenue",
    "employer_medicare_tax_income_tax_revenue",
    "employee_social_security_tax",
    "employee_medicare_tax",
    "employer_social_security_tax",
    "employer_medicare_tax",
    "self_employment_tax",
    "payroll_tax",
    "household_net_income",
)


@dataclass(frozen=True)
class ScenarioAggregate:
    revenue: float
    tob_medicare_hi: float
    tob_oasdi: float
    tob_total: float
    social_security: float
    taxable_payroll: float
    employer_ss_tax_revenue: float
    employer_medicare_tax_revenue: float


US_ENTITY_KEYS = (
    "person",
    "household",
    "tax_unit",
    "spm_unit",
    "family",
    "marital_unit",
)


def _raw_h5_period_matches(period: Any, year: int) -> bool:
    return getattr(period, "unit", None) == ETERNITY or str(period) == str(year)


def _raw_h5_period_sort_key(period: Any, year: int) -> tuple[int, str]:
    if str(period) == str(year):
        return (0, str(period))
    if getattr(period, "unit", None) == ETERNITY:
        return (1, str(period))
    return (2, str(period))


def _raw_h5_array(values: Any) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype == object:
        array = array.astype(str)
    return array


def save_microsimulation_raw_h5(
    sim: Any,
    output_path: str | Path,
    *,
    year: int,
) -> dict[str, Any]:
    """Persist cached scenario microdata in PolicyEngine-US entity-table H5 form.

    This records native-entity arrays already materialized by the scenario
    simulation, including source inputs and formula dependencies reached while
    computing CRFB metrics. It does not trigger broad extra calculations.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entity_counts: dict[str, int] = {}
    for population in sim.populations.values():
        entity_key = population.entity.key
        if entity_key in US_ENTITY_KEYS:
            entity_counts[entity_key] = int(population.count)

    entity_columns: dict[str, dict[str, np.ndarray]] = {
        entity_key: {} for entity_key in entity_counts
    }
    skipped_wrong_shape: list[dict[str, Any]] = []

    for variable_name, variable in sorted(sim.tax_benefit_system.variables.items()):
        entity_key = getattr(variable.entity, "key", None)
        if entity_key not in entity_columns:
            continue

        holder = sim.get_holder(variable_name)
        candidate_periods = [
            period
            for branch_name, period in holder.get_known_branch_periods()
            if branch_name == "default" and _raw_h5_period_matches(period, year)
        ]
        if not candidate_periods:
            continue

        period = sorted(
            candidate_periods,
            key=lambda known_period: _raw_h5_period_sort_key(known_period, year),
        )[0]
        array = holder.get_array(period, "default")
        if array is None:
            continue
        values = _raw_h5_array(array)
        expected_length = entity_counts[entity_key]
        if values.ndim != 1 or len(values) != expected_length:
            skipped_wrong_shape.append(
                {
                    "variable": variable_name,
                    "entity": entity_key,
                    "period": str(period),
                    "shape": list(values.shape),
                    "expected_length": expected_length,
                }
            )
            continue
        entity_columns[entity_key][variable_name] = values

    entities_written: dict[str, dict[str, Any]] = {}
    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    tmp_path.unlink(missing_ok=True)
    with pd.HDFStore(tmp_path, mode="w") as store:
        for entity_key in US_ENTITY_KEYS:
            columns = entity_columns.get(entity_key, {})
            if not columns:
                continue
            dataframe = pd.DataFrame(columns)
            store.put(entity_key, dataframe, format="table")
            entities_written[entity_key] = {
                "rows": int(len(dataframe)),
                "columns": list(dataframe.columns),
                "column_count": int(len(dataframe.columns)),
            }
        store.put("_time_period", pd.Series([int(year)]), format="table")

    if not entities_written:
        tmp_path.unlink(missing_ok=True)
        raise ValueError(
            f"No cached simulation arrays were available to save to {output_path}."
        )

    tmp_path.replace(output_path)
    size_bytes = output_path.stat().st_size
    return {
        "artifact_type": "policyengine_us_entity_table_raw_scenario_h5",
        "artifact_version": 1,
        "path": str(output_path),
        "year": int(year),
        "size_bytes": int(size_bytes),
        "entities": entities_written,
        "entity_count": int(len(entities_written)),
        "variable_count": int(
            sum(entity["column_count"] for entity in entities_written.values())
        ),
        "skipped_wrong_shape": skipped_wrong_shape[:100],
        "skipped_wrong_shape_count": int(len(skipped_wrong_shape)),
        "capture_policy": (
            "native-entity arrays cached by the completed scenario simulation "
            "for the requested year or ETERNITY; no broad extra calculations"
        ),
    }


def _normalize_dataset(dataset: Any) -> Any:
    if isinstance(dataset, Dataset):
        return dataset
    if isinstance(dataset, (str, Path)):
        path = Path(dataset).expanduser()
        if path.exists():
            return Dataset.from_file(str(path))
    return dataset


def _float_array(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=float)


def scenario_household_metrics_arrays(
    metrics: ScenarioHouseholdMetrics,
) -> dict[str, np.ndarray]:
    arrays = {
        "household_ids": np.asarray(metrics.household_ids),
        "income_tax": _float_array(metrics.income_tax),
        "tob_medicare_hi": _float_array(metrics.tob_medicare_hi),
        "tob_oasdi": _float_array(metrics.tob_oasdi),
        "social_security": _float_array(metrics.social_security),
        "taxable_payroll": _float_array(metrics.taxable_payroll),
        "employer_ss_tax_revenue": _float_array(metrics.employer_ss_tax_revenue),
        "employer_medicare_tax_revenue": _float_array(
            metrics.employer_medicare_tax_revenue
        ),
    }
    if metrics.household_weight is not None:
        arrays["household_weight"] = _float_array(metrics.household_weight)
    return arrays


def save_scenario_household_metrics(
    metrics: ScenarioHouseholdMetrics,
    metrics_path: str | Path,
    *,
    compressed: bool = True,
) -> None:
    path = Path(metrics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = scenario_household_metrics_arrays(metrics)
    save = np.savez_compressed if compressed else np.savez
    save(path, **arrays)


def _aligned_metric_array(
    metrics: ScenarioHouseholdMetrics,
    variable_name: str,
    household_ids: np.ndarray,
) -> np.ndarray:
    values = _float_array(getattr(metrics, variable_name))
    source_ids = np.asarray(metrics.household_ids)
    target_ids = np.asarray(household_ids)
    if np.array_equal(source_ids, target_ids):
        return values

    order = np.argsort(source_ids)
    sorted_source_ids = source_ids[order]
    if np.unique(sorted_source_ids).size != sorted_source_ids.size:
        raise ValueError("Cannot align household metrics with duplicate household_ids")

    positions = np.searchsorted(sorted_source_ids, target_ids)
    valid_positions = positions < sorted_source_ids.size
    matched = np.zeros(target_ids.shape, dtype=bool)
    matched[valid_positions] = (
        sorted_source_ids[positions[valid_positions]] == target_ids[valid_positions]
    )
    if not bool(np.all(matched)):
        missing = target_ids[~matched]
        preview = ", ".join(str(value) for value in missing[:5])
        raise ValueError(
            "Baseline household metrics are missing reform household_ids: " + preview
        )
    return values[order][positions]


def reform_household_metric_change_arrays(
    *,
    baseline_metrics: ScenarioHouseholdMetrics,
    reform_metrics: ScenarioHouseholdMetrics,
    tolerance: float = 1e-9,
) -> tuple[dict[str, np.ndarray], list[str], list[str]]:
    household_ids = np.asarray(reform_metrics.household_ids)
    arrays: dict[str, np.ndarray] = {"household_ids": household_ids}
    if reform_metrics.household_weight is not None:
        arrays["household_weight"] = _float_array(reform_metrics.household_weight)
    changed: list[str] = []
    unchanged: list[str] = []

    for variable_name in SCENARIO_HOUSEHOLD_VALUE_VARIABLES:
        baseline_values = _aligned_metric_array(
            baseline_metrics,
            variable_name,
            household_ids,
        )
        reform_values = _float_array(getattr(reform_metrics, variable_name))
        change = reform_values - baseline_values
        if bool(np.any(np.abs(change) > tolerance)):
            arrays[f"baseline_{variable_name}"] = baseline_values
            arrays[f"reform_{variable_name}"] = reform_values
            arrays[f"{variable_name}_change"] = change
            changed.append(variable_name)
        else:
            unchanged.append(variable_name)

    arrays["changed_metric_variables"] = np.asarray(changed, dtype="U")
    arrays["unchanged_metric_variables"] = np.asarray(unchanged, dtype="U")
    return arrays, changed, unchanged


def save_reform_household_metric_changes(
    *,
    baseline_metrics: ScenarioHouseholdMetrics,
    reform_metrics: ScenarioHouseholdMetrics,
    metrics_path: str | Path,
    tolerance: float = 1e-9,
    compressed: bool = True,
) -> dict[str, Any]:
    path = Path(metrics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays, changed, unchanged = reform_household_metric_change_arrays(
        baseline_metrics=baseline_metrics,
        reform_metrics=reform_metrics,
        tolerance=tolerance,
    )
    save = np.savez_compressed if compressed else np.savez
    save(path, **arrays)
    return {
        "artifact_type": "compact_reform_household_metric_changes",
        "changed_metric_variables": changed,
        "unchanged_metric_variables": unchanged,
        "saved_arrays": list(arrays),
    }


def scenario_aggregate_to_dict(
    aggregate: ScenarioAggregate,
) -> dict[str, float]:
    return {
        "revenue": float(aggregate.revenue),
        "tob_medicare_hi": float(aggregate.tob_medicare_hi),
        "tob_oasdi": float(aggregate.tob_oasdi),
        "tob_total": float(aggregate.tob_total),
        "social_security": float(aggregate.social_security),
        "taxable_payroll": float(aggregate.taxable_payroll),
        "employer_ss_tax_revenue": float(aggregate.employer_ss_tax_revenue),
        "employer_medicare_tax_revenue": float(aggregate.employer_medicare_tax_revenue),
    }


def scenario_aggregate_from_dict(
    values: Mapping[str, Any],
) -> ScenarioAggregate:
    return ScenarioAggregate(
        revenue=float(values["revenue"]),
        tob_medicare_hi=float(values["tob_medicare_hi"]),
        tob_oasdi=float(values["tob_oasdi"]),
        tob_total=float(values["tob_total"]),
        social_security=float(values["social_security"]),
        taxable_payroll=float(values["taxable_payroll"]),
        employer_ss_tax_revenue=float(values["employer_ss_tax_revenue"]),
        employer_medicare_tax_revenue=float(values["employer_medicare_tax_revenue"]),
    )


def baseline_result_to_dict(
    baseline: BaselineResult,
) -> dict[str, float | str | bool | None]:
    return {
        "revenue": float(baseline.revenue),
        "tob_medicare_hi": float(baseline.tob_medicare_hi),
        "tob_oasdi": float(baseline.tob_oasdi),
        "tob_total": float(baseline.tob_total),
        "social_security": float(baseline.social_security),
        "taxable_payroll": float(baseline.taxable_payroll),
        "tax_assumption_name": baseline.tax_assumption_name,
        "tax_assumption_active": bool(baseline.tax_assumption_active),
    }


@dataclass(frozen=True)
class MicrodataSampleResult:
    dataset_name: str
    metadata: dict[str, float | int | str | bool]


def _dataset_path(dataset_name: Any) -> Path:
    if isinstance(dataset_name, (str, Path)):
        path = Path(dataset_name).expanduser()
        if path.exists():
            return path

    file_path = getattr(dataset_name, "file_path", None)
    if file_path:
        path = Path(file_path).expanduser()
        if path.exists():
            return path

    raise ValueError(
        "Microdata sampling requires a filesystem-backed HDF5 dataset path"
    )


def _tax_assumption_contract(
    *,
    year: int,
    dataset_name: Any,
) -> TaxAssumptionContract:
    return tax_assumption_contract_for_dataset(dataset_name, year)


def _resolve_baseline_reform_for_dataset(
    *,
    year: int,
    dataset_name: Any,
    baseline_reform: Any | None,
) -> Any | None:
    contract = _tax_assumption_contract(year=year, dataset_name=dataset_name)
    if contract.active:
        return load_tax_assumption_reform_for_dataset(dataset_name, year)
    if baseline_reform is not None:
        return baseline_reform
    return load_tax_assumption_reform_for_dataset(dataset_name, year)


def _annotate_baseline_tax_assumption(
    baseline: BaselineResult,
    *,
    year: int,
    dataset_name: Any,
) -> BaselineResult:
    contract = _tax_assumption_contract(year=year, dataset_name=dataset_name)
    return replace(
        baseline,
        tax_assumption_name=contract.name,
        tax_assumption_active=contract.active,
    )


def _validate_baseline_tax_assumption(
    baseline: BaselineResult,
    *,
    year: int,
    dataset_name: Any,
) -> None:
    contract = _tax_assumption_contract(year=year, dataset_name=dataset_name)
    if not contract.active:
        return
    if (
        baseline.tax_assumption_active is not True
        or baseline.tax_assumption_name != contract.name
    ):
        raise ValueError(
            "BaselineResult tax assumption does not match dataset metadata for "
            f"{_dataset_path(dataset_name)} in {year}: baseline has "
            f"{baseline.tax_assumption_name!r} active="
            f"{baseline.tax_assumption_active!r}, dataset requires "
            f"{contract.name!r} active=True."
        )


def _first_existing_period(group: Any, preferred_period: str) -> str:
    if preferred_period in group:
        return preferred_period
    periods = [period for period in group.keys() if period != "ETERNITY"]
    if periods:
        return sorted(periods)[0]
    return sorted(group.keys())[0]


def _positions_for_ids(ids: np.ndarray, values: np.ndarray) -> np.ndarray:
    ids = np.asarray(ids)
    values = np.asarray(values)
    order = np.argsort(ids)
    sorted_ids = ids[order]
    positions = np.searchsorted(sorted_ids, values)
    invalid = positions >= len(sorted_ids)
    safe_positions = np.minimum(positions, len(sorted_ids) - 1)
    invalid |= sorted_ids[safe_positions] != values
    if invalid.any():
        missing = values[invalid]
        raise ValueError(
            "Entity relationship contains IDs missing from the parent entity: "
            + ", ".join(str(value) for value in missing[:5])
        )
    return order[positions]


def _household_person_sum(
    h5_file: Any,
    *,
    period: str,
    household_ids: np.ndarray,
    person_household_ids: np.ndarray,
    variable_names: tuple[str, ...],
) -> np.ndarray:
    household_values = np.zeros(household_ids.shape[0], dtype=float)
    person_household_positions = _positions_for_ids(
        household_ids,
        person_household_ids,
    )
    for variable_name in variable_names:
        if variable_name not in h5_file or period not in h5_file[variable_name]:
            continue
        values = np.asarray(h5_file[variable_name][period][:], dtype=float)
        np.add.at(household_values, person_household_positions, values)
    return household_values


def _sample_household_indices(
    *,
    household_ids: np.ndarray,
    household_weights: np.ndarray,
    household_social_security: np.ndarray,
    household_earnings: np.ndarray,
    sample_fraction: float,
    seed: int,
    min_households: int,
    drop_zero_weight_households: bool,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    if not 0 <= sample_fraction <= 1:
        raise ValueError("sample_fraction must be between 0 and 1")

    eligible_mask = np.ones(household_ids.shape[0], dtype=bool)
    if drop_zero_weight_households:
        eligible_mask &= household_weights != 0

    eligible_indices = np.flatnonzero(eligible_mask)
    if eligible_indices.size == 0:
        raise ValueError("No households are eligible for microdata sampling")

    effective_fraction = 1.0 if sample_fraction == 0 else sample_fraction
    if min_households > 0:
        effective_fraction = max(
            effective_fraction,
            min(1.0, min_households / eligible_indices.size),
        )
    effective_fraction = min(1.0, effective_fraction)

    target_count = int(round(eligible_indices.size * effective_fraction))
    target_count = max(1, min(target_count, eligible_indices.size))
    if target_count == eligible_indices.size:
        return (
            eligible_indices,
            np.ones(eligible_indices.shape[0], dtype=float),
            int(household_ids.shape[0] - eligible_indices.size),
            int(eligible_indices.shape[0]),
        )

    def normalized(values: np.ndarray) -> np.ndarray:
        positive_values = values[(values > 0) & eligible_mask]
        if positive_values.size == 0:
            return np.zeros(values.shape[0], dtype=float)
        return values / np.mean(positive_values)

    size_measure = np.abs(household_weights) * (
        1 + normalized(household_social_security) + normalized(household_earnings)
    )
    size_measure = np.where(size_measure > 0, size_measure, 1)
    eligible_by_size = eligible_indices[
        np.argsort(size_measure[eligible_indices])[::-1]
    ]
    certainty_count = min(target_count, max(1, int(round(target_count * 0.5))))
    certainty_indices = np.sort(eligible_by_size[:certainty_count])
    remaining_pool = np.sort(eligible_by_size[certainty_count:])
    remaining_target = target_count - certainty_count

    selected_indices: list[np.ndarray] = []
    probabilities: list[np.ndarray] = []
    rng = np.random.default_rng(seed)

    def quantile_bins(values: np.ndarray, bin_count: int = 5) -> np.ndarray:
        bins = np.zeros(values.shape[0], dtype=int)
        eligible_values = np.asarray(values[eligible_indices], dtype=float)
        if np.all(eligible_values == eligible_values[0]):
            return bins
        edges = np.unique(
            np.quantile(
                eligible_values,
                np.linspace(0, 1, bin_count + 1)[1:-1],
            )
        )
        if edges.size == 0:
            return bins
        return np.searchsorted(edges, values, side="right")

    selected_indices.append(certainty_indices)
    probabilities.append(np.ones(certainty_indices.shape[0], dtype=float))

    if remaining_target == 0 or remaining_pool.size == 0:
        selected = np.concatenate(selected_indices)
        selection_probabilities = np.concatenate(probabilities)
        order = np.argsort(selected)
        return (
            selected[order],
            selection_probabilities[order],
            int(household_ids.shape[0] - eligible_indices.size),
            int(certainty_indices.shape[0]),
        )

    strata = pd.DataFrame(
        {
            "index": remaining_pool,
            "has_social_security": household_social_security[remaining_pool] > 0,
            "social_security_bin": quantile_bins(household_social_security)[
                remaining_pool
            ],
            "earnings_bin": quantile_bins(household_earnings)[remaining_pool],
        }
    )

    groups = [
        stratum["index"].to_numpy(dtype=int)
        for _, stratum in strata.groupby(
            ["has_social_security", "social_security_bin", "earnings_bin"],
            sort=True,
        )
    ]
    if remaining_target < len(groups):
        groups = [remaining_pool]

    raw_allocations = np.array(
        [remaining_target * group.size / remaining_pool.size for group in groups],
        dtype=float,
    )
    keep_counts = np.floor(raw_allocations).astype(int)
    keep_counts = np.minimum(keep_counts, np.array([group.size for group in groups]))
    nonempty = np.array([group.size > 0 for group in groups])
    keep_counts[(keep_counts == 0) & nonempty & (remaining_target >= len(groups))] = 1

    while keep_counts.sum() > remaining_target:
        reducible = np.flatnonzero(keep_counts > 1)
        if reducible.size == 0:
            break
        index = reducible[np.argmin(raw_allocations[reducible] % 1)]
        keep_counts[index] -= 1

    while keep_counts.sum() < remaining_target:
        room = np.flatnonzero(keep_counts < np.array([group.size for group in groups]))
        if room.size == 0:
            break
        index = room[np.argmax(raw_allocations[room] - keep_counts[room])]
        keep_counts[index] += 1

    for stratum_indices, keep_count in zip(groups, keep_counts):
        stratum_count = stratum_indices.size
        if keep_count <= 0:
            continue
        keep_count = min(int(keep_count), stratum_count)
        if keep_count == stratum_count:
            chosen = stratum_indices
        else:
            chosen = np.sort(
                rng.choice(stratum_indices, size=keep_count, replace=False)
            )
        selected_indices.append(chosen)
        probabilities.append(
            np.full(chosen.shape[0], keep_count / stratum_count, dtype=float)
        )

    selected = np.concatenate(selected_indices)
    selection_probabilities = np.concatenate(probabilities)
    order = np.argsort(selected)
    return (
        selected[order],
        selection_probabilities[order],
        int(household_ids.shape[0] - eligible_indices.size),
        int(certainty_indices.shape[0]),
    )


def _copy_attrs(source: Any, target: Any) -> None:
    for key, value in source.attrs.items():
        target.attrs[key] = value


def create_household_sampled_dataset(
    dataset_name: Any,
    *,
    year: int,
    sample_fraction: float,
    seed: int = 0,
    min_households: int = 0,
    drop_zero_weight_households: bool = True,
    output_dir: str | Path = "/tmp/crfb_microdata_samples",
) -> MicrodataSampleResult:
    """Create a deterministic, reweighted household sample HDF5 dataset."""
    import h5py

    source_path = _dataset_path(dataset_name)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_stat = source_path.stat()
    cache_key = "|".join(
        [
            "certainty-v1",
            str(source_path.resolve()),
            str(source_stat.st_mtime_ns),
            str(source_stat.st_size),
            str(year),
            f"{sample_fraction:.12g}",
            str(seed),
            str(min_households),
            str(drop_zero_weight_households),
        ]
    )
    cache_tag = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:12]
    output_path = output_dir / f"{source_path.stem}_sample_{cache_tag}.h5"
    metadata_path = Path(f"{output_path}.metadata.json")

    if output_path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))[
            "microdata_sample"
        ]
        return MicrodataSampleResult(str(output_path), metadata)

    with h5py.File(source_path, "r") as source:
        id_period = _first_existing_period(source["household_id"], str(year))
        household_ids = source["household_id"][id_period][:]
        household_weights = _float_array(source["household_weight"][id_period][:])
        person_household_ids = source["person_household_id"][id_period][:]
        household_social_security = _household_person_sum(
            source,
            period=id_period,
            household_ids=household_ids,
            person_household_ids=person_household_ids,
            variable_names=(
                "social_security_retirement",
                "social_security_disability",
                "social_security_survivors",
                "social_security_dependents",
            ),
        )
        household_earnings = _household_person_sum(
            source,
            period=id_period,
            household_ids=household_ids,
            person_household_ids=person_household_ids,
            variable_names=(
                "employment_income_before_lsr",
                "self_employment_income_before_lsr",
            ),
        )

        (
            selected_household_indices,
            selection_probabilities,
            dropped_households,
            certainty_households,
        ) = _sample_household_indices(
            household_ids=household_ids,
            household_weights=household_weights,
            household_social_security=household_social_security,
            household_earnings=household_earnings,
            sample_fraction=sample_fraction,
            seed=seed + year * 1_000_003,
            min_households=min_households,
            drop_zero_weight_households=drop_zero_weight_households,
        )
        selected_household_ids = household_ids[selected_household_indices]
        sampled_household_weights = (
            household_weights[selected_household_indices] / selection_probabilities
        )

        person_mask = np.isin(person_household_ids, selected_household_ids)
        selected_tax_unit_ids = np.unique(
            source["person_tax_unit_id"][id_period][:][person_mask]
        )
        selected_spm_unit_ids = np.unique(
            source["person_spm_unit_id"][id_period][:][person_mask]
        )
        selected_family_ids = np.unique(
            source["person_family_id"][id_period][:][person_mask]
        )
        selected_marital_unit_ids = np.unique(
            source["person_marital_unit_id"][id_period][:][person_mask]
        )

        masks_by_length: dict[int, np.ndarray] = {
            household_ids.shape[0]: np.isin(household_ids, selected_household_ids),
            person_household_ids.shape[0]: person_mask,
            source["tax_unit_id"][id_period].shape[0]: np.isin(
                source["tax_unit_id"][id_period][:],
                selected_tax_unit_ids,
            ),
            source["spm_unit_id"][id_period].shape[0]: np.isin(
                source["spm_unit_id"][id_period][:],
                selected_spm_unit_ids,
            ),
            source["family_id"][id_period].shape[0]: np.isin(
                source["family_id"][id_period][:],
                selected_family_ids,
            ),
            source["marital_unit_id"][id_period].shape[0]: np.isin(
                source["marital_unit_id"][id_period][:],
                selected_marital_unit_ids,
            ),
        }

        with h5py.File(output_path, "w") as target:
            _copy_attrs(source, target)
            for variable_name, source_group in source.items():
                target_group = target.create_group(variable_name)
                _copy_attrs(source_group, target_group)
                for period_name, source_dataset in source_group.items():
                    data = source_dataset[()]
                    mask = (
                        masks_by_length.get(source_dataset.shape[0])
                        if source_dataset.shape
                        else None
                    )
                    if mask is not None:
                        data = data[mask, ...]
                        if variable_name == "household_weight":
                            data = sampled_household_weights.astype(
                                source_dataset.dtype,
                                copy=False,
                            )
                    target_dataset = target_group.create_dataset(period_name, data=data)
                    _copy_attrs(source_dataset, target_dataset)

    source_metadata_path = Path(f"{source_path}.metadata.json")
    output_metadata = (
        json.loads(source_metadata_path.read_text(encoding="utf-8"))
        if source_metadata_path.exists()
        else {}
    )
    metadata = {
        "microdata_sample_active": True,
        "microdata_source_path": str(source_path),
        "microdata_sample_path": str(output_path),
        "microdata_sample_fraction": float(sample_fraction),
        "microdata_sample_seed": int(seed),
        "microdata_sample_min_households": int(min_households),
        "microdata_drop_zero_weight_households": bool(drop_zero_weight_households),
        "microdata_households_full": int(household_ids.shape[0]),
        "microdata_households_sampled": int(selected_household_indices.shape[0]),
        "microdata_certainty_households": int(certainty_households),
        "microdata_positive_weight_households_full": int(
            np.count_nonzero(household_weights != 0)
        ),
        "microdata_zero_weight_households_dropped": int(dropped_households),
        "microdata_effective_sample_fraction": float(
            selected_household_indices.shape[0]
            / max(1, household_ids.shape[0] - dropped_households)
        ),
    }
    output_metadata["microdata_sample"] = metadata
    metadata_path.write_text(
        json.dumps(output_metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return MicrodataSampleResult(str(output_path), metadata)


def maybe_create_household_sampled_dataset(
    dataset_name: Any,
    *,
    year: int,
    sample_fraction: float = 0,
    seed: int = 0,
    min_households: int = 0,
    drop_zero_weight_households: bool = False,
    output_dir: str | Path = "/tmp/crfb_microdata_samples",
) -> MicrodataSampleResult:
    if sample_fraction <= 0 and not drop_zero_weight_households:
        return MicrodataSampleResult(
            str(dataset_name),
            {"microdata_sample_active": False},
        )
    if sample_fraction >= 1 and not drop_zero_weight_households:
        return MicrodataSampleResult(
            str(dataset_name),
            {"microdata_sample_active": False},
        )
    return create_household_sampled_dataset(
        dataset_name,
        year=year,
        sample_fraction=sample_fraction,
        seed=seed,
        min_households=min_households,
        drop_zero_weight_households=drop_zero_weight_households,
        output_dir=output_dir,
    )


def compute_scenario_household_metrics(
    *,
    year: int,
    dataset_name: Any,
    reform: Any | None = None,
    progress_label: str | None = None,
) -> ScenarioHouseholdMetrics:
    metrics, _ = compute_scenario_household_metrics_and_aggregate(
        year=year,
        dataset_name=dataset_name,
        reform=reform,
        progress_label=progress_label,
    )
    return metrics


def compute_scenario_household_metrics_and_aggregate(
    *,
    year: int,
    dataset_name: Any,
    reform: Any | None = None,
    progress_label: str | None = None,
) -> tuple[ScenarioHouseholdMetrics, ScenarioAggregate]:
    metrics, aggregate, _ = compute_scenario_household_metrics_aggregate_and_raw_h5(
        year=year,
        dataset_name=dataset_name,
        reform=reform,
        progress_label=progress_label,
    )
    return metrics, aggregate


def compute_scenario_household_metrics_aggregate_and_raw_h5(
    *,
    year: int,
    dataset_name: Any,
    reform: Any | None = None,
    progress_label: str | None = None,
    raw_h5_output_path: str | Path | None = None,
) -> tuple[ScenarioHouseholdMetrics, ScenarioAggregate, dict[str, Any] | None]:
    dataset = _normalize_dataset(dataset_name)
    sim = dataset_microsimulation(dataset, reform=reform)

    def log_step(message: str) -> None:
        if progress_label:
            print(f"[metrics:{progress_label}] {message}", flush=True)

    def calculate_household_variable(*variable_names: str, simulation=sim):
        for variable_name in variable_names:
            if variable_name in simulation.tax_benefit_system.variables:
                return simulation.calculate(
                    variable_name,
                    map_to="household",
                    period=year,
                )
        variable_list = ", ".join(variable_names)
        raise ValueError(f"None of these variables exist: {variable_list}")

    log_step("household_id start")
    household_microseries = sim.calculate("household_id", map_to="household")
    household_ids = np.asarray(household_microseries.values)
    log_step(f"household_id done ({household_ids.shape[0]} households)")
    log_step("income_tax start")
    income_tax_microseries = sim.calculate(
        "income_tax", map_to="household", period=year
    )
    income_tax = _float_array(income_tax_microseries.values)
    log_step("income_tax done")
    log_step("tob_revenue_medicare_hi start")
    tob_medicare_hi_microseries = sim.calculate(
        "tob_revenue_medicare_hi",
        map_to="household",
        period=year,
    )
    tob_medicare_hi = _float_array(tob_medicare_hi_microseries.values)
    log_step("tob_revenue_medicare_hi done")
    log_step("tob_revenue_oasdi start")
    tob_oasdi_microseries = sim.calculate(
        "tob_revenue_oasdi",
        map_to="household",
        period=year,
    )
    tob_oasdi = _float_array(tob_oasdi_microseries.values)
    log_step("tob_revenue_oasdi done")
    log_step("social_security start")
    social_security_microseries = sim.calculate(
        "social_security",
        map_to="household",
        period=year,
    )
    social_security = _float_array(social_security_microseries.values)
    log_step("social_security done")
    log_step("taxable_payroll start")
    taxable_wages_microseries = calculate_household_variable(
        "taxable_wages_for_social_security",
        "taxable_earnings_for_social_security",
    )
    taxable_self_employment_microseries = calculate_household_variable(
        "taxable_self_employment_income_for_social_security",
        "social_security_taxable_self_employment_income",
    )
    taxable_wages = _float_array(taxable_wages_microseries.values)
    taxable_self_employment = _float_array(taxable_self_employment_microseries.values)
    taxable_payroll = taxable_wages + taxable_self_employment
    log_step("taxable_payroll done")
    log_step("employer_ss_tax_income_tax_revenue start")
    employer_ss_tax_revenue_microseries = sim.calculate(
        "employer_ss_tax_income_tax_revenue",
        map_to="household",
        period=year,
    )
    employer_ss_tax_revenue = _float_array(employer_ss_tax_revenue_microseries.values)
    log_step("employer_ss_tax_income_tax_revenue done")
    log_step("employer_medicare_tax_income_tax_revenue start")
    employer_medicare_tax_revenue_microseries = sim.calculate(
        "employer_medicare_tax_income_tax_revenue",
        map_to="household",
        period=year,
    )
    employer_medicare_tax_revenue = _float_array(
        employer_medicare_tax_revenue_microseries.values
    )
    log_step("employer_medicare_tax_income_tax_revenue done")

    raw_h5_metadata = None
    if raw_h5_output_path is not None:
        log_step(f"raw H5 save start ({raw_h5_output_path})")
        raw_h5_metadata = save_microsimulation_raw_h5(
            sim,
            raw_h5_output_path,
            year=year,
        )
        log_step("raw H5 save done")

    del sim, household_microseries

    metrics = ScenarioHouseholdMetrics(
        household_ids=household_ids,
        income_tax=income_tax,
        tob_medicare_hi=tob_medicare_hi,
        tob_oasdi=tob_oasdi,
        social_security=social_security,
        taxable_payroll=taxable_payroll,
        employer_ss_tax_revenue=employer_ss_tax_revenue,
        employer_medicare_tax_revenue=employer_medicare_tax_revenue,
        household_weight=_float_array(income_tax_microseries.weights.values),
    )
    tob_medicare_hi_total = float(tob_medicare_hi_microseries.sum())
    tob_oasdi_total = float(tob_oasdi_microseries.sum())
    aggregate = ScenarioAggregate(
        revenue=float(income_tax_microseries.sum()),
        tob_medicare_hi=tob_medicare_hi_total,
        tob_oasdi=tob_oasdi_total,
        tob_total=tob_oasdi_total + tob_medicare_hi_total,
        social_security=float(social_security_microseries.sum()),
        taxable_payroll=float(taxable_wages_microseries.sum())
        + float(taxable_self_employment_microseries.sum()),
        employer_ss_tax_revenue=float(employer_ss_tax_revenue_microseries.sum()),
        employer_medicare_tax_revenue=float(
            employer_medicare_tax_revenue_microseries.sum()
        ),
    )
    return metrics, aggregate, raw_h5_metadata


def compute_scenario_aggregate(
    *,
    year: int,
    dataset_name: Any,
    reform: Any | None = None,
    progress_label: str | None = None,
) -> ScenarioAggregate:
    _, aggregate = compute_scenario_household_metrics_and_aggregate(
        year=year,
        dataset_name=dataset_name,
        reform=reform,
        progress_label=progress_label,
    )
    return aggregate


def load_scenario_household_metrics(
    metrics_path: str | Path,
) -> ScenarioHouseholdMetrics:
    with np.load(Path(metrics_path), allow_pickle=False) as data:
        required = [
            "household_ids",
            "income_tax",
            "tob_medicare_hi",
            "tob_oasdi",
            "social_security",
            "taxable_payroll",
            "employer_ss_tax_revenue",
            "employer_medicare_tax_revenue",
        ]
        missing = [key for key in required if key not in data.files]
        if missing:
            raise KeyError(
                f"Metrics artifact {metrics_path} is missing: " + ", ".join(missing)
            )
        return ScenarioHouseholdMetrics(
            household_ids=np.asarray(data["household_ids"]),
            income_tax=_float_array(data["income_tax"]),
            tob_medicare_hi=_float_array(data["tob_medicare_hi"]),
            tob_oasdi=_float_array(data["tob_oasdi"]),
            social_security=_float_array(data["social_security"]),
            taxable_payroll=_float_array(data["taxable_payroll"]),
            employer_ss_tax_revenue=_float_array(data["employer_ss_tax_revenue"]),
            employer_medicare_tax_revenue=_float_array(
                data["employer_medicare_tax_revenue"]
            ),
            household_weight=(
                _float_array(data["household_weight"])
                if "household_weight" in data.files
                else None
            ),
        )


def subset_scenario_household_metrics(
    metrics: ScenarioHouseholdMetrics,
    household_ids: np.ndarray,
) -> ScenarioHouseholdMetrics:
    keep = np.isin(metrics.household_ids, np.asarray(household_ids))
    return ScenarioHouseholdMetrics(
        household_ids=metrics.household_ids[keep],
        income_tax=metrics.income_tax[keep],
        tob_medicare_hi=metrics.tob_medicare_hi[keep],
        tob_oasdi=metrics.tob_oasdi[keep],
        social_security=metrics.social_security[keep],
        taxable_payroll=metrics.taxable_payroll[keep],
        employer_ss_tax_revenue=metrics.employer_ss_tax_revenue[keep],
        employer_medicare_tax_revenue=metrics.employer_medicare_tax_revenue[keep],
        household_weight=(
            metrics.household_weight[keep]
            if metrics.household_weight is not None
            else None
        ),
    )


def get_reform_lookups(
    excluded_reforms: AbstractSet[str] = frozenset(),
) -> tuple[dict[str, Callable[[], Any]], dict[str, Callable[[], dict[str, Any]]]]:
    reform_functions = {
        reform_id: func
        for reform_id, func in STATIC_REFORM_FUNCTIONS.items()
        if reform_id not in excluded_reforms
    }
    behavioral_functions = {
        reform_id: func
        for reform_id, func in BEHAVIORAL_REFORM_FUNCTIONS.items()
        if reform_id not in excluded_reforms
    }
    return reform_functions, behavioral_functions


def load_baseline(
    year: int,
    dataset_name: Any,
    baseline_reform: Any | None = None,
    progress_label: str | None = None,
) -> BaselineResult:
    baseline_reform = _resolve_baseline_reform_for_dataset(
        year=year,
        dataset_name=dataset_name,
        baseline_reform=baseline_reform,
    )
    _, aggregate = compute_scenario_household_metrics_and_aggregate(
        year=year,
        dataset_name=dataset_name,
        reform=baseline_reform,
        progress_label=progress_label,
    )
    baseline = BaselineResult(
        revenue=aggregate.revenue,
        tob_medicare_hi=aggregate.tob_medicare_hi,
        tob_oasdi=aggregate.tob_oasdi,
        tob_total=aggregate.tob_total,
        social_security=aggregate.social_security,
        taxable_payroll=aggregate.taxable_payroll,
    )
    return _annotate_baseline_tax_assumption(
        baseline,
        year=year,
        dataset_name=dataset_name,
    )


def baseline_result_from_aggregate(
    aggregate: ScenarioAggregate,
    *,
    tax_assumption_name: str | None = None,
    tax_assumption_active: bool = False,
) -> BaselineResult:
    return BaselineResult(
        revenue=aggregate.revenue,
        tob_medicare_hi=aggregate.tob_medicare_hi,
        tob_oasdi=aggregate.tob_oasdi,
        tob_total=aggregate.tob_total,
        social_security=aggregate.social_security,
        taxable_payroll=aggregate.taxable_payroll,
        tax_assumption_name=tax_assumption_name,
        tax_assumption_active=tax_assumption_active,
    )


BASELINE_RECONCILIATION_TARGETS: dict[str, str] = {
    "ss_total": "social_security",
    "payroll_total": "taxable_payroll",
    "oasdi_tob": "tob_oasdi",
    "hi_tob": "tob_medicare_hi",
}


def _baseline_reconciliation_pct_error(
    actual: float,
    expected: float,
) -> float:
    if expected == 0:
        return 0.0 if actual == 0 else float("inf")
    return float(abs(actual - expected) / abs(expected) * 100)


def _metadata_path_for_dataset_name(dataset_name: Any) -> Path:
    dataset_file = _dataset_path(dataset_name)
    return Path(f"{dataset_file}.metadata.json")


def _year_from_metrics_or_dataset(metrics_path: str | Path, dataset_name: Any) -> int:
    metadata_path = _metadata_path_for_dataset_name(dataset_name)
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("year") is not None:
            return int(metadata["year"])

    dataset_file = _dataset_path(dataset_name)
    try:
        return int(dataset_file.stem)
    except ValueError:
        pass

    for part in Path(metrics_path).parts:
        if part.isdigit() and len(part) == 4:
            return int(part)

    raise ValueError(
        "Could not infer metrics year. Pass a dataset with metadata.year or "
        "a four-digit year in its path."
    )


def build_baseline_reconciliation_report(
    dataset_name: Any,
    baseline: BaselineResult,
) -> dict[str, Any]:
    metadata_path = _metadata_path_for_dataset_name(dataset_name)
    if not metadata_path.exists():
        return {
            "baseline_reconciliation_checked": False,
            "baseline_reconciliation_skip_reason": "dataset metadata missing",
        }

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    microdata_sample = metadata.get("microdata_sample", {})
    if microdata_sample.get("microdata_sample_active"):
        return {
            "baseline_reconciliation_checked": False,
            "baseline_reconciliation_skip_reason": "microdata sample",
        }

    constraints = metadata.get("calibration_audit", {}).get("constraints", {})
    entries: dict[str, dict[str, float]] = {}
    max_roundtrip_pct_error = 0.0

    for constraint_name, baseline_attr in BASELINE_RECONCILIATION_TARGETS.items():
        constraint = constraints.get(constraint_name)
        if not constraint:
            continue
        expected = constraint.get("achieved", constraint.get("target"))
        target = constraint.get("target")
        if expected is None:
            continue
        scored = float(getattr(baseline, baseline_attr))
        expected = float(expected)
        roundtrip_pct_error = _baseline_reconciliation_pct_error(scored, expected)
        target_pct_error = (
            _baseline_reconciliation_pct_error(scored, float(target))
            if target is not None
            else 0.0
        )
        entries[constraint_name] = {
            "scored": scored,
            "expected": expected,
            "target": float(target) if target is not None else expected,
            "roundtrip_pct_error": roundtrip_pct_error,
            "target_pct_error": target_pct_error,
        }
        max_roundtrip_pct_error = max(
            max_roundtrip_pct_error,
            roundtrip_pct_error,
        )

    if not entries:
        return {
            "baseline_reconciliation_checked": False,
            "baseline_reconciliation_skip_reason": "no comparable constraints",
        }

    return {
        "baseline_reconciliation_checked": True,
        "baseline_reconciliation_max_pct_error": max_roundtrip_pct_error,
        "baseline_reconciliation": entries,
    }


def validate_baseline_reconciliation(
    dataset_name: Any,
    baseline: BaselineResult,
    *,
    max_roundtrip_pct_error: float = 1.0,
) -> dict[str, Any]:
    report = build_baseline_reconciliation_report(dataset_name, baseline)
    if not report.get("baseline_reconciliation_checked"):
        return report

    failures = [
        f"{name}={entry['roundtrip_pct_error']:.6f}%"
        for name, entry in report["baseline_reconciliation"].items()
        if entry["roundtrip_pct_error"] > max_roundtrip_pct_error
    ]
    if failures:
        raise ValueError(
            "Baseline scored-vs-calibrated reconciliation failed for "
            f"{_dataset_path(dataset_name)}: "
            + ", ".join(failures)
            + f" exceeds {max_roundtrip_pct_error:.6f}%."
        )

    return report


def load_baseline_from_metrics(
    metrics_path: str | Path,
    *,
    dataset_name: Any | None = None,
) -> BaselineResult:
    del metrics_path, dataset_name
    raise RuntimeError(
        "Baseline metrics artifacts contain unweighted arrays and must not be "
        "re-aggregated with raw household weights. Recompute or load a saved "
        "aggregate produced by MicroSeries.sum()."
    )


def build_reform(
    reform_id: str,
    scoring_type: str,
    reform_functions: dict[str, Callable[[], Any]],
    behavioral_functions: dict[str, Callable[[], Any]],
) -> Any:
    if scoring_type == "static":
        reform_func = reform_functions.get(reform_id)
        if reform_func is None:
            raise KeyError(f"Unknown reform: {reform_id}")
        return reform_func()

    if scoring_type == "behavioral":
        behavioral_func = behavioral_functions.get(reform_id)
        if behavioral_func is None:
            raise KeyError(f"No behavioral reform for: {reform_id}")
        reform_definition = behavioral_func()
        if isinstance(reform_definition, dict):
            return Reform.from_dict(reform_definition, country_id="us")
        return reform_definition

    raise ValueError(f"Invalid scoring type: {scoring_type}")


def _default_net_impacts(
    tob_oasdi_impact: float,
    tob_medicare_impact: float,
    default_net_impact_mode: str,
) -> dict[str, float]:
    if default_net_impact_mode == "direct":
        oasdi_net = tob_oasdi_impact
        hi_net = tob_medicare_impact
    else:
        oasdi_net = 0.0
        hi_net = 0.0

    return {
        "employer_ss_tax_revenue": 0.0,
        "employer_medicare_tax_revenue": 0.0,
        "oasdi_gain": 0.0,
        "hi_gain": 0.0,
        "oasdi_loss": 0.0,
        "hi_loss": 0.0,
        "oasdi_net_impact": oasdi_net,
        "hi_net_impact": hi_net,
    }


def _calculate_option6_gains(
    year: int,
    employer_ss_revenue: float,
    employer_medicare_revenue: float,
) -> tuple[float, float]:
    if year >= 2033:
        return employer_ss_revenue, employer_medicare_revenue

    rate = OPTION6_PHASE_IN_RATES.get(year, 1.0)
    total_percentage_points = rate * 7.65
    total_gain = employer_ss_revenue + employer_medicare_revenue

    if total_percentage_points <= 6.2:
        return total_gain, 0.0

    oasdi_share = 6.2 / total_percentage_points
    return total_gain * oasdi_share, total_gain * (1 - oasdi_share)


def calculate_employer_net_impacts_from_aggregates(
    reform_id: str,
    year: int,
    reform_totals: ScenarioAggregate,
    baseline: BaselineResult,
    employer_net_reforms: AbstractSet[str],
    default_net_impact_mode: str = "zero",
) -> dict[str, float]:
    impacts = _default_net_impacts(
        tob_oasdi_impact=reform_totals.tob_oasdi - baseline.tob_oasdi,
        tob_medicare_impact=reform_totals.tob_medicare_hi - baseline.tob_medicare_hi,
        default_net_impact_mode=default_net_impact_mode,
    )

    if reform_id not in employer_net_reforms:
        return impacts

    employer_ss_revenue = reform_totals.employer_ss_tax_revenue
    employer_medicare_revenue = reform_totals.employer_medicare_tax_revenue

    if reform_id in {"option5", "option12"}:
        oasdi_gain = employer_ss_revenue
        hi_gain = employer_medicare_revenue
    else:
        oasdi_gain, hi_gain = _calculate_option6_gains(
            year,
            employer_ss_revenue,
            employer_medicare_revenue,
        )

    oasdi_loss = baseline.tob_oasdi - reform_totals.tob_oasdi
    hi_loss = baseline.tob_medicare_hi - reform_totals.tob_medicare_hi

    return {
        "employer_ss_tax_revenue": employer_ss_revenue,
        "employer_medicare_tax_revenue": employer_medicare_revenue,
        "oasdi_gain": oasdi_gain,
        "hi_gain": hi_gain,
        "oasdi_loss": oasdi_loss,
        "hi_loss": hi_loss,
        "oasdi_net_impact": oasdi_gain - oasdi_loss,
        "hi_net_impact": hi_gain - hi_loss,
    }


def build_reform_result_from_aggregates(
    *,
    reform_id: str,
    year: int,
    baseline: BaselineResult,
    reform_totals: ScenarioAggregate,
    employer_net_reforms: AbstractSet[str],
    default_net_impact_mode: str = "zero",
    scoring_type: str = "static",
) -> dict[str, float | int | str]:
    revenue_impact = reform_totals.revenue - baseline.revenue
    tob_medicare_impact = reform_totals.tob_medicare_hi - baseline.tob_medicare_hi
    tob_oasdi_impact = reform_totals.tob_oasdi - baseline.tob_oasdi
    tob_total_impact = reform_totals.tob_total - baseline.tob_total

    allocation_impacts = calculate_employer_net_impacts_from_aggregates(
        reform_id=reform_id,
        year=year,
        reform_totals=reform_totals,
        baseline=baseline,
        employer_net_reforms=employer_net_reforms,
        default_net_impact_mode=default_net_impact_mode,
    )

    return {
        "reform_name": reform_id,
        "year": year,
        "baseline_tax_assumption_name": baseline.tax_assumption_name or "",
        "baseline_tax_assumption_active": baseline.tax_assumption_active,
        "baseline_revenue": baseline.revenue,
        "reform_revenue": reform_totals.revenue,
        "revenue_impact": revenue_impact,
        "baseline_tob_medicare_hi": baseline.tob_medicare_hi,
        "reform_tob_medicare_hi": reform_totals.tob_medicare_hi,
        "tob_medicare_hi_impact": tob_medicare_impact,
        "baseline_tob_oasdi": baseline.tob_oasdi,
        "reform_tob_oasdi": reform_totals.tob_oasdi,
        "tob_oasdi_impact": tob_oasdi_impact,
        "baseline_tob_total": baseline.tob_total,
        "reform_tob_total": reform_totals.tob_total,
        "tob_total_impact": tob_total_impact,
        "scoring_type": scoring_type,
        **allocation_impacts,
    }


def compute_reform_result(
    reform_id: str,
    year: int,
    scoring_type: str,
    dataset_name: Any,
    baseline: BaselineResult,
    reform_functions: dict[str, Callable[[], Any]],
    behavioral_functions: dict[str, Callable[[], dict[str, Any]]],
    employer_net_reforms: AbstractSet[str],
    default_net_impact_mode: str = "zero",
    baseline_reform: Any | None = None,
    progress_label: str | None = None,
    metrics_output_path: str | Path | None = None,
    raw_h5_output_path: str | Path | None = None,
    baseline_metrics: ScenarioHouseholdMetrics | None = None,
    metric_change_tolerance: float = 1e-9,
) -> dict[str, float | int | str]:
    baseline_reform = _resolve_baseline_reform_for_dataset(
        year=year,
        dataset_name=dataset_name,
        baseline_reform=baseline_reform,
    )
    _validate_baseline_tax_assumption(
        baseline,
        year=year,
        dataset_name=dataset_name,
    )
    reform = build_reform(
        reform_id, scoring_type, reform_functions, behavioral_functions
    )
    combined_reform = (
        (baseline_reform, reform) if baseline_reform is not None else reform
    )
    if raw_h5_output_path is None:
        metrics, reform_totals = compute_scenario_household_metrics_and_aggregate(
            year=year,
            dataset_name=dataset_name,
            reform=combined_reform,
            progress_label=progress_label,
        )
        raw_h5_metadata = None
    else:
        metrics, reform_totals, raw_h5_metadata = (
            compute_scenario_household_metrics_aggregate_and_raw_h5(
                year=year,
                dataset_name=dataset_name,
                reform=combined_reform,
                progress_label=progress_label,
                raw_h5_output_path=raw_h5_output_path,
            )
        )
    result = build_reform_result_from_aggregates(
        reform_id=reform_id,
        year=year,
        baseline=baseline,
        reform_totals=reform_totals,
        employer_net_reforms=employer_net_reforms,
        default_net_impact_mode=default_net_impact_mode,
        scoring_type=scoring_type,
    )
    if metrics_output_path is not None:
        if baseline_metrics is None:
            metric_artifact = {
                "artifact_type": "scenario_household_metrics",
                "changed_metric_variables": list(SCENARIO_HOUSEHOLD_VALUE_VARIABLES),
                "unchanged_metric_variables": [],
                "saved_arrays": list(scenario_household_metrics_arrays(metrics)),
            }
            save_scenario_household_metrics(metrics, metrics_output_path)
        else:
            metric_artifact = save_reform_household_metric_changes(
                baseline_metrics=baseline_metrics,
                reform_metrics=metrics,
                metrics_path=metrics_output_path,
                tolerance=metric_change_tolerance,
            )
        result.update(
            {
                "reform_household_metrics_artifact_type": metric_artifact[
                    "artifact_type"
                ],
                "reform_household_metrics_changed_variables": ",".join(
                    metric_artifact["changed_metric_variables"]
                ),
                "reform_household_metrics_unchanged_variables": ",".join(
                    metric_artifact["unchanged_metric_variables"]
                ),
                "reform_household_metrics_saved_arrays": ",".join(
                    metric_artifact["saved_arrays"]
                ),
            }
        )
    if raw_h5_output_path is not None:
        if raw_h5_metadata is None:
            raise RuntimeError(
                f"Raw reform H5 was requested but not saved: {raw_h5_output_path}"
            )
        result.update(
            {
                "reform_raw_h5_saved": True,
                "reform_raw_h5_path": str(raw_h5_output_path),
                "reform_raw_h5_size_bytes": raw_h5_metadata["size_bytes"],
                "reform_raw_h5_entity_count": raw_h5_metadata["entity_count"],
                "reform_raw_h5_variable_count": raw_h5_metadata["variable_count"],
                "reform_raw_h5_artifact_type": raw_h5_metadata["artifact_type"],
            }
        )
    del reform

    return result


def _materialize_raw_h5_variables(
    sim: Any,
    *,
    year: int,
    variable_names: tuple[str, ...] = DEFAULT_REFORM_RAW_H5_MATERIALIZE_VARIABLES,
    progress_label: str | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    materialized: list[str] = []
    skipped: list[dict[str, str]] = []

    def log_step(message: str) -> None:
        if progress_label:
            print(f"[raw-h5:{progress_label}] {message}", flush=True)

    available = sim.tax_benefit_system.variables
    for variable_name in variable_names:
        if variable_name not in available:
            skipped.append({"variable": variable_name, "reason": "missing"})
            continue
        log_step(f"{variable_name} start")
        try:
            sim.calculate(variable_name, period=year)
        except Exception as period_error:
            try:
                sim.calculate(variable_name)
            except Exception as fallback_error:
                skipped.append(
                    {
                        "variable": variable_name,
                        "reason": (
                            f"period={type(period_error).__name__}: "
                            f"{str(period_error)[:160]}; "
                            f"fallback={type(fallback_error).__name__}: "
                            f"{str(fallback_error)[:160]}"
                        ),
                    }
                )
                log_step(f"{variable_name} skipped")
                continue
        materialized.append(variable_name)
        log_step(f"{variable_name} done")

    return materialized, skipped


def save_reform_raw_h5_only(
    *,
    reform_id: str,
    year: int,
    scoring_type: str,
    dataset_name: Any,
    reform_functions: dict[str, Callable[[], Any]],
    behavioral_functions: dict[str, Callable[[], dict[str, Any]]],
    raw_h5_output_path: str | Path,
    baseline_reform: Any | None = None,
    progress_label: str | None = None,
    materialize_variables: tuple[
        str, ...
    ] = DEFAULT_REFORM_RAW_H5_MATERIALIZE_VARIABLES,
) -> dict[str, Any]:
    baseline_reform = _resolve_baseline_reform_for_dataset(
        year=year,
        dataset_name=dataset_name,
        baseline_reform=baseline_reform,
    )
    reform = build_reform(
        reform_id,
        scoring_type,
        reform_functions,
        behavioral_functions,
    )
    combined_reform = (
        (baseline_reform, reform) if baseline_reform is not None else reform
    )
    dataset = _normalize_dataset(dataset_name)
    sim = dataset_microsimulation(dataset, reform=combined_reform)
    materialized, skipped = _materialize_raw_h5_variables(
        sim,
        year=year,
        variable_names=materialize_variables,
        progress_label=progress_label,
    )
    if not materialized:
        raise RuntimeError(
            f"No variables materialized before raw H5 save for {reform_id} {year}."
        )
    metadata = save_microsimulation_raw_h5(
        sim,
        raw_h5_output_path,
        year=year,
    )
    metadata.update(
        {
            "reform_id": reform_id,
            "scoring_type": scoring_type,
            "materialization_policy": "explicit_crfb_reform_raw_h5_variables",
            "requested_materialized_variables": list(materialize_variables),
            "materialized_variables": materialized,
            "skipped_materialized_variables": skipped,
            "baseline_aggregate_metrics_computed": False,
            "baseline_reconciliation_computed": False,
        }
    )
    del sim, reform
    return metadata
