from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from policyengine_us import Microsimulation


DEFAULT_VARIABLES = [
    "employment_income",
    "employment_income_before_lsr",
    "self_employment_income",
    "self_employment_income_before_lsr",
    "partnership_s_corp_income",
    "partnership_se_income",
    "sstb_self_employment_income_before_lsr",
    "farm_operations_income",
    "qualified_dividend_income",
    "long_term_capital_gains",
    "long_term_capital_gains_before_response",
    "taxable_interest_income",
    "taxable_private_pension_income",
    "taxable_ira_distributions",
    "taxable_401k_distributions",
    "social_security",
    "taxable_social_security",
    "income_tax",
]


def _as_float_array(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def _series_stats(sim: Microsimulation, variable: str, year: int) -> dict[str, object]:
    series = sim.calculate(variable, period=year)
    values = _as_float_array(series.values)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raw_min = raw_max = nonzero_count = None
    else:
        raw_min = float(finite.min())
        raw_max = float(finite.max())
        nonzero_count = int(np.count_nonzero(np.abs(finite) > 1e-9))

    return {
        "variable": variable,
        "weighted_sum": float(series.sum()),
        "raw_min": raw_min,
        "raw_max": raw_max,
        "nonzero_count": nonzero_count,
        "row_count": int(values.size),
    }


def audit_h5(path: Path, year: int, variables: list[str]) -> list[dict[str, object]]:
    sim = Microsimulation(dataset=str(path))
    rows: list[dict[str, object]] = []
    for variable in variables:
        if variable not in sim.tax_benefit_system.variables:
            rows.append(
                {
                    "variable": variable,
                    "error": "missing_from_policyengine_us",
                }
            )
            continue
        try:
            rows.append(_series_stats(sim, variable, year))
        except Exception as exc:  # pragma: no cover - diagnostic script
            rows.append({"variable": variable, "error": repr(exc)})
    return rows


def write_outputs(rows: list[dict[str, object]], csv_path: Path, json_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "variable",
        "weighted_sum",
        "weighted_sum_billions",
        "weighted_sum_trillions",
        "raw_min",
        "raw_max",
        "nonzero_count",
        "row_count",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            weighted_sum = out.get("weighted_sum")
            if isinstance(weighted_sum, (int, float)):
                out["weighted_sum_billions"] = weighted_sum / 1e9
                out["weighted_sum_trillions"] = weighted_sum / 1e12
            writer.writerow({column: out.get(column, "") for column in columns})

    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")


def _row_by_variable(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row["variable"]): row for row in rows}


def _weighted_sum(row: dict[str, object]) -> float | None:
    value = row.get("weighted_sum")
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return None
    return float(value)


def validation_failures(
    rows: list[dict[str, object]],
    *,
    max_partnership_abs: float,
    max_sstb_self_employment_ratio: float,
) -> list[str]:
    failures: list[str] = []
    rows_by_variable = _row_by_variable(rows)

    for row in rows:
        variable = str(row["variable"])
        if row.get("error"):
            failures.append(f"{variable}: {row['error']}")
            continue
        for field in ("weighted_sum", "raw_min", "raw_max"):
            value = row.get(field)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                failures.append(f"{variable}: non-finite {field}={value!r}")

    partnership = _weighted_sum(rows_by_variable.get("partnership_s_corp_income", {}))
    if partnership is None:
        failures.append("partnership_s_corp_income: missing weighted sum")
    elif abs(partnership) > max_partnership_abs:
        failures.append(
            "partnership_s_corp_income: "
            f"weighted sum ${partnership / 1e12:,.3f}T exceeds "
            f"${max_partnership_abs / 1e12:,.3f}T gate"
        )

    sstb = _weighted_sum(
        rows_by_variable.get("sstb_self_employment_income_before_lsr", {})
    )
    self_employment = _weighted_sum(
        rows_by_variable.get("self_employment_income_before_lsr", {})
    )
    if sstb is None:
        failures.append("sstb_self_employment_income_before_lsr: missing weighted sum")
    elif self_employment is None:
        failures.append("self_employment_income_before_lsr: missing weighted sum")
    else:
        denominator = max(abs(self_employment), 1.0)
        ratio = abs(sstb) / denominator
        if ratio > max_sstb_self_employment_ratio:
            failures.append(
                "sstb_self_employment_income_before_lsr: "
                f"${sstb / 1e12:,.3f}T is {ratio:,.1f}x "
                "self_employment_income_before_lsr, exceeding "
                f"{max_sstb_self_employment_ratio:,.1f}x gate"
            )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit CRFB long-run H5 business-income aggregates and maxima."
    )
    parser.add_argument("h5", type=Path)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument(
        "--variables",
        default=",".join(DEFAULT_VARIABLES),
        help="Comma-separated variable list.",
    )
    parser.add_argument(
        "--max-partnership-abs",
        type=float,
        default=50e12,
        help=(
            "Fail if abs(weighted partnership_s_corp_income) exceeds this "
            "dollar amount."
        ),
    )
    parser.add_argument(
        "--max-sstb-self-employment-ratio",
        type=float,
        default=2.0,
        help=(
            "Fail if abs(SSTB self-employment income before LSR) exceeds this "
            "multiple of abs(total self-employment income before LSR)."
        ),
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Write diagnostics but return success even when validation gates fail.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    variables = [item.strip() for item in args.variables.split(",") if item.strip()]
    rows = audit_h5(args.h5.expanduser().resolve(), args.year, variables)
    write_outputs(rows, args.csv.expanduser().resolve(), args.json.expanduser().resolve())
    for row in rows:
        if row.get("error"):
            print(f"{row['variable']}: {row['error']}")
            continue
        print(
            f"{row['variable']}: "
            f"weighted=${row['weighted_sum'] / 1e12:,.3f}T, "
            f"raw_max=${row['raw_max']:,.0f}"
        )
    failures = validation_failures(
        rows,
        max_partnership_abs=args.max_partnership_abs,
        max_sstb_self_employment_ratio=args.max_sstb_self_employment_ratio,
    )
    if failures:
        print("Validation failures:")
        for failure in failures:
            print(f"- {failure}")
        return 0 if args.no_fail else 1
    print("Validation gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
