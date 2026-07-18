from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HI_EXPENDITURES = REPO_ROOT / "data" / "hi_expenditures_tr2026.csv"


def get_hi_data(path: str | Path = DEFAULT_HI_EXPENDITURES) -> pd.DataFrame:
    """Load Medicare HI expenditures in the legacy balanced-fix schema.

    The file stores ``cost_rate`` as a decimal and payroll/expenditures in
    nominal dollars. Callers should index by year explicitly so missing years
    fail loudly instead of falling through to an old vintage.
    """

    frame = pd.read_csv(path)
    required = {"year", "cost_rate", "hi_taxable_payroll", "hi_expenditures"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"HI expenditures file missing columns: {sorted(missing)}")
    columns = ["year", "cost_rate", "hi_taxable_payroll", "hi_expenditures"]
    frame = frame[columns].copy()
    frame["year"] = frame["year"].astype(int)
    for column in ["cost_rate", "hi_taxable_payroll", "hi_expenditures"]:
        frame[column] = frame[column].astype(float)
    if frame["year"].duplicated().any():
        duplicated = sorted(frame.loc[frame["year"].duplicated(), "year"].unique())
        raise ValueError(f"HI expenditures file has duplicate years: {duplicated}")
    return frame.sort_values("year").reset_index(drop=True)


def hi_expenditures_for_year(
    year: int,
    *,
    path: str | Path = DEFAULT_HI_EXPENDITURES,
) -> dict[str, float]:
    frame = get_hi_data(path).set_index("year")
    if int(year) not in frame.index:
        raise KeyError(f"HI expenditures file has no year {year}.")
    row = frame.loc[int(year)]
    return {
        "cost_rate": float(row["cost_rate"]),
        "hi_taxable_payroll": float(row["hi_taxable_payroll"]),
        "hi_expenditures": float(row["hi_expenditures"]),
    }
