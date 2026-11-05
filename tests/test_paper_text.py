"""Guards for the public paper at /us/taxation-of-benefits-reforms/paper/.

The paper's generated exhibits must match what the generators produce from the
committed results panel; the reform count the paper and dashboard state must
match the reforms the dashboard menu offers; included fragments must nest under
the heading that includes them; the manuscript must carry no drafting notes;
and every figure written by hand into the prose must match the results panel.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from scripts import build_headline_summary as headline
from scripts import generate_paper_static_exhibits as exhibits

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER = REPO_ROOT / "paper"
SECTIONS = PAPER / "sections"
DASHBOARD_COMPONENTS = REPO_ROOT / "dashboard" / "src" / "components"
DASHBOARD_SHELL = DASHBOARD_COMPONENTS / "dashboard-shell.tsx"
DASHBOARD_METHODOLOGY = (
    DASHBOARD_COMPONENTS / "methodology-section.tsx",
    DASHBOARD_COMPONENTS / "methodology-diagram.tsx",
)
EXHIBIT_DIRS = (PAPER / "exhibits", SECTIONS / "exhibits")
DATASET_METADATA = REPO_ROOT / "projected_datasets_v2pop"
ECONOMIC_PROJECTIONS = REPO_ROOT / "data" / "ssa_economic_projections.csv"
FAR_HORIZON_YEARS = range(2075, 2101, 5)
SUPPORT_FLOOR = 50
INCLUDE = re.compile(r"\{\{< include (\S+) >\}\}")
HEADING = re.compile(r"^(#{1,6}) \S")

# Phrases that mark draft apparatus, revision history, or internal process
# rather than finished text a reader can use.
DRAFTING_PHRASES = (
    "artifact contract",
    "clean rerun",
    "current contract",
    "current development head",
    "current release",
    "draft",
    "drafting",
    "earlier internal notes",
    "fixme",
    "interpretation boundary",
    "legacy",
    "placeholder",
    "previously",
    "publication surface",
    "release logic",
    "release surface",
    "remaining manuscript work",
    "should be overwritten",
    "tbd",
    "the manuscript",
    "then-current",
    "this manuscript",
    "todo",
    "updated manuscript",
    "wired to",
)


def paper_texts() -> dict[str, str]:
    """Every file whose text renders into the paper."""
    paths = [PAPER / "index.qmd", *sorted(SECTIONS.glob("*.qmd"))]
    paths += sorted((SECTIONS / "exhibits").glob("*.md"))
    return {
        str(path.relative_to(REPO_ROOT)): path.read_text(encoding="utf-8")
        for path in paths
    }


def flat(text: str) -> str:
    """Collapse line breaks and runs of spaces so phrases match across wraps."""
    return re.sub(r"\s+", " ", text)


def dashboard_menu_ids() -> set[str]:
    shell = DASHBOARD_SHELL.read_text(encoding="utf-8")
    ids: set[str] = set()
    for name in ("BENEFIT_RULE_IDS", "STRUCTURAL_IDS"):
        match = re.search(rf"const {name} = \[(.*?)\];", shell, re.DOTALL)
        assert match, f"{name} not found in dashboard-shell.tsx"
        ids.update(re.findall(r'"([a-z0-9_]+)"', match.group(1)))
    return ids


@pytest.fixture(scope="module")
def static() -> pd.DataFrame:
    df = pd.read_csv(exhibits.RESULTS_CSV)
    return df[df["scoring_type"] == "static"]


@pytest.fixture(scope="module")
def behavioral() -> pd.DataFrame:
    df = pd.read_csv(exhibits.RESULTS_CSV)
    return df[df["scoring_type"] == "behavioral"]


def cell(df: pd.DataFrame, reform: str, year: int, column: str = "revenue_impact"):
    row = df[(df["reform_name"] == reform) & (df["year"] == year)]
    assert len(row) == 1, (reform, year)
    return float(row.iloc[0][column])


def test_committed_exhibits_match_generator() -> None:
    for name, text in exhibits.render_all().items():
        for directory in EXHIBIT_DIRS:
            committed = (directory / name).read_text(encoding="utf-8")
            assert committed == text, (
                f"{directory.name}/{name} is stale; run "
                "scripts/generate_paper_static_exhibits.py"
            )


def test_headline_fragment_matches_generator() -> None:
    text = headline.render_exhibit(headline.build())
    for directory in EXHIBIT_DIRS:
        committed = (directory / "headline-summary.md").read_text(encoding="utf-8")
        assert committed == text, (
            f"{directory.name}/headline-summary.md is stale; run "
            "scripts/build_headline_summary.py"
        )


def test_every_included_fragment_is_committed_and_mirrored() -> None:
    included = set()
    for name, text in paper_texts().items():
        for target in INCLUDE.findall(text):
            if name.startswith("paper/sections/"):
                assert (SECTIONS / target).exists(), f"{name} includes {target}"
            if target.startswith("exhibits/"):
                included.add(Path(target).name)
    generated = set(exhibits.render_all()) | {"headline-summary.md"}
    assert included == generated
    for name in generated:
        assert (PAPER / "exhibits" / name).read_bytes() == (
            SECTIONS / "exhibits" / name
        ).read_bytes()


def test_menu_reforms_match_dashboard_and_panel(static: pd.DataFrame) -> None:
    scored = set(static["reform_name"])

    assert set(exhibits.STANDARD_REFORMS) == scored
    assert set(exhibits.MENU_REFORMS) == dashboard_menu_ids()
    assert set(exhibits.MENU_REFORMS) == scored - set(exhibits.SENSITIVITY_REFORMS)
    assert len(exhibits.MENU_REFORMS) == 15


def test_paper_and_dashboard_state_the_menu_count() -> None:
    word = exhibits.count_word(len(exhibits.MENU_REFORMS))
    texts = paper_texts()
    for name in (
        "paper/index.qmd",
        "paper/sections/01-scope.qmd",
        "paper/sections/02-policy-design.qmd",
    ):
        assert f"{word} reforms" in flat(texts[name]), name
    for name, text in texts.items():
        assert not re.search(r"\b(fourteen|sixteen)\b", text, re.I), name

    section, diagram = (
        path.read_text(encoding="utf-8") for path in DASHBOARD_METHODOLOGY
    )
    assert f"all {word} reforms" in flat(section)
    assert f"{len(exhibits.MENU_REFORMS)} reforms" in diagram
    for text in (section, diagram):
        assert not re.search(
            r"\b(fourteen|sixteen|14 options|16 options)\b", text, re.I
        )


def test_paper_carries_no_drafting_notes() -> None:
    for name, text in paper_texts().items():
        lowered = flat(text).lower()
        for phrase in DRAFTING_PHRASES:
            assert not re.search(rf"\b{re.escape(phrase)}\b", lowered), (
                f"{name} contains drafting phrase {phrase!r}"
            )


def test_included_fragment_headings_nest_under_the_including_heading() -> None:
    for path in [PAPER / "index.qmd", *sorted(SECTIONS.glob("*.qmd"))]:
        parent_level = 0
        in_code = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            heading = HEADING.match(line)
            if heading:
                parent_level = len(heading.group(1))
                continue
            include = INCLUDE.search(line)
            if not include or not include.group(1).startswith("exhibits/"):
                continue
            fragment = (SECTIONS / include.group(1)).read_text(encoding="utf-8")
            levels = [
                len(match.group(1))
                for match in map(HEADING.match, fragment.splitlines())
                if match
            ]
            if levels:
                assert min(levels) == parent_level + 1, (
                    f"{include.group(1)} headings start at level {min(levels)} "
                    f"under a level-{parent_level} heading in {path.name}"
                )


def test_abstract_figures_match_results(static: pd.DataFrame) -> None:
    abstract = flat((PAPER / "index.qmd").read_text(encoding="utf-8"))
    first_decade = static[static["year"].between(2026, 2035)]
    ten_year = first_decade.groupby("reform_name")["revenue_impact"].sum()
    pv = {
        row["reform"]: float(row["pv75_total_billions"])
        for row in headline.build()
        if row["baseline_scenario"] == "scheduled_benefits"
    }

    assert f"${abs(ten_year['option1']) / 1000:.2f} trillion" in abstract
    assert f"${abs(pv['option1']) / 1000:.1f} trillion" in abstract
    assert ten_year["option1"] < 0 and pv["option1"] < 0
    assert f"${ten_year['option8']:,.0f} billion" in abstract

    for reform, name in (("option5", "immediate"), ("option12", "phased")):
        series = static[static["reform_name"] == reform].set_index("year")
        revenue = series["revenue_impact"].sort_index()
        first_loss = int(revenue[revenue < 0].index.min())
        assert (revenue.loc[: first_loss - 1] > 0).all()
        assert (revenue.loc[first_loss:] < 0).all()
        assert f"from `{first_loss}` for the {name}" in abstract, reform


def test_methods_figures_match_results(
    static: pd.DataFrame, behavioral: pd.DataFrame
) -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))

    def gap(reform: str, years: slice) -> float:
        series = static[static["reform_name"] == reform].set_index("year").sort_index()
        diff = (
            series["oasdi_net_impact"]
            + series["hi_net_impact"]
            - series["revenue_impact"]
        )
        assert (diff > 0).all(), f"{reform}'s fund sum should exceed revenue every year"
        return float(diff.loc[years].sum())

    ten_year_gaps = [
        gap(r, slice(2026, 2035)) for r in ("option5", "option12", "option6")
    ]
    assert (
        f"by ${ten_year_gaps[0]:.1f} billion for `option5`, "
        f"${ten_year_gaps[1]:.1f} billion for `option12`, and "
        f"${ten_year_gaps[2]:.1f} billion for `option6`"
    ) in methods
    terminal = {
        round(gap(r, slice(2100, 2100)), 1) for r in ("option5", "option12", "option6")
    }
    assert len(terminal) == 1
    assert f"${terminal.pop():.1f} billion for each in `2100`" in methods

    def straight(reform: str, year: int, start: int, end: int) -> float:
        low, high = cell(static, reform, start), cell(static, reform, end)
        return low + (high - low) * (year - start) / (end - start)

    understatement = cell(static, "option7", 2028) - straight(
        "option7", 2028, 2026, 2030
    )
    assert f"`2028` impact by ${understatement:.1f} billion" in methods
    assert cell(static, "option7", 2029) == pytest.approx(0, abs=0.005)

    corner_gap = abs(
        straight("option5", 2062, 2060, 2065) - straight("option12", 2062, 2060, 2065)
    )
    assert f"put them ${corner_gap:.1f} billion apart" in methods
    for frame in (static, behavioral):
        assert cell(frame, "option5", 2062) == pytest.approx(
            cell(frame, "option12", 2062), abs=1e-6
        )

    assert (
        f"`${cell(static, 'option1', 2030, 'baseline_revenue'):,.1f}` billion"
        in methods
    )
    seam = [cell(static, r, 2030) for r in ("option1", "option7", "option8")]
    assert (
        f"`-${abs(seam[0]):.1f}`, `${seam[1]:.1f}`, and `${seam[2]:.1f}` billion"
    ) in methods


def test_validation_and_design_claims_hold(static: pd.DataFrame) -> None:
    repeal = static[static["reform_name"] == "option1"]
    anchors = repeal[repeal["full_h5_result_type"] == exhibits.EXACT_STATIC]
    assert len(anchors) >= 16
    assert anchors["reform_tob_total"].abs().max() < 1e-6
    assert (
        anchors["revenue_impact"] + anchors["baseline_tob_total"]
    ).abs().max() < 1e-5
    assert (static.loc[static["reform_name"] == "option8", "revenue_impact"] > 0).all()

    for year in (2075, 2100):
        assert cell(static, "option11", year) == pytest.approx(
            cell(static, "option2", year), abs=0.05
        )
    assert cell(static, "option11", 2050) < cell(static, "option2", 2050) - 1


def test_income_tax_share_of_gdp_matches_methods(static: pd.DataFrame) -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    gdp = pd.read_csv(ECONOMIC_PROJECTIONS).set_index("year")["gdp"]
    baseline = static[static["reform_name"] == "option1"].set_index("year")[
        "baseline_revenue"
    ]
    share = 100 * baseline / gdp.reindex(baseline.index)
    assert share.notna().all()
    low, high = round(share.min()), round(share.max())
    assert f"about {low} to {high} percent of GDP" in methods


def dataset_audits() -> dict[int, dict]:
    audits = {}
    for path in sorted(DATASET_METADATA.glob("*.h5.metadata.json")):
        year = int(path.name.split(".")[0])
        audits[year] = json.loads(path.read_text(encoding="utf-8"))
    assert set(FAR_HORIZON_YEARS) <= set(audits)
    return audits


def test_published_datasets_calibrate_exactly_on_real_records() -> None:
    for year, metadata in dataset_audits().items():
        assert metadata["calibration_audit"]["calibration_quality"] == "exact", year
        assert metadata["sentinel"]["donor_clone_household_count"] == 0, year


def test_far_horizon_support_figures_match_dataset_metadata() -> None:
    validation = flat((SECTIONS / "05-validation.qmd").read_text(encoding="utf-8"))
    audits = dataset_audits()

    def ess(year: int, fund: str) -> float:
        contributors = audits[year]["calibration_audit"]["contributors"]
        return float(contributors[fund]["contributor_effective_sample_size"])

    for fund, label in (("oasdi_tob", "OASDI"), ("hi_tob", "HI")):
        values = [ess(year, fund) for year in FAR_HORIZON_YEARS]
        assert min(values) >= SUPPORT_FLOOR
        assert (
            f"`{round(min(values))}`-`{round(max(values))}` for {label}" in validation
        )
        assert f"`{round(ess(2100, fund))}` for {label}" in validation
    assert f"floor of `{SUPPORT_FLOOR}`" in validation
    top_10 = audits[2100]["calibration_audit"]["top_10_weight_share_pct"]
    assert f"`{top_10:.1f}%` of the total weight" in validation
