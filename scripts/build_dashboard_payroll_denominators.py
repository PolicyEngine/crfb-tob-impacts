from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RAW_HI = REPO / "data" / "hi_expenditures_tr2025.csv"
RAW_SSA = REPO / "data" / "ssa_economic_projections.csv"
DASHBOARD_HI = REPO / "dashboard" / "public" / "data" / "hi_taxable_payroll.csv"
DASHBOARD_SSA = REPO / "dashboard" / "public" / "data" / "ssa_economic_projections.csv"
START_YEAR = 2026
END_YEAR = 2100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dashboard payroll denominator CSVs for percent-payroll views."
    )
    parser.add_argument("--raw-hi", type=Path, default=RAW_HI)
    parser.add_argument("--raw-ssa", type=Path, default=RAW_SSA)
    parser.add_argument("--dashboard-hi", type=Path, default=DASHBOARD_HI)
    parser.add_argument("--dashboard-ssa", type=Path, default=DASHBOARD_SSA)
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    return parser.parse_args()


def build_hi_payroll(
    *,
    raw_hi_path: Path,
    existing_dashboard_path: Path,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    raw = pd.read_csv(raw_hi_path, usecols=["year", "hi_taxable_payroll"])
    raw["year"] = raw["year"].astype(int)
    raw["hi_taxable_payroll"] = raw["hi_taxable_payroll"].astype(float) / 1e9
    raw = raw.sort_values("year").reset_index(drop=True)

    if len(raw) < 2:
        raise ValueError(
            "Need at least two raw HI payroll rows to extrapolate endpoints."
        )

    raw_start = int(raw["year"].min())
    raw_end = int(raw["year"].max())

    existing = pd.read_csv(existing_dashboard_path)
    existing["year"] = existing["year"].astype(int)
    bridge = existing.loc[
        (existing["year"] >= start_year) & (existing["year"] < raw_start),
        ["year", "hi_taxable_payroll"],
    ].copy()

    raw_window = raw.loc[
        (raw["year"] >= start_year) & (raw["year"] <= min(raw_end, end_year)),
        ["year", "hi_taxable_payroll"],
    ].copy()

    rows = [bridge, raw_window]
    if raw_end < end_year:
        previous = raw.iloc[-2:]
        growth = (
            previous["hi_taxable_payroll"].iloc[-1]
            / previous["hi_taxable_payroll"].iloc[-2]
        )
        extrapolated: list[dict[str, float | int]] = []
        value = previous["hi_taxable_payroll"].iloc[-1]
        for year in range(raw_end + 1, end_year + 1):
            value *= growth
            extrapolated.append({"year": year, "hi_taxable_payroll": value})
        rows.append(pd.DataFrame(extrapolated))

    output = (
        pd.concat(rows, ignore_index=True)
        .sort_values("year")
        .drop_duplicates("year", keep="last")
        .reset_index(drop=True)
    )
    expected_years = set(range(start_year, end_year + 1))
    missing = sorted(expected_years - set(output["year"]))
    if missing:
        raise ValueError(
            "Missing HI taxable payroll years: " + ", ".join(map(str, missing))
        )
    return output


def main() -> int:
    args = parse_args()
    args.dashboard_hi.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_ssa.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(args.raw_ssa, args.dashboard_ssa)

    hi_payroll = build_hi_payroll(
        raw_hi_path=args.raw_hi,
        existing_dashboard_path=args.dashboard_hi,
        start_year=args.start_year,
        end_year=args.end_year,
    )
    hi_payroll.to_csv(args.dashboard_hi, index=False, float_format="%.6f")

    print(f"Wrote {args.dashboard_ssa}")
    print(f"Wrote {args.dashboard_hi}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
