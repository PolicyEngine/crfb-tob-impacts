"""Build the per-trust-fund effective interest rate series for PV discounting.

CRFB asked that present values use the Trustees' *effective* interest rates on
each trust fund rather than a single assumed nominal series (the prior
``tr2026_interest_rates.csv`` matched the high-cost alternative's nominal
rates, not the intermediate assumptions).

Sources (both under ``data/sources/tr2026/``; see the sources manifest):

- OASDI: Table VI.G1 of the 2026 OASDI Trustees Report single-year tables
  (``SingleYearTRTables_TR2026.xlsx``), "Compound effective trust fund interest
  factor" column, intermediate alternative. Footnote c: the reciprocals of the
  factors are the discounting/accumulation factors SSA uses for summarized
  rates and balances. The annual effective rate for year y is
  ``factor[y] / factor[y - 1] - 1``.
- HI: Table IV.A4 of the 2026 Medicare Trustees Report, "HI effective interest
  rate" column, intermediate estimates, 2026-2035 (transcribed in
  ``hi_effective_interest_rates_tr2026_iv_a4.csv``). Per the table's footnote,
  rates then grade linearly to the ultimate nominal assumption (4.7 percent)
  by year 15 (2040) and hold at 4.7 percent afterward.

Output: ``dashboard/public/data/effective_interest_rates.csv`` with columns
``year, oasdi_effective_rate_pct, hi_effective_rate_pct`` for 2026-2100.
"""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parents[1]
WORKBOOK = REPO / "data" / "sources" / "tr2026" / "SingleYearTRTables_TR2026.xlsx"
HI_SOURCE = (
    REPO / "data" / "sources" / "tr2026" / "hi_effective_interest_rates_tr2026_iv_a4.csv"
)
OUTPUT = REPO / "dashboard" / "public" / "data" / "effective_interest_rates.csv"

YEAR_START = 2026
YEAR_END = 2100
HI_ULTIMATE_PCT = 4.7
HI_ULTIMATE_YEAR = 2040  # "grade to the ultimate nominal ... by year 15"


def oasdi_effective_rates() -> dict[int, float]:
    """Annual effective OASDI rates from the VI.G1 intermediate factor series."""
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True)
    ws = wb["VI.G1"]
    rows = list(ws.iter_rows(values_only=True))

    # The sheet stacks Historical / Intermediate / Low-cost / High-cost blocks;
    # scenario labels sit in column A. Collect (year, factor) rows between the
    # "Historical data:" and "Low-cost:" labels — historical flows straight
    # into the intermediate projection with no year reset.
    factors: dict[int, float] = {}
    active = False
    for row in rows:
        label = row[0]
        if isinstance(label, str):
            if label.startswith("Historical data") or label.startswith("Intermediate"):
                active = True
                continue
            if label.startswith("Low-cost") or label.startswith("High-cost"):
                active = False
                continue
        if active and isinstance(label, (int, float)) and isinstance(row[6], (int, float)):
            factors[int(label)] = float(row[6])

    missing = [y for y in range(YEAR_START - 1, YEAR_END + 1) if y not in factors]
    if missing:
        raise RuntimeError(f"VI.G1 intermediate factors missing years: {missing[:5]}")

    return {
        year: (factors[year] / factors[year - 1] - 1.0) * 100.0
        for year in range(YEAR_START, YEAR_END + 1)
    }


def hi_effective_rates() -> dict[int, float]:
    """HI effective rates: IV.A4 through 2035, grade to 4.7% by 2040, then flat."""
    published: dict[int, float] = {}
    with HI_SOURCE.open() as file:
        for row in csv.DictReader(
            line for line in file if not line.startswith("#")
        ):
            published[int(row["year"])] = float(row["hi_effective_interest_rate_pct"])

    if min(published) != YEAR_START:
        raise RuntimeError("IV.A4 source must start at 2026.")
    last_published = max(published)

    rates = dict(published)
    grade_years = HI_ULTIMATE_YEAR - last_published
    for step in range(1, grade_years + 1):
        year = last_published + step
        rates[year] = published[last_published] + (
            HI_ULTIMATE_PCT - published[last_published]
        ) * (step / grade_years)
    for year in range(HI_ULTIMATE_YEAR + 1, YEAR_END + 1):
        rates[year] = HI_ULTIMATE_PCT
    return rates


def main() -> int:
    oasdi = oasdi_effective_rates()
    hi = hi_effective_rates()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["year", "oasdi_effective_rate_pct", "hi_effective_rate_pct"])
        for year in range(YEAR_START, YEAR_END + 1):
            writer.writerow([year, f"{oasdi[year]:.4f}", f"{hi[year]:.4f}"])
    print(f"wrote {OUTPUT} ({YEAR_END - YEAR_START + 1} years)")
    print(
        "  OASDI: "
        + ", ".join(f"{y}={oasdi[y]:.2f}%" for y in (2026, 2030, 2040, 2060, 2100))
    )
    print(
        "  HI:    "
        + ", ".join(f"{y}={hi[y]:.2f}%" for y in (2026, 2030, 2040, 2060, 2100))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
