from __future__ import annotations

from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
DASHBOARD_DATA = REPO / "dashboard" / "public" / "data"
STATIC = RESULTS / "all_static_results_full_h5_selected_panel_display_20260522.csv"
OASDI_PAYROLL = DASHBOARD_DATA / "ssa_economic_projections.csv"
HI_PAYROLL = DASHBOARD_DATA / "hi_taxable_payroll.csv"
OUT_CSV = RESULTS / "late_horizon_discontinuity_audit_20260430.csv"
OUT_MD = REPO / "docs" / "current" / "late-horizon-discontinuity-audit.md"

FOCUS_TRANSITIONS = {(2049, 2050), (2074, 2075), (2099, 2100)}
PUBLICATION_REFORMS = {
    "option1",
    "option2",
    "option3",
    "option4",
    "option5",
    "option7",
    "option8",
    "option9",
    "option10",
    "option11",
    "option12",
    "option13",
    "option14_stacked",
}


def fmt_pp(value: float) -> str:
    return f"{value:+.3f}"


def fmt_b(value: float) -> str:
    return f"{value:+,.1f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def load_inputs() -> pd.DataFrame:
    static = pd.read_csv(STATIC)
    static = static[static["reform_name"].isin(PUBLICATION_REFORMS)].copy()
    oasdi = pd.read_csv(OASDI_PAYROLL)[["year", "taxable_payroll", "gdp"]]
    hi = pd.read_csv(HI_PAYROLL)[["year", "hi_taxable_payroll"]]

    df = static.merge(oasdi, on="year", how="left").merge(hi, on="year", how="left")
    df["total_pct_payroll"] = df["revenue_impact"] / df["taxable_payroll"] * 100
    df["oasdi_pct_payroll"] = df["oasdi_net_impact"] / df["taxable_payroll"] * 100
    df["hi_pct_payroll"] = df["hi_net_impact"] / df["hi_taxable_payroll"] * 100
    df["total_pct_gdp"] = df["revenue_impact"] / df["gdp"] * 100
    return df.sort_values(["reform_name", "year"]).reset_index(drop=True)


def build_transition_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    by_reform = {reform: group.set_index("year") for reform, group in df.groupby("reform_name")}

    for reform, group in by_reform.items():
        for from_year in range(2026, 2100):
            to_year = from_year + 1
            if from_year not in group.index or to_year not in group.index:
                continue

            prev = group.loc[from_year]
            curr = group.loc[to_year]
            delta_total_pct = curr["total_pct_payroll"] - prev["total_pct_payroll"]
            delta_oasdi_pct = curr["oasdi_pct_payroll"] - prev["oasdi_pct_payroll"]
            delta_hi_pct = curr["hi_pct_payroll"] - prev["hi_pct_payroll"]
            delta_revenue = curr["revenue_impact"] - prev["revenue_impact"]

            rows.append(
                {
                    "reform_name": reform,
                    "from_year": from_year,
                    "to_year": to_year,
                    "transition": f"{from_year}->{to_year}",
                    "focus_transition": (from_year, to_year) in FOCUS_TRANSITIONS,
                    "revenue_impact_from_B": prev["revenue_impact"],
                    "revenue_impact_to_B": curr["revenue_impact"],
                    "revenue_impact_delta_B": delta_revenue,
                    "total_pct_payroll_from": prev["total_pct_payroll"],
                    "total_pct_payroll_to": curr["total_pct_payroll"],
                    "total_pct_payroll_delta_pp": delta_total_pct,
                    "oasdi_pct_payroll_delta_pp": delta_oasdi_pct,
                    "hi_pct_payroll_delta_pp": delta_hi_pct,
                    "abs_total_pct_payroll_delta_pp": abs(delta_total_pct),
                    "classification": classify_transition(
                        reform,
                        from_year,
                        to_year,
                        delta_total_pct,
                    ),
                }
            )

    return pd.DataFrame(rows).sort_values(
        ["abs_total_pct_payroll_delta_pp", "reform_name", "to_year"],
        ascending=[False, True, True],
    )


def classify_transition(
    reform: str,
    from_year: int,
    to_year: int,
    delta_total_pct: float,
) -> str:
    if (from_year, to_year) == (2099, 2100):
        return "endpoint check"
    if (from_year, to_year) in FOCUS_TRANSITIONS:
        return "CRFB focus transition"
    if abs(delta_total_pct) >= 0.05 and to_year >= 2049:
        return "large late-horizon step"
    if reform == "option7" and to_year > 2028:
        return "expected zero after senior deduction expiration"
    return "not flagged"


def build_markdown(audit: pd.DataFrame) -> str:
    focus = audit[audit["focus_transition"]].sort_values(
        ["transition", "abs_total_pct_payroll_delta_pp", "reform_name"],
        ascending=[True, False, True],
    )
    top = audit[audit["to_year"] >= 2049].head(20)

    focus_rows = [
        [
            row.transition,
            row.reform_name,
            fmt_pp(row.total_pct_payroll_delta_pp),
            fmt_b(row.revenue_impact_delta_B),
            row.classification,
        ]
        for row in focus.itertuples()
    ]
    top_rows = [
        [
            row.transition,
            row.reform_name,
            fmt_pp(row.total_pct_payroll_delta_pp),
            fmt_b(row.revenue_impact_delta_B),
            row.classification,
        ]
        for row in top.itertuples()
    ]

    endpoint = audit[audit["transition"] == "2099->2100"]
    max_endpoint_row = endpoint.loc[endpoint["abs_total_pct_payroll_delta_pp"].idxmax()]

    return f"""
# Late-Horizon Discontinuity Audit

This audit checks year-over-year changes in static revenue impact as a percent
of OASDI taxable payroll. It focuses on the CRFB review transitions
`2049->2050`, `2074->2075`, and `2099->2100`, and excludes the legacy short
phase-in Roth variant (`option6`) from the publication-facing summary.

Generated CSV: `results/late_horizon_discontinuity_audit_20260430.csv`.

## Focus Transitions

{markdown_table(["Transition", "Reform", "Delta pp payroll", "Delta $B", "Classification"], focus_rows)}

## Largest Late-Horizon Steps

{markdown_table(["Transition", "Reform", "Delta pp payroll", "Delta $B", "Classification"], top_rows)}

## Readout

- The `2099->2100` endpoint is now explicitly measurable in the release audit.
  The largest publication-facing endpoint step is `{max_endpoint_row.reform_name}`
  at `{fmt_pp(max_endpoint_row.total_pct_payroll_delta_pp)}` percentage points
  of payroll.
- `option7` is expected to be zero after the temporary senior deduction window;
  any nonzero late-horizon row would be a release failure.
- Remaining large late-horizon steps should be treated as source/provenance
  questions, not silently described as policy effects, until reviewed against
  raw annual outputs and calibration metadata.
"""


def main() -> int:
    df = load_inputs()
    audit = build_transition_audit(df)
    audit.to_csv(OUT_CSV, index=False)
    OUT_MD.write_text(build_markdown(audit).strip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
