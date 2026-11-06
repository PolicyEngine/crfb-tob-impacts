"""Generate the Markdown exhibits that the paper includes from the results panel.

Every exhibit reads the published dashboard panel
(``dashboard/public/data/results.csv``) and writes the same text to
``paper/exhibits/`` and ``paper/sections/exhibits/``. The prose inside each
exhibit states rankings and comparisons computed from that panel; ``check``
raises if a regenerated panel would make a sentence false, so a data change
cannot silently leave stale prose behind.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import sys

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.build_headline_summary import REFORM_LABELS  # noqa: E402

EXHIBITS = REPO / "paper" / "exhibits"
SECTION_EXHIBITS = REPO / "paper" / "sections" / "exhibits"
RESULTS_CSV = REPO / "dashboard" / "public" / "data" / "results.csv"
STANDARD_REFORMS = tuple(f"option{i}" for i in range(1, 13)) + (
    "reverse_roth",
    "tax93",
    "magi100",
    "tax_panel_2005",
)
# option6, the short phase-in Roth swap, stays in the scored panel as a
# sensitivity case. The dashboard menu omits it
# (dashboard/src/components/dashboard-shell.tsx), so the paper counts the
# fifteen menu reforms and labels option6 wherever a table includes it.
SENSITIVITY_REFORMS = ("option6",)
MENU_REFORMS = tuple(r for r in STANDARD_REFORMS if r not in SENSITIVITY_REFORMS)
SWAP_REFORMS = ("option5", "option6", "option12")
# How running text names each reform. Tables use REFORM_LABELS, the dashboard's
# names, and paper/sections/02-policy-design.qmd ties both to the results file's
# reform codes.
PROSE_NAMES = {
    "option1": "full repeal",
    "magi100": "full MAGI inclusion",
    "tax_panel_2005": "the 2005 Tax Panel deduction",
    "option2": "85 percent taxation",
    "option3": "85 percent taxation with the extended senior deduction",
    "option7": "the senior-deduction repeal",
    "option4": "the $500 credit",
    "option11": "the $700 credit",
    "option9": "90 percent taxation",
    "tax93": "93 percent taxation",
    "option10": "95 percent taxation",
    "option8": "100 percent taxation",
    "option5": "the Roth swap",
    "option6": "the short phase-in Roth",
    "option12": "the phased Roth swap",
    "reverse_roth": "the reverse Roth",
}
ENDPOINT_YEARS = (2026, 2100)
MILESTONE_YEARS = (2035, 2050, 2075, 2100)
BUDGET_WINDOW_YEARS = (2028, 2029)
PHASE_IN_CORNER_YEARS = (2032, 2033)
NUMBER_WORDS = {
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
}
DASHBOARD_URL = "https://policyengine.org/us/taxation-of-benefits-reforms"
RESULTS_CSV_URL = f"{DASHBOARD_URL}/data/results.csv"
EXACT_STATIC = "exact_full_h5"
EXACT_BEHAVIORAL = "exact_behavioral_endpoint_full_h5"

# paper/sections/04-results.qmd and 05-validation.qmd
# include these fragments under level-2 headings, so fragment headings start
# at level 3 (tests/test_paper_text.py checks the nesting).
FRAGMENT_HEADING = "###"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"exhibit prose no longer matches the panel: {message}")


def fmt_b(value: float) -> str:
    return f"{value:+,.1f}"


def dollars(value: float) -> str:
    return f"${abs(value):,.1f} billion"


def label(reform: str) -> str:
    """Name a reform in a table, as the dashboard menu does."""
    name = REFORM_LABELS[reform]
    return f"{name} (sensitivity)" if reform in SENSITIVITY_REFORMS else name


def prose(reform: str) -> str:
    return PROSE_NAMES[reform]


def opening(reform: str) -> str:
    """Name a reform at the start of a sentence."""
    name = PROSE_NAMES[reform]
    return name[0].upper() + name[1:]


def count_word(count: int) -> str:
    return NUMBER_WORDS[count]


def table_row(cells: list[str]) -> str:
    """Escape dollar signs, since Pandoc reads two in one row as inline math."""
    return "| " + " | ".join(cell.replace("$", r"\$") for cell in cells) + " |"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        table_row(headers),
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend(table_row(row) for row in rows)
    return "\n".join(lines)


def load_panel() -> pd.DataFrame:
    df = pd.read_csv(RESULTS_CSV)
    return df[df["reform_name"].isin(STANDARD_REFORMS)].copy()


def load_static() -> pd.DataFrame:
    df = load_panel()
    static = df[df["scoring_type"] == "static"]
    return static.sort_values(["year", "reform_name"]).reset_index(drop=True)


def load_behavioral() -> pd.DataFrame:
    df = load_panel()
    behavioral = df[df["scoring_type"] == "behavioral"]
    return behavioral.sort_values(["year", "reform_name"]).reset_index(drop=True)


def ordered(reforms: Iterable[str]) -> list[str]:
    present = set(reforms)
    return [r for r in REFORM_LABELS if r in present]


def build_results_overview(df: pd.DataFrame) -> str:
    check(
        set(df["reform_name"]) == set(STANDARD_REFORMS),
        "the static panel should hold every standard reform",
    )
    ten_year = (
        df[df["year"].between(2026, 2035)]
        .groupby("reform_name")["revenue_impact"]
        .sum()
    )
    terminal = df[df["year"] == 2100].set_index("reform_name")

    ten_year_table = markdown_table(
        ["Reform", "2026-2035 revenue impact ($B)"],
        [
            [label(reform), fmt_b(value)]
            for reform, value in ten_year.sort_values().items()
        ],
    )
    terminal_table = markdown_table(
        ["Reform", "2100 revenue impact ($B)", "2100 benefit-tax revenue impact ($B)"],
        [
            [
                label(reform),
                fmt_b(row.revenue_impact),
                fmt_b(row.tob_total_impact),
            ]
            for reform, row in terminal.sort_values("revenue_impact").iterrows()
        ],
    )

    menu_ten_year = ten_year[list(MENU_REFORMS)].sort_values(ascending=False)
    first, second = menu_ten_year.index[:2]
    last = menu_ten_year.index[-1]
    check(menu_ten_year[last] < 0, "the smallest ten-year impact should be a loss")

    menu_terminal = terminal.loc[list(MENU_REFORMS), "revenue_impact"]
    top, runner_up = menu_terminal.sort_values(ascending=False).index[:2]
    losses = menu_terminal[menu_terminal < 0].sort_values()
    worst, next_worst = losses.index[:2]
    check(
        worst not in SWAP_REFORMS and next_worst not in SWAP_REFORMS,
        "the two largest 2100 losses should come from non-swap reforms",
    )
    swap_terminal = terminal.loc[list(SWAP_REFORMS)]
    check(
        swap_terminal["revenue_impact"].max() - swap_terminal["revenue_impact"].min()
        < 0.01,
        "the Roth swaps should share one 2100 revenue impact",
    )
    check(
        bool((swap_terminal["reform_tob_total"].abs() < 0.01).all()),
        "no Roth swap should tax benefits in 2100",
    )
    swap_loss = float(swap_terminal["revenue_impact"].iloc[0])
    check(swap_loss < 0, "the Roth swaps should lose revenue in 2100")

    return f"""
{FRAGMENT_HEADING} Ten-year static revenue impacts

Over 2026-2035, we estimate that {prose(first)} raises the most revenue of the
{count_word(len(MENU_REFORMS))} reforms ({dollars(menu_ten_year[first])}) and
{prose(second)} the next most ({dollars(menu_ten_year[second])}).
{opening(last)} loses the most ({dollars(menu_ten_year[last])}).

{ten_year_table}

{FRAGMENT_HEADING} Terminal-year static impacts

In 2100, we estimate that {prose(top)} raises the most revenue
({dollars(menu_terminal[top])}) and {prose(runner_up)} the next most
({dollars(menu_terminal[runner_up])}). {opening(worst)} loses the most
({dollars(menu_terminal[worst])}), followed by {prose(next_worst)}
({dollars(menu_terminal[next_worst])}). By then {prose("option5")},
{prose("option12")}, and {prose("option6")} reach the same end state, with
employer contributions taxable and no benefits taxed, and each loses
{dollars(swap_loss)}.

{terminal_table}
"""


def build_milestones(df: pd.DataFrame) -> str:
    """Milestone-year static impacts for every scored reform."""
    lineage = df[df["full_h5_result_type"] == EXACT_STATIC]
    check(
        bool(lineage["run_prefix"].notna().all())
        and bool(lineage["output_h5_sha256"].notna().all()),
        "every exact cell should record its run prefix and output hash",
    )
    panel = df.pivot(index="reform_name", columns="year", values="revenue_impact")
    milestones = panel.loc[:, list(MILESTONE_YEARS)]

    def rising(reform: str) -> bool:
        return bool((milestones.loc[reform].diff().dropna() > 0).all())

    def falling(reform: str) -> bool:
        return bool((milestones.loc[reform].diff().dropna() < 0).all())

    check(
        bool((milestones.loc["option1"] < 0).all()) and falling("option1"),
        "option1 should lose more revenue at each milestone",
    )
    for reform in ("option5", "option12"):
        values = milestones.loc[reform]
        check(
            values[2035] > 0 and values[2050] > 0,
            f"{reform} should raise revenue in 2035 and 2050",
        )
        check(
            values[2075] < 0 and values[2100] < 0,
            f"{reform} should lose revenue in 2075 and 2100",
        )
        row = df[(df["reform_name"] == reform) & (df["year"] == 2075)].iloc[0]
        employer_tax = row.employer_ss_tax_revenue + row.employer_medicare_tax_revenue
        check(
            -row.tob_total_impact > employer_tax,
            f"{reform}'s 2075 benefit-tax loss should exceed its employer tax",
        )
    gainers = (
        "option2",
        "option3",
        "option4",
        "option8",
        "option9",
        "option10",
        "option11",
        "tax93",
        "magi100",
    )
    for reform in gainers:
        check(
            bool((milestones.loc[reform] > 0).all()) and rising(reform),
            f"{reform} should raise more revenue at each milestone",
        )

    milestone_table = markdown_table(
        ["Reform"] + [f"{year} ($B)" for year in MILESTONE_YEARS],
        [
            [label(reform)]
            + [fmt_b(float(milestones.loc[reform, year])) for year in MILESTONE_YEARS]
            for reform in ordered(milestones.index)
        ],
    )

    return f"""
We estimate that the revenue loss from {prose("option1")} grows at each
milestone year. {opening("option5")} and {prose("option12")} raise revenue in
2035 and 2050 but lose it by 2075, when the benefit-tax revenue they repeal
exceeds the income tax on employer contributions. The revenue gain from every
reform that taxes more of benefits grows at each milestone year.

{milestone_table}
"""


def swap_trust_fund_gap(df: pd.DataFrame, reform: str, year: int) -> float:
    """OASDI net plus HI net, less the federal income-tax change, in $B."""
    row = df[(df["reform_name"] == reform) & (df["year"] == year)].iloc[0]
    return float(row.oasdi_net_impact + row.hi_net_impact - row.revenue_impact)


def build_trust_fund_decomposition(df: pd.DataFrame) -> str:
    decomposition_reforms = ordered(
        ["option1", "option2", "option4", "option8", "option12"]
    )
    terminal = df[df["year"] == 2100].set_index("reform_name")
    rows = [
        [
            label(reform),
            fmt_b(terminal.loc[reform, "revenue_impact"]),
            fmt_b(terminal.loc[reform, "tob_total_impact"]),
            fmt_b(terminal.loc[reform, "oasdi_net_impact"]),
            fmt_b(terminal.loc[reform, "hi_net_impact"]),
        ]
        for reform in decomposition_reforms
    ]
    benefit_taxation = [r for r in decomposition_reforms if r not in SWAP_REFORMS]
    for reform in benefit_taxation:
        check(
            abs(swap_trust_fund_gap(df, reform, 2100)) < 0.01,
            f"{reform}'s fund impacts should sum to its revenue impact",
        )
    gap = swap_trust_fund_gap(df, "option12", 2100)
    check(gap > 0, "option12's fund impacts should exceed its revenue impact")

    def net(reform: str, fund: str) -> float:
        return float(terminal.loc[reform, f"{fund}_net_impact"])

    check(
        net("option1", "oasdi") < 0 and net("option1", "hi") < 0,
        "full repeal should cost both funds in 2100",
    )
    check(
        net("option2", "oasdi") > 0
        and abs(net("option2", "oasdi") - net("option8", "oasdi")) < 0.05,
        "85 and 100 percent taxation should give OASDI one 2100 gain",
    )
    check(
        net("option12", "oasdi") > 0 and net("option12", "hi") < 0,
        "the phased Roth swap should gain OASDI and cost HI in 2100",
    )

    table = markdown_table(
        [
            "Reform",
            "2100 revenue ($B)",
            "2100 benefit-tax revenue ($B)",
            "2100 OASDI net ($B)",
            "2100 HI net ($B)",
        ],
        rows,
    )
    return f"""
This table credits each trust fund with the revenue the model attributes to it,
not the default split in @sec-headline, and applies the rules in
@sec-swap-accounting to {prose("option12")}. We estimate that in 2100
{prose("option1")} costs OASDI {dollars(net("option1", "oasdi"))} and HI
{dollars(net("option1", "hi"))}. Under 85 or 100 percent taxation, OASDI gains
{dollars(net("option2", "oasdi"))} and HI gains the rest. {opening("option12")}
gains OASDI {dollars(net("option12", "oasdi"))} and costs HI
{dollars(net("option12", "hi"))}.

{table}
"""


def straight_line(
    df: pd.DataFrame, reform: str, year: int, start: int, end: int
) -> float:
    """Revenue impact on the straight line between two anchor years, in $B."""
    values = df[df["reform_name"] == reform].set_index("year")["revenue_impact"]
    low, high = float(values[start]), float(values[end])
    return low + (high - low) * (year - start) / (end - start)


def build_budget_window_anchors(df: pd.DataFrame) -> str:
    """Compare the added exact anchors with straight lines between neighbors."""
    exact = set(
        df.loc[
            df["full_h5_result_type"] == EXACT_STATIC, ["reform_name", "year"]
        ].itertuples(index=False, name=None)
    )
    revenue = df.set_index(["reform_name", "year"])["revenue_impact"]

    rows = []
    gaps = []
    for reform in ordered(STANDARD_REFORMS):
        row = [label(reform)]
        for year in BUDGET_WINDOW_YEARS:
            check((reform, year) in exact, f"{reform} {year} should be exact")
            line = straight_line(df, reform, year, 2026, 2030)
            value = float(revenue[(reform, year)])
            gaps.append((abs(value - line), reform, year))
            row += [fmt_b(line), fmt_b(value)]
        rows.append(row)
    largest_gap, gap_reform, gap_year = max(gaps)

    corner = {}
    for year in PHASE_IN_CORNER_YEARS:
        check(("option6", year) in exact, f"option6 {year} should be exact")
        corner[year] = (
            straight_line(df, "option6", year, 2030, 2035),
            float(revenue[("option6", year)]),
        )
    first, last = PHASE_IN_CORNER_YEARS

    table = markdown_table(
        [
            "Reform",
            "2028 straight line ($B)",
            "2028 exact ($B)",
            "2029 straight line ($B)",
            "2029 exact ($B)",
        ],
        rows,
    )
    return f"""
Straight lines between each reform's 2026 and 2030 anchors miss the exact 2028
and 2029 anchors by as much as {dollars(largest_gap)}, for {prose(gap_reform)} in
{gap_year}.

{table}

For {prose("option6")}, the straight line between 2030 and 2035 would give
{dollars(corner[first][0])} in {first} and {dollars(corner[last][0])} in {last},
against exact anchors of {dollars(corner[first][1])} and
{dollars(corner[last][1])}.
"""


def build_external_benchmarks(df: pd.DataFrame) -> str:
    first_decade = df[df["year"].between(2026, 2035)]
    ten_year = (
        first_decade.groupby("reform_name", as_index=False)["revenue_impact"]
        .sum()
        .set_index("reform_name")["revenue_impact"]
    )
    ten_year_tob = (
        first_decade.groupby("reform_name", as_index=False)["tob_total_impact"]
        .sum()
        .set_index("reform_name")["tob_total_impact"]
    )

    option1_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue impact ($B)"],
        [
            [
                "PolicyEngine",
                label("option1"),
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option1"])),
            ],
            [
                "CBO [@cbo2024options]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,600.0",
            ],
            [
                "SSA Trustees [@ssa2024trustees]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,800.0",
            ],
            [
                "Tax Foundation [@taxfoundation2024trump]",
                "Full repeal",
                "Conventional",
                "2025-2034",
                "-1,400.0",
            ],
            [
                "Tax Foundation [@taxfoundation2024trump]",
                "Full repeal",
                "Macroeconomic",
                "2025-2034",
                "-1,300.0",
            ],
        ],
    )

    option2_table = markdown_table(
        ["Source", "Policy", "Scoring", "Window", "Revenue impact ($B)"],
        [
            [
                "PolicyEngine",
                label("option2"),
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option2"])),
            ],
            [
                "PolicyEngine",
                label("option8"),
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option8"])),
            ],
            [
                "JCT [@jct2024expenditures]",
                "Current SS tax expenditure",
                "Conventional",
                "2024-2028",
                "+318.4",
            ],
            [
                "CBO [@cbo2024pension]",
                "Pension-style basis recovery",
                "Conventional",
                "2021-2030",
                "+458.7",
            ],
        ],
    )

    option7_table = markdown_table(
        [
            "Source",
            "Policy",
            "Scoring",
            "Window",
            "Federal revenue ($B)",
            "Benefit-tax revenue impact ($B)",
        ],
        [
            [
                "PolicyEngine",
                label("option7"),
                "Static",
                "2026-2035",
                fmt_b(float(ten_year["option7"])),
                fmt_b(float(ten_year_tob["option7"])),
            ],
            [
                "JCT [@jct2025bonus]",
                "Bonus senior deduction",
                "Conventional",
                "FY2025-FY2034",
                "-66.3",
                "n/a",
            ],
        ],
    )

    return f"""
{FRAGMENT_HEADING} Full repeal

{option1_table}

{FRAGMENT_HEADING} 85 and 100 percent taxation

{option2_table}

{FRAGMENT_HEADING} Bonus senior deduction

JCT scores enacting the deduction and we score repealing it, so the signs differ.

{option7_table}
"""


def build_labor_supply_responses(static: pd.DataFrame, behavioral: pd.DataFrame) -> str:
    scored = set(behavioral["reform_name"])
    check(
        [r for r in MENU_REFORMS if r not in scored] == ["magi100", "tax_panel_2005"],
        "every menu reform but two should carry labor-supply responses",
    )
    check(
        set(SENSITIVITY_REFORMS) <= scored,
        "the sensitivity case should carry labor-supply responses",
    )

    exact = behavioral[behavioral["full_h5_result_type"] == EXACT_BEHAVIORAL]
    anchors = {
        reform: sorted(int(year) for year in group["year"])
        for reform, group in exact.groupby("reform_name")
    }
    check(set(anchors) == scored, "every scored reform should have exact anchors")
    for reform, years in anchors.items():
        check(
            all(year in years for year in ENDPOINT_YEARS),
            f"{reform} should have exact 2026 and 2100 anchors",
        )

    rows = []
    effects = {}
    for reform in ordered(scored):
        with_responses = behavioral[behavioral["reform_name"] == reform].set_index(
            "year"
        )
        without = static[static["reform_name"] == reform].set_index("year")
        cells = [label(reform)]
        for year in ENDPOINT_YEARS:
            response = float(with_responses.loc[year, "revenue_impact"])
            effect = response - float(without.loc[year, "revenue_impact"])
            cells += [fmt_b(response), fmt_b(effect)]
            effects[reform] = effect
        rows.append(cells)
    table = markdown_table(
        [
            "Reform",
            "2026 revenue impact ($B)",
            "2026 response effect ($B)",
            "2100 revenue impact ($B)",
            "2100 response effect ($B)",
        ],
        rows,
    )

    swap_effects = [effects[reform] for reform in SWAP_REFORMS]
    check(
        max(swap_effects) < 0 and max(swap_effects) - min(swap_effects) < 0.05,
        "responses should cost each Roth swap one amount in 2100",
    )
    check(
        effects["reverse_roth"] > 0, "responses should offset the reverse Roth's loss"
    )
    other = max(
        abs(effect)
        for reform, effect in effects.items()
        if reform not in SWAP_REFORMS and reform != "reverse_roth"
    )

    return f"""
We estimate that in 2100 labor-supply responses cost the Roth swaps another
{dollars(swap_effects[0])}, offset {dollars(effects["reverse_roth"])} of the
reverse Roth's loss, and move every other reform's revenue impact by at most
{dollars(other)}.

For each reform, we report the revenue impact with labor-supply responses at the
two endpoints and the response effect, which subtracts the static impact.

{table}
"""


def build_household_impacts() -> str:
    return f"""
We report each reform's change in household net income, by baseline income
decile, on the [dashboard]({DASHBOARD_URL}). We simulate anchor years from
2026 to 2100 and interpolate the years between them.
"""


def render_all() -> dict[str, str]:
    static = load_static()
    behavioral = load_behavioral()
    exhibits = {
        "results-overview.md": build_results_overview(static),
        "full-h5-results-summary.md": build_milestones(static),
        "revenue-impacts.md": build_trust_fund_decomposition(static),
        "budget-window-anchors.md": build_budget_window_anchors(static),
        "external-benchmarks.md": build_external_benchmarks(static),
        "labor-supply-response-status.md": build_labor_supply_responses(
            static, behavioral
        ),
        "household-impacts.md": build_household_impacts(),
    }
    return {name: text.strip() + "\n" for name, text in exhibits.items()}


def main() -> None:
    EXHIBITS.mkdir(parents=True, exist_ok=True)
    SECTION_EXHIBITS.mkdir(parents=True, exist_ok=True)
    for name, text in render_all().items():
        for directory in (EXHIBITS, SECTION_EXHIBITS):
            (directory / name).write_text(text, encoding="utf-8")

    print("Wrote paper exhibits:")
    for path in sorted(EXHIBITS.glob("*.md")):
        print(f" - {path}")


if __name__ == "__main__":
    main()
