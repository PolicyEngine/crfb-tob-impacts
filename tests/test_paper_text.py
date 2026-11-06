"""Guards for the public paper at /us/taxation-of-benefits-reforms/paper/.

The paper's generated exhibits must match what the generators produce from the
committed results panel; the reform count the paper and dashboard state must
match the reforms the dashboard menu offers; included fragments must nest under
the heading that includes them; the manuscript must carry no drafting notes;
every figure written by hand into the prose must match the results panel; each
claim about how a run or baseline was produced must match the record that
scripts/build_run_provenance.py writes from the runs' own metadata files; and a
reader must meet each reform by one name and every table with intact headers.

Invariants over the published panel and the run record:

- Every exact row belongs to one run, and the record's digest of each run's rows
  matches the results file.
- Every run shares the package versions the paper states and checked its
  baseline against a manifest on every row.
- Every baseline H5 appears in a committed manifest, calibrates exactly, and
  clears every publication gate in every year.
- Every interpolated row's anchors are the nearest exact years on either side.
- Every reform code appears once in the paper, in the section that defines it.
- No exhibit holds a dollar sign that Pandoc could read as closing math.
- The age groups, growth cap, scaled income, indexed parameters, wage path, and
  trust-fund splits the methods state match each dataset's metadata, the results
  files, and the code that splits revenue.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts import build_headline_summary as headline
from scripts import build_run_provenance as provenance
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
SOLVENCY_RESULTS = (
    REPO_ROOT / "dashboard" / "public" / "data" / "balanced_fix_results.csv"
)
ECONOMIC_PROJECTIONS = REPO_ROOT / "data" / "ssa_economic_projections.csv"
TRUSTEES_AUX = REPO_ROOT / "data" / "social_security_aux_tr2026.csv"
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "public" / "data"
BASELINE_ASSUMPTIONS = DASHBOARD_DATA / "baseline_assumptions_metadata.json"
INDEXED_PARAMETERS = DASHBOARD_DATA / "baseline_indexed_parameters.csv"
INDEXING_GROWTH = DASHBOARD_DATA / "baseline_indexing_growth.csv"
DIAGNOSTICS = DASHBOARD_DATA / "v2_baseline_diagnostics.csv"
BASELINE_TAB = DASHBOARD_COMPONENTS / "baseline-assumptions-section.tsx"

MANIFESTS = REPO_ROOT / "docs" / "current" / "manifests"
FAR_HORIZON_YEARS = range(2075, 2101, 5)
SUPPORT_FLOOR = 50
INCLUDE = re.compile(r"\{\{< include (\S+) >\}\}")
HEADING = re.compile(r"^(#{1,6}) \S")
REFORM_CODE = re.compile(r"\b(option\d+|reverse_roth|tax93|magi100|tax_panel_2005)\b")
NUMBER_IN_CODE_FONT = re.compile(r"`[-+]?\$?\d[\d,.]*%?\+?`")
REPO_FILE_LINK = re.compile(r"crfb-tob-impacts/blob/main/([^)\s]+)\)")

# The limits at the commits that built the published baselines (3de8abb6 and
# c5e4f1a6). They differ from src/projection.py at head; see
# docs/current/late-year-support-gates.md.
WEIGHT_GATES = {
    "positive_weight_count": ("min", 1_000),
    "effective_sample_size": ("min", 300.0),
    "top_10_weight_share_pct": ("max", 15.0),
    "top_100_weight_share_pct": ("max", 45.0),
}
TOB_CONTRIBUTOR_GATES = {
    "positive_contributor_count": ("min", 1_000),
    "contributor_effective_sample_size": ("min", 50.0),
    "top_10_contribution_share_pct": ("max", 50.0),
    "top_100_contribution_share_pct": ("max", 95.0),
    "max_contribution_share_pct": ("max", 15.0),
}
CONTRIBUTOR_GATES = {
    "ss_total": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 25.0),
        "top_10_contribution_share_pct": ("max", 60.0),
        "top_100_contribution_share_pct": ("max", 95.0),
        "max_contribution_share_pct": ("max", 15.0),
    },
    "payroll_total": {
        "positive_contributor_count": ("min", 1_000),
        "contributor_effective_sample_size": ("min", 200.0),
        "top_10_contribution_share_pct": ("max", 20.0),
        "top_100_contribution_share_pct": ("max", 50.0),
        "max_contribution_share_pct": ("max", 5.0),
    },
    "oasdi_tob": TOB_CONTRIBUTOR_GATES,
    "hi_tob": TOB_CONTRIBUTOR_GATES,
}

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
    "full-h5",
    "interpretation boundary",
    "legacy",
    "placeholder",
    "previously",
    "publication surface",
    "release logic",
    "release surface",
    "remaining manuscript work",
    "rough-estimate",
    "should be overwritten",
    "tbd",
    "the manuscript",
    "then-current",
    "this manuscript",
    "todo",
    "updated manuscript",
    "wired to",
)

# Terms from claims the code does not support: the v1 calibration profile's name,
# a calibration fallback no code path has, run machinery only some runs used, and
# wrong descriptions of the records, age groups, growth cap, income guards, indexed
# parameters, and parameter review.
UNSUPPORTED_CLAIM_PHRASES = (
    "86 columns",
    "core federal income-tax thresholds",
    "iterative proportional",
    "modal",
    "no income source grows faster",
    "real survey",
    "reproducibility bundle",
    "runtime",
    "scanned every model parameter",
    "smoke-test",
    "ss-payroll-tob",
    "stage a growth paths",
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
        # Include directives name source files; a reader never sees them.
        lowered = flat(INCLUDE.sub("", text)).lower()
        for phrase in DRAFTING_PHRASES:
            assert not re.search(rf"\b{re.escape(phrase)}\b", lowered), (
                f"{name} contains drafting phrase {phrase!r}"
            )


def test_paper_drops_claims_the_code_does_not_support() -> None:
    for name, text in paper_texts().items():
        lowered = flat(text).lower()
        for phrase in UNSUPPORTED_CLAIM_PHRASES:
            assert not re.search(rf"\b{re.escape(phrase)}\b", lowered), (
                f"{name} contains {phrase!r}"
            )


def test_dashboard_methodology_shows_no_internal_tracking() -> None:
    section, diagram = (
        path.read_text(encoding="utf-8") for path in DASHBOARD_METHODOLOGY
    )
    for term in ("Internal", "LiveModelingProgress", "ReproducibilityRoadmap"):
        assert term not in section, term
    assert "Modal" not in diagram
    assert "Options 5-6" not in section


def test_dashboard_methodology_drops_claims_the_code_does_not_support() -> None:
    for path in DASHBOARD_METHODOLOGY:
        text = flat(path.read_text(encoding="utf-8")).lower()
        for phrase in ("awi", "cbo-vintage", "growth paths", "outruns", "real survey"):
            assert not re.search(rf"\b{re.escape(phrase)}\b", text), (path.name, phrase)


def test_baseline_tab_names_the_wage_path_it_uses() -> None:
    tab = flat(BASELINE_TAB.read_text(encoding="utf-8"))
    for phrase in (
        "Core tax thresholds",
        "Trustees average-wage growth",
        "Trustees wage indexing",
    ):
        assert phrase not in tab, phrase
    growth = INDEXING_GROWTH.read_text(encoding="utf-8")
    assert "Trustees average-wage growth" not in growth
    assert "PolicyEngine National Average Wage Index growth" in growth


def test_dashboard_methodology_uses_reader_names() -> None:
    for path in DASHBOARD_METHODOLOGY:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bOptions? \d", text), path.name
        assert not re.search(r"\b(H5|TOB)\b", text), path.name


def test_each_reform_code_appears_once_in_the_section_that_defines_it() -> None:
    design = "paper/sections/02-policy-design.qmd"
    counts: dict[str, int] = {}
    for name, text in paper_texts().items():
        codes = REFORM_CODE.findall(text)
        if name != design:
            assert not codes, (name, sorted(set(codes)))
        for code in codes:
            counts[code] = counts.get(code, 0) + 1
    assert counts == {reform: 1 for reform in headline.REFORM_LABELS}


def test_every_reform_has_one_table_name_and_one_prose_name() -> None:
    assert set(exhibits.PROSE_NAMES) == set(headline.REFORM_LABELS)
    assert set(exhibits.STANDARD_REFORMS) == set(headline.REFORM_LABELS)


def test_paper_sets_no_figure_in_code_font() -> None:
    for name, text in paper_texts().items():
        assert not NUMBER_IN_CODE_FONT.search(text), (
            name,
            NUMBER_IN_CODE_FONT.search(text).group(0),
        )


def test_no_exhibit_dollar_sign_can_close_math() -> None:
    for path in sorted((SECTIONS / "exhibits").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("|"):
                assert not re.search(r"(?<!\\)\$", line), (path.name, line)
            assert not re.search(r"(?<!\\)\$(?!\d)", line), (path.name, line)


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

    def first_loss(series: pd.Series) -> int:
        """The year a series turns negative, after gains in every earlier year."""
        series = series.sort_index()
        year = int(series[series < 0].index.min())
        assert (series.loc[: year - 1] > 0).all()
        assert (series.loc[year:] < 0).all()
        return year

    def first_losses(reform: str) -> set[int]:
        """The first loss by each measure: the income-tax change and the fund sum."""
        rows = static[static["reform_name"] == reform].set_index("year")
        return {
            first_loss(rows["revenue_impact"]),
            first_loss(rows["oasdi_net_impact"] + rows["hi_net_impact"]),
        }

    assert first_losses("option5") <= set(range(2053, 2057))
    assert "from the mid-2050s for the immediate" in abstract
    assert first_losses("option12") == {2060}
    assert "from 2060 for the phased" in abstract

    anchor_years = {item["year"] for item in run_record()["baselines"]}
    assert (
        f"project to {len(anchor_years)} years from {min(anchor_years)} to "
        f"{max(anchor_years)}"
    ) in abstract


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
        f"by ${ten_year_gaps[0]:.1f} billion for the Roth swap, "
        f"${ten_year_gaps[1]:.1f} billion for the phased Roth swap, and "
        f"${ten_year_gaps[2]:.1f} billion for the short phase-in Roth"
    ) in methods
    terminal = {
        round(gap(r, slice(2100, 2100)), 1) for r in ("option5", "option12", "option6")
    }
    assert len(terminal) == 1
    assert f"${terminal.pop():.1f} billion for each in 2100" in methods

    def straight(reform: str, year: int, start: int, end: int) -> float:
        low, high = cell(static, reform, start), cell(static, reform, end)
        return low + (high - low) * (year - start) / (end - start)

    understatement = cell(static, "option7", 2028) - straight(
        "option7", 2028, 2026, 2030
    )
    assert f"2028 impact by ${understatement:.1f} billion" in methods
    assert cell(static, "option7", 2029) == pytest.approx(0, abs=0.005)

    corner_gap = abs(
        straight("option5", 2062, 2060, 2065) - straight("option12", 2062, 2060, 2065)
    )
    assert f"put them ${corner_gap:.1f} billion apart" in methods
    for frame in (static, behavioral):
        assert cell(frame, "option5", 2062) == pytest.approx(
            cell(frame, "option12", 2062), abs=1e-6
        )


def test_solvency_figures_match_results() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    solvent = pd.read_csv(SOLVENCY_RESULTS)
    phased = solvent[solvent["reform_name"] == "option12"].set_index("year")

    def below_line(column: str) -> float:
        low, high = phased.loc[2050, column], phased.loc[2075, column]
        line = low + (high - low) * (2065 - 2050) / (2075 - 2050)
        return float(line - phased.loc[2065, column])

    oasdi, hi = below_line("oasdi_net_impact"), below_line("hi_net_impact")
    assert oasdi > 0 and hi > 0
    assert (
        f"OASDI and HI impacts run ${oasdi:.1f} billion and ${hi:.1f} billion below "
        "a straight line between 2050 and 2075"
    ) in methods


def test_solvency_rows_split_revenue_as_the_methods_state() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    solvent = pd.read_csv(SOLVENCY_RESULTS)
    exact = solvent[solvent["balanced_fix_result_type"].str.startswith("exact")]

    for reform in ("option1", "option2", "option8"):
        rows = exact[exact["reform_name"] == reform]
        assert len(rows) == 5, reform
        share = rows["baseline_tob_oasdi"] / (
            rows["baseline_tob_oasdi"] + rows["baseline_tob_medicare_hi"]
        )
        assert (
            rows["solvent_oasdi_impact"] - rows["revenue_impact"] * share
        ).abs().max() < 1e-6
        assert rows["solvent_general_fund_impact"].abs().max() < 1e-6

    phased = exact[exact["reform_name"] == "option12"]
    assert len(phased) == 5
    assert (
        phased["solvent_oasdi_impact"] - phased["oasdi_net_impact"]
    ).abs().max() < 1e-6
    assert (
        phased["solvent_medicare_hi_impact"] - phased["hi_net_impact"]
    ).abs().max() < 1e-6
    assert phased["solvent_general_fund_impact"].abs().max() > 1

    components = solvent[
        [
            "solvent_oasdi_impact",
            "solvent_medicare_hi_impact",
            "solvent_general_fund_impact",
        ]
    ].sum(axis=1)
    assert (components - solvent["revenue_impact"]).abs().max() < 1e-6

    for phrase in (
        "For full repeal, 85 percent taxation, and 100 percent taxation, we split "
        "revenue by baseline trust-fund shares.",
        "For the phased Roth swap, we credit each fund under the rules in "
        "@sec-swap-accounting and assign the rest of the revenue impact to the "
        "general fund.",
        "The components of every row sum to the total.",
    ):
        assert phrase in methods, phrase


def test_methods_state_the_default_split_for_each_reform() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    rules = headline.load_allocation_rules()
    net_impact = {*rules["directBranchingOptions"], *rules["netImpactOptions"]}
    shares = {*rules["baselineShareOptions"], *rules["allocationEligibleOptions"]}
    assert net_impact == set(exhibits.SWAP_REFORMS)
    assert shares == (
        set(exhibits.STANDARD_REFORMS) - net_impact - {"option7", "reverse_roth"}
    )

    row = {
        "revenue_impact": "10",
        "oasdi_net_impact": "7",
        "hi_net_impact": "4",
        "baseline_tob_oasdi": "3",
        "baseline_tob_medicare_hi": "1",
        "tob_oasdi_impact": "2",
        "tob_medicare_hi_impact": "1",
    }

    def split(reform: str) -> tuple[float, float, float, float]:
        return headline.default_split({**row, "reform_name": reform})

    assert split("option2") == (10, 7.5, 2.5, 0)
    assert split("option5") == (11, 7, 4, 0)
    assert split("option12") == (11, 7, 4, 0)
    assert split("option7") == (10, 2, 1, 7)
    assert split("reverse_roth") == (10, 9, 1, 0)

    for phrase in (
        "we divide revenue between OASDI and HI by each fund's share of baseline "
        "benefit-tax revenue",
        "so we add the two funds' net impacts",
        "we credit each fund with its taxation-of-benefits change and assign the "
        "rest to the general fund",
        "we credit HI with its benefit-tax change as the model scores it and charge "
        "OASDI with the rest of the revenue impact",
    ):
        assert phrase in methods, phrase


def test_labor_supply_methods_match_the_scored_reforms_and_anchors(
    behavioral: pd.DataFrame,
) -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    scored = set(behavioral["reform_name"])
    assert set(exhibits.MENU_REFORMS) - scored == {"magi100", "tax_panel_2005"}
    assert len(set(exhibits.MENU_REFORMS) & scored) == 13
    assert set(exhibits.SENSITIVITY_REFORMS) <= scored
    assert (
        "thirteen of the fifteen reforms, all but full MAGI inclusion and the 2005 "
        "Tax Panel deduction, and for the short phase-in Roth"
    ) in methods
    assert (
        "we simulate 2026 and 2100, plus 2062 for the Roth swap and the phased Roth "
        "swap and 2033 for the short phase-in Roth"
    ) in methods

    exact = behavioral[
        behavioral["full_h5_result_type"].isin(provenance.EXACT_RESULT_TYPES)
    ]
    extra = {"option5": {2062}, "option12": {2062}, "option6": {2033}}
    for reform, rows in exact.groupby("reform_name"):
        assert set(rows["year"]) == {2026, 2100} | extra.get(reform, set()), reform


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


def test_income_tax_share_of_gdp_matches_validation(static: pd.DataFrame) -> None:
    validation = flat((SECTIONS / "05-validation.qmd").read_text(encoding="utf-8"))
    gdp = pd.read_csv(ECONOMIC_PROJECTIONS).set_index("year")["gdp"]
    baseline = static[static["reform_name"] == "option1"].set_index("year")[
        "baseline_revenue"
    ]
    share = 100 * baseline / gdp.reindex(baseline.index)
    assert share.notna().all()
    low, high = round(share.min()), round(share.max())
    assert f"about {low} to {high} percent of GDP" in validation


def dataset_audits() -> dict[int, dict]:
    audits = {}
    for path in sorted(DATASET_METADATA.glob("*.h5.metadata.json")):
        year = int(path.name.split(".")[0])
        audits[year] = json.loads(path.read_text(encoding="utf-8"))
    assert set(FAR_HORIZON_YEARS) <= set(audits)
    return audits


def test_published_datasets_calibrate_exactly_and_add_no_records() -> None:
    for year, metadata in dataset_audits().items():
        assert metadata["calibration_audit"]["calibration_quality"] == "exact", year
        assert metadata["sentinel"]["donor_clone_household_count"] == 0, year


def test_methods_state_the_age_groups_the_projection_used() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    for year, metadata in dataset_audits().items():
        assert metadata["profile"]["age_bucket_size"] == 5, year
    columns = 85 // 5 + 1
    assert (
        f"has {columns} columns: five-year groups from 0-4 through 80-84 and a "
        "top-coded 85+ group"
    ) in methods


def test_methods_state_what_the_growth_cap_reached() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    capped: set[str] = set()
    for year, metadata in dataset_audits().items():
        factors = metadata.get("longrun_growth_caps") or {}
        assert all(0 < factor <= 1 for factor in factors.values()), year
        if year <= 2034:
            assert not factors, year
        capped |= set(factors)
    assert capped == {
        "non_qualified_dividend_income",
        "partnership_s_corp_income",
        "qualified_bdc_income",
        "qualified_dividend_income",
        "qualified_reit_and_ptp_income",
    }
    assert (
        "In our projections, we scale down only dividends, the investment income "
        "that shares their index, and partnership and S-corporation income."
    ) in methods

    diagnostics = pd.read_csv(DIAGNOSTICS).set_index("year")

    def growth(column: str) -> float:
        return float(diagnostics.loc[2100, column] / diagnostics.loc[2035, column])

    assert (
        "from 2035 to 2100, we project partnership and S-corporation income to grow "
        f"{growth('partnership_s_corp_income'):.1f}-fold, against "
        f"{growth('gdp'):.1f}-fold for the Trustees' GDP path"
    ) in methods


def test_methods_state_the_income_the_value_scalar_moves() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    gains = "short-term and non-Schedule-D capital gains"
    retirement = "pension and IRA income"
    rents = "rental and farm-rent income"
    named = {
        "taxable_interest_income": "interest",
        "tax_exempt_interest_income": "interest",
        "qualified_dividend_income": "dividends",
        "non_qualified_dividend_income": "dividends",
        "short_term_capital_gains": gains,
        "non_sch_d_capital_gains": gains,
        "taxable_ira_distributions": retirement,
        "taxable_pension_income": retirement,
        "tax_exempt_pension_income": retirement,
        "rental_income": rents,
        "farm_rent_income": rents,
        "estate_income": "estate income",
        "partnership_s_corp_income": "partnership and S-corporation income",
        "miscellaneous_income": "miscellaneous income",
    }
    for year, metadata in dataset_audits().items():
        columns = metadata["value_scaling"]["other_income_columns"]
        assert {column.removesuffix(f"__{year}") for column in columns} == set(named)
    for phrase in set(named.values()):
        assert phrase in methods, phrase


def test_methods_state_the_parameters_the_baseline_indexes_to_wages() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    assumption = json.loads(BASELINE_ASSUMPTIONS.read_text(encoding="utf-8"))[
        "tax_assumption"
    ]
    assert assumption["parameter_groups"] == ["all_gov_irs_uprating_parameters"]
    assert assumption["uprating_parameter"] == "gov.irs.uprating"
    assert assumption["wage_index"] == "gov.ssa.nawi"
    assert assumption["start_year"] == 2035
    assert "May 6, 2026" in assumption["source"]
    for year, metadata in dataset_audits().items():
        assert metadata["tax_assumption"]["start_year"] == 2035, year

    assert "From 2035, we therefore index to wages every federal income-tax" in methods
    assert "credit amounts such as the child tax credit" in methods
    assert "May 5 and May 6, 2026" in methods


def test_methods_state_the_wage_path_behind_the_indexed_parameters() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    parameters = pd.read_csv(INDEXED_PARAMETERS)
    bracket = parameters[
        parameters["parameter_name"] == "gov.irs.income.bracket.thresholds.1.JOINT"
    ].set_index("year")["value"]
    wages = pd.read_csv(TRUSTEES_AUX).set_index("year")["average_wage_index"]

    # A parameter for year y follows the wage index for year y - 1.
    model_growth = bracket[2100] / bracket[2034]
    trustees_growth = wages[2099] / wages[2033]
    implied = bracket[2034] * trustees_growth

    assert f"about {model_growth:.1f}-fold from 2033 to 2099" in methods
    assert f"against about {trustees_growth:.1f}-fold" in methods
    assert f"${bracket[2100]:,.0f} in 2100" in methods
    assert f"${round(implied, -2):,.0f} that Trustees wage growth implies" in methods
    assert f"about {100 * (1 - bracket[2100] / implied):.0f} percent below" in methods


def test_far_horizon_support_figures_match_dataset_metadata() -> None:
    validation = flat((SECTIONS / "05-validation.qmd").read_text(encoding="utf-8"))
    audits = dataset_audits()

    def ess(year: int, fund: str) -> float:
        contributors = audits[year]["calibration_audit"]["contributors"]
        return float(contributors[fund]["contributor_effective_sample_size"])

    for fund, label in (("oasdi_tob", "OASDI"), ("hi_tob", "HI")):
        values = [ess(year, fund) for year in FAR_HORIZON_YEARS]
        assert min(values) >= SUPPORT_FLOOR
        assert f"{round(min(values))}-{round(max(values))} for {label}" in validation
        assert f"{round(ess(2100, fund))} for {label}" in validation
    assert f"floor of {SUPPORT_FLOOR}" in validation
    top_10 = audits[2100]["calibration_audit"]["top_10_weight_share_pct"]
    assert f"{top_10:.1f}% of the total weight" in validation


def run_record() -> dict:
    return json.loads(provenance.OUTPUT.read_text(encoding="utf-8"))


def results_contract() -> dict:
    return json.loads(provenance.RESULTS_CONTRACT.read_text(encoding="utf-8"))


def manifests() -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(MANIFESTS.glob("*.json"))
    }


def manifest_hash(manifest: dict, year: int) -> str:
    records = [item for item in manifest["datasets"] if item["year"] == year]
    assert len(records) == 1, year
    return records[0]["h5_sha256"]


def gate_failures(metrics: dict, gates: dict) -> list[str]:
    failures = []
    for metric, (direction, bound) in gates.items():
        value = metrics[metric]
        if (direction == "min" and value < bound) or (
            direction == "max" and value > bound
        ):
            failures.append(f"{metric}={value} against {direction} {bound}")
    return failures


def test_run_record_covers_every_exact_row() -> None:
    record = run_record()
    results = pd.read_csv(exhibits.RESULTS_CSV)
    summary = provenance.results_summary(results)

    assert record["schema"] == provenance.SCHEMA
    assert {run["run_prefix"] for run in record["runs"]} == set(summary)
    for run in record["runs"]:
        for field, value in summary[run["run_prefix"]].items():
            assert run[field] == value, (run["run_prefix"], field)
    assert record["exact_rows"] == len(provenance.exact_rows(results))
    assert record["exact_rows"] == sum(run["exact_rows"] for run in record["runs"])


def test_every_run_used_the_stated_versions_and_checked_its_baseline() -> None:
    for run in run_record()["runs"]:
        packages = run["packages"]
        assert packages["policyengine-us"] == "1.700.2", run["run_prefix"]
        assert packages["policyengine"] == "4.5.1", run["run_prefix"]
        assert packages["policyengine-core"] == "3.26.1", run["run_prefix"]
        assert run["baseline_manifest_checked_rows"] == run["exact_rows"]
        assert run["worker_entrypoint"].endswith("run_reform_full_h5_cell")
        assert run["tax_assumption"] == "trustees-2025-core-thresholds-v1"


def test_data_and_code_section_matches_the_run_record() -> None:
    text = (SECTIONS / "06-data-and-code.qmd").read_text(encoding="utf-8")
    section = flat(text)
    record = run_record()
    runs = record["runs"]
    labor_supply = [run for run in runs if run["scoring_type"] == "behavioral"]

    assert f"Each of the {record['exact_rows']} exact rows" in section
    assert len(runs) == 10 and "in ten runs" in section
    assert len(labor_supply) == 2 and "The two labor-supply runs" in section
    assert "`policyengine-us` 1.700.2" in section
    assert "`policyengine.py` 4.5.1" in section
    assert "`policyengine-core` 3.26.1" in section

    linked = REPO_FILE_LINK.findall(text)
    assert {
        "docs/current/run-provenance.json",
        "docs/current/patches/policyengine-core-3.26.1-delete-arrays.patch",
    } <= set(linked)
    for path in linked:
        assert (REPO_ROOT / path).is_file(), path
    patch = (
        REPO_ROOT / "docs/current/patches/policyengine-core-3.26.1-delete-arrays.patch"
    ).read_text(encoding="utf-8")
    assert "policyengine_core/simulations/simulation.py" in patch
    assert "holder.delete_arrays(period, _branch_name)" in patch


def test_every_baseline_calibrates_exactly_and_clears_every_gate() -> None:
    baselines = run_record()["baselines"]
    years = {item["year"] for item in baselines}
    assert len(years) == 21

    for item in baselines:
        label = (item["year"], item["h5_sha256"][:8])
        assert item["calibration_quality"] == "exact", label
        assert item["validation_passed"] is True, label
        assert item["gates_passed"] is True, label
        assert item["donor_clone_households"] == 0, label
        assert not gate_failures(item, WEIGHT_GATES), label
        for name, gates in CONTRIBUTOR_GATES.items():
            assert not gate_failures(item["contributors"][name], gates), (label, name)

    largest_error_pct = 100 * max(
        item["max_constraint_error_fraction"] for item in baselines
    )
    assert largest_error_pct <= 0.000001

    validation = flat((SECTIONS / "05-validation.qmd").read_text(encoding="utf-8"))
    assert f"All {len(years)} anchor years" in validation
    assert "by more than 0.000001%" in validation

    def lowest(name: str) -> int:
        return math.floor(
            min(
                item["contributors"][name]["contributor_effective_sample_size"]
                for item in baselines
            )
        )

    assert (
        f"never fall below {lowest('oasdi_tob')} for OASDI "
        f"and {lowest('hi_tob')} for HI"
    ) in validation


def test_methods_state_the_gates_that_built_the_baselines() -> None:
    methods = flat((SECTIONS / "03-methods.qmd").read_text(encoding="utf-8"))
    limits = {metric: bound for metric, (_, bound) in TOB_CONTRIBUTOR_GATES.items()}

    for phrase in (
        f"at least {limits['positive_contributor_count']:,} positive contributors",
        "effective sample size of at least "
        f"{limits['contributor_effective_sample_size']:.0f}",
        f"top-10 contribution share of at most "
        f"{limits['top_10_contribution_share_pct']:.0f}%",
        f"top-100 share of at most {limits['top_100_contribution_share_pct']:.0f}%",
        "largest single-contributor share of at most "
        f"{limits['max_contribution_share_pct']:.0f}%",
        "from 2075",
    ):
        assert phrase in methods, phrase


def test_reform_scoring_claims_count_the_exact_rows() -> None:
    validation = flat((SECTIONS / "05-validation.qmd").read_text(encoding="utf-8"))
    assert f"each of the {run_record()['exact_rows']} exact rows" in validation


def test_results_contract_traces_every_row() -> None:
    contract = results_contract()["results"]
    results = pd.read_csv(exhibits.RESULTS_CSV)
    assert len(contract) == len(results)

    published = {
        (row.reform_name, row.scoring_type, int(row.year)): row
        for row in provenance.exact_rows(results).itertuples()
    }
    baselines = {item["h5_sha256"]: item["year"] for item in run_record()["baselines"]}
    exact_years: dict[tuple[str, str], list[int]] = {}
    for reform, scoring_type, year in published:
        exact_years.setdefault((reform, scoring_type), []).append(year)

    exact_seen = 0
    for item in contract:
        lineage = item["lineage"]
        key = (item["reform"], item["scoring_type"], int(item["year"]))
        if item["result_type"] in provenance.EXACT_RESULT_TYPES:
            exact_seen += 1
            row = published[key]
            assert lineage["scenario_h5_sha256"] == row.output_h5_sha256, key
            assert lineage["run_prefix"] == row.run_prefix, key
            assert baselines[lineage["baseline_year_h5_sha256"]] == key[2], key
            assert lineage["interpolated_between"] is None, key
        else:
            low, high = lineage["interpolated_between"]
            years = exact_years[key[:2]]
            assert low == max(year for year in years if year < key[2]), key
            assert high == min(year for year in years if year > key[2]), key
    assert exact_seen == len(published)


def test_every_baseline_appears_in_a_committed_manifest() -> None:
    committed = {
        (item["year"], item["h5_sha256"])
        for manifest in manifests().values()
        for item in manifest["datasets"]
    }
    for item in run_record()["baselines"]:
        assert (item["year"], item["h5_sha256"]) in committed, item["year"]


def test_baselines_trace_to_the_stated_build_commits() -> None:
    section = flat((SECTIONS / "06-data-and-code.qmd").read_text(encoding="utf-8"))
    assert "commits `3de8abb6` and `c5e4f1a6`" in section

    builders = {
        (item["year"], item["h5_sha256"]): manifest["source_sha"][:8]
        for manifest in manifests().values()
        for item in manifest["datasets"]
    }
    used = {
        builders[(item["year"], item["h5_sha256"])]
        for item in run_record()["baselines"]
    }
    assert used == {"3de8abb6", "c5e4f1a6"}

    published = manifests()["baseline-dataset-manifest-v2pop.json"]
    infill = manifests()["baseline-dataset-manifest-9f1260b-certinfill.json"]
    for manifest in (published, infill):
        assert manifest["source_sha"].startswith("3de8abb6")
    assert manifest_hash(infill, 2030) == manifest_hash(published, 2030)

    baseline_hashes = {
        item["year"]: item["h5_sha256"]
        for item in run_record()["baselines"]
        if item["year"] in (2026, 2028, 2029, 2030)
    }
    assert baseline_hashes[2026] == manifest_hash(published, 2026)
    assert baseline_hashes[2030] == manifest_hash(published, 2030)
    assert baseline_hashes[2028] == manifest_hash(infill, 2028)
    assert baseline_hashes[2029] == manifest_hash(infill, 2029)


def provenance_fixture() -> tuple[SimpleNamespace, dict, dict]:
    """One exact row with the metadata and contract entry that agree with it."""
    row = SimpleNamespace(
        run_prefix="run",
        year=2030,
        reform_name="option1",
        scoring_type="static",
        output_h5_sha256="reform-hash",
    )
    audit = {
        "calibration_audit": {
            "calibration_quality": "exact",
            "validation_passed": True,
            "max_constraint_pct_error": 1e-9,
            "positive_weight_count": 5_000,
            "effective_sample_size": 1_500.0,
            "top_10_weight_share_pct": 3.0,
            "top_100_weight_share_pct": 16.0,
            "contributors": {},
        },
        "sentinel": {"gates_passed": True, "donor_clone_household_count": 0},
    }
    metadata = {
        "run_prefix": "run",
        "year": 2030,
        "reform_id": "option1",
        "scoring_type": "static",
        "output_h5_sha256": "reform-hash",
        "dataset_h5_sha256": "baseline-hash",
        "full_reform_output_h5_saved": True,
        "manual_weight_aggregation_used": False,
        "baseline_dataset_validation": {
            "validated": True,
            "dataset_sha256": "baseline-hash",
            "metadata_validation": {"metadata": audit},
        },
    }
    contract_row = {
        "lineage": {
            "scenario_h5_sha256": "reform-hash",
            "baseline_year_h5_sha256": "baseline-hash",
        }
    }
    return row, metadata, contract_row


def test_row_check_passes_when_the_records_agree() -> None:
    assert provenance.row_disagreements(*provenance_fixture()) == []


@pytest.mark.parametrize(
    ("field", "value", "named"),
    [
        ("run_prefix", "other", ["run prefix"]),
        ("year", 2031, ["year"]),
        ("reform_id", "option2", ["reform"]),
        ("scoring_type", "behavioral", ["scoring type"]),
        (
            "output_h5_sha256",
            "other",
            ["reform H5 hash in results", "reform H5 hash in contract"],
        ),
        (
            "dataset_h5_sha256",
            "other",
            ["baseline H5 hash in contract", "baseline manifest check"],
        ),
        ("full_reform_output_h5_saved", False, ["saved reform H5"]),
        ("manual_weight_aggregation_used", True, ["weighted aggregation"]),
    ],
)
def test_row_check_names_each_disagreement(
    field: str, value: object, named: list[str]
) -> None:
    row, metadata, contract_row = provenance_fixture()
    metadata[field] = value
    assert provenance.row_disagreements(row, metadata, contract_row) == named


def test_row_check_catches_a_failed_manifest_check() -> None:
    row, metadata, contract_row = provenance_fixture()
    metadata["baseline_dataset_validation"]["validated"] = False
    assert provenance.row_disagreements(row, metadata, contract_row) == [
        "baseline manifest check"
    ]


def test_run_summary_refuses_two_values_for_one_run() -> None:
    assert provenance.one_value(["1.700.2", "1.700.2"], "version", "run") == "1.700.2"
    with pytest.raises(ValueError, match="expected one version"):
        provenance.one_value(["1.700.2", "1.701.0"], "version", "run")


def test_baseline_figures_allow_only_last_digit_noise() -> None:
    figures = {"gates_passed": True, "ess": 135.29197715148172, "nested": {"top": 2.5}}
    noisy = {"gates_passed": True, "ess": 135.2919771514817, "nested": {"top": 2.5}}
    assert provenance.figures_agree(figures, noisy)
    assert not provenance.figures_agree(figures, {**figures, "gates_passed": False})
    assert not provenance.figures_agree(figures, {**figures, "ess": 135.4})
    assert not provenance.figures_agree(figures, {**figures, "nested": {"top": 2.6}})
    assert not provenance.figures_agree(figures, {"gates_passed": True})


def complete_fixture() -> tuple[pd.DataFrame, dict, dict]:
    """A one-row results file, contract, and metadata file that `build` accepts."""
    row, metadata, contract_row = provenance_fixture()
    results = pd.DataFrame(
        [
            {
                "run_prefix": row.run_prefix,
                "year": row.year,
                "reform_name": row.reform_name,
                "scoring_type": row.scoring_type,
                "output_h5_sha256": row.output_h5_sha256,
                "full_h5_result_type": "exact_full_h5",
            }
        ]
    )
    contract_row["lineage"]["run_prefix"] = row.run_prefix
    contract = {
        "results": [
            {
                "year": row.year,
                "reform": row.reform_name,
                "scoring_type": row.scoring_type,
                "result_type": "exact_full_h5",
                **contract_row,
            }
        ]
    }
    metadata.update(
        created_at="2026-07-23T00:00:00Z",
        worker_entrypoint="src.reform_full_h5_worker.run_reform_full_h5_cell",
        tax_assumption={"name": "trustees-2025-core-thresholds-v1"},
        expected_schema_validation=None,
        runtime_provenance={
            "submitter_runtime_fingerprint": None,
            "python": {"version": "3.13.9 (main)"},
            "packages": {"policyengine-us": "1.700.2"},
            "pip_freeze": {"available": False},
        },
    )
    return results, contract, metadata


def test_build_writes_one_run_and_one_baseline() -> None:
    results, contract, metadata = complete_fixture()
    record = provenance.build(results, contract, lambda row: metadata)

    assert record["exact_rows"] == 1
    assert [run["run_prefix"] for run in record["runs"]] == ["run"]
    run = record["runs"][0]
    assert run["environment"] == "local"
    assert run["python"] == "3.13.9"
    assert run["baseline_manifest_checked_rows"] == 1
    assert run["expected_schema_checked_rows"] == 0
    assert [item["h5_sha256"] for item in record["baselines"]] == ["baseline-hash"]


def test_build_stops_on_a_metadata_disagreement() -> None:
    results, contract, metadata = complete_fixture()
    metadata["output_h5_sha256"] = "other"
    with pytest.raises(ValueError, match="reform H5 hash in results"):
        provenance.build(results, contract, lambda row: metadata)


def test_committed_run_record_carries_no_local_paths() -> None:
    assert "/Users/" not in provenance.OUTPUT.read_text(encoding="utf-8")
