"""Build per-reform, per-year distributional impact by income decile.

For each anchor year we run one baseline simulation to get each household's
baseline net income and income decile, then diff every reform's saved
reform-output H5 (already cached locally from the aggregation runs) against
that baseline by household. The result is the average and percentage change
in household net income within each baseline income decile.

All weighting goes through MicroSeries/MicroDataFrame. The script never fetches
PolicyEngine weight variables directly; weights are carried from the calculated
baseline MicroSeries into the joined distributional table.

Usage:
    uv run python scripts/build_distributional_data.py \
        --output dashboard/public/data/distributional.json
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
from pathlib import Path

import microdf as mdf
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BASELINE_DIR = REPO / "projected_datasets_v2pop"
ANCHOR_YEARS = [2026, 2028, 2029, 2030] + list(range(2035, 2101, 5))

# Reforms scored on the certified-reproduction environment pair with
# baselines from the SAME datasets (exported per-household by the
# crfb-cert/tmp export scripts), per the same-family rule in
# docs/current/magi100-provenance.md. Through 2070 that is the certrepro
# rebuild; from 2075 both reforms were rescored on the published no-clone
# far-horizon datasets (docs/current/tax-panel-2005-provenance.md, the
# 2070->2075 seam fix), so the far years pair with no-clone exports.
NOCLONE_START_YEAR = 2075
CERTREPRO_PREFIXES = {
    "magi100": "magi100_certrepro_20260706",
    "tax_panel_2005": "tax_panel_2005_certrepro_20260717",
}
CERTREPRO_CELL_ROOTS = {
    "magi100": REPO / "tmp" / "full_h5_magi100",
    "tax_panel_2005": REPO / "tmp" / "full_h5_tax_panel_2005",
}
NOCLONE_FARFIX_PREFIX = "noclone_farfix_20260722"
NOCLONE_FARFIX_ROOT = REPO / "tmp" / "full_h5_noclone_farfix"
CERTREPRO_BASELINE_DIR = (
    REPO.parent / "crfb-cert" / "tmp" / "baseline_households_certrepro"
)
NOCLONE_BASELINE_DIR = REPO.parent / "crfb-cert" / "tmp" / "baseline_households_noclone"
REFORMS = (
    [f"option{i}" for i in range(1, 13)]
    + ["reverse_roth", "tax93"]
    + sorted(CERTREPRO_PREFIXES)
)

# The reform-output H5s were cached locally by the aggregation runs. Static
# 2026-2070 live under the original prefix cache; 2075-2100 under the no-clone
# cache. Each entry maps a year to (cache_root, run_prefix).
STATIC_CACHE = REPO / "tmp" / "reform_full_h5_r2_cache_v2pop"
NOCLONE_CACHE = REPO / "tmp" / "r2_cache_noclone"


def scenario_path(year: int, reform: str) -> Path:
    if reform in CERTREPRO_PREFIXES:
        if year >= NOCLONE_START_YEAR:
            root = NOCLONE_FARFIX_ROOT
            prefix = NOCLONE_FARFIX_PREFIX
        else:
            root = CERTREPRO_CELL_ROOTS[reform]
            prefix = CERTREPRO_PREFIXES[reform]
        return (
            root
            / prefix
            / "reform_full_h5"
            / f"year={year}"
            / f"reform={reform}"
            / "scenario.h5"
        )
    if year <= 2070:
        return (
            STATIC_CACHE
            / "axiom-corpus/crfb/reform_full_h5/v2pop_tr2026_20260611"
            / "reform_full_h5"
            / f"year={year}"
            / f"reform={reform}"
            / "scenario.h5"
        )
    return (
        NOCLONE_CACHE
        / "axiom-corpus/crfb/reform_full_h5/v2pop_tr2026_noclone_20260612"
        / "reform_full_h5"
        / f"year={year}"
        / f"reform={reform}"
        / "scenario.h5"
    )


def baseline_households(year: int) -> pd.DataFrame:
    """Baseline household net income + weighted decile, by household_id."""
    from policyengine_us import Microsimulation

    from src.pipeline import _tax_assumption_reform

    sim = Microsimulation(
        dataset=str(BASELINE_DIR / f"{year}.h5"),
        reform=_tax_assumption_reform(year),
    )
    hh_id = sim.calc("household_id", period=year).reset_index(drop=True)
    net = sim.calc("household_net_income", period=year)
    weights = net.weights.reset_index(drop=True)
    net = net.reset_index(drop=True)
    frame = mdf.MicroDataFrame(
        {
            "household_id": pd.Series(hh_id).reset_index(drop=True),
            "baseline_net_income": pd.Series(net).reset_index(drop=True),
        },
        weights=weights,
    )
    # Population-weighted income deciles on baseline household net income.
    frame["decile"] = frame["baseline_net_income"].decile_rank().astype(int)
    del sim
    gc.collect()
    return frame


def certrepro_baseline_households(year: int) -> pd.DataFrame:
    """Same-family baseline for certrepro-scored reforms, from the exported
    per-household CSVs (certified worktree, policyengine-us 1.700.2)."""
    directory = (
        NOCLONE_BASELINE_DIR if year >= NOCLONE_START_YEAR else CERTREPRO_BASELINE_DIR
    )
    path = directory / f"{year}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} — run crfb-cert/tmp/export_baseline_households.py {year}"
        )
    raw = pd.read_csv(path)
    frame = mdf.MicroDataFrame(
        {
            "household_id": raw["household_id"].reset_index(drop=True),
            "baseline_net_income": raw["baseline_net_income"].reset_index(drop=True),
        },
        weights=raw["weight"].reset_index(drop=True),
    )
    frame["decile"] = frame["baseline_net_income"].decile_rank().astype(int)
    return frame


def reform_net_income(year: int, reform: str) -> pd.DataFrame:
    path = scenario_path(year, reform)
    if not path.exists():
        raise FileNotFoundError(path)
    with pd.HDFStore(path, mode="r") as store:
        hh = store["household"]
    return hh[["household_id", "household_net_income"]].rename(
        columns={"household_net_income": "reform_net_income"}
    )


def decile_impacts(baseline: pd.DataFrame, reform: pd.DataFrame) -> list[dict]:
    merged = baseline.merge(
        reform, on="household_id", how="inner", validate="one_to_one"
    )
    merged["change"] = merged["reform_net_income"] - merged["baseline_net_income"]
    rows: list[dict] = []
    for decile in range(1, 11):
        group = merged.loc[merged["decile"] == decile]
        if group.empty:
            rows.append(
                {
                    "decile": decile,
                    "avg_change": 0.0,
                    "pct_change": None,
                    "total_change_billions": 0.0,
                }
            )
            continue
        total_change = float(group["change"].sum())
        total_baseline = float(group["baseline_net_income"].sum())
        avg_change = float(group["change"].mean())
        rows.append(
            {
                "decile": decile,
                "avg_change": round(avg_change, 2),
                # A percentage change is only meaningful when the decile's
                # aggregate baseline net income is positive. The bottom decile
                # can be negative (business losses, etc.), where dividing by it
                # flips the sign and fabricates an outlier, so suppress it.
                "pct_change": round(100.0 * total_change / total_baseline, 3)
                if total_baseline > 0
                else None,
                "total_change_billions": round(total_change / 1e9, 3),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "dashboard" / "public" / "data" / "distributional.json",
    )
    parser.add_argument("--years", default=None, help="Comma list; default all anchors")
    parser.add_argument(
        "--reforms",
        default=None,
        help=(
            "Comma list; default all. Other reforms' entries in an existing "
            "output file are preserved (per-reform merge)."
        ),
    )
    args = parser.parse_args()

    years = [int(y) for y in args.years.split(",")] if args.years else ANCHOR_YEARS
    reforms = args.reforms.split(",") if args.reforms else list(REFORMS)
    unknown = sorted(set(reforms) - set(REFORMS))
    if unknown:
        raise SystemExit(f"unknown reforms: {unknown}")

    data: dict[str, dict] = {reform: {} for reform in REFORMS}
    if args.output.exists():
        existing = json.loads(args.output.read_text())
        for reform, by_year in existing.get("data", {}).items():
            data.setdefault(reform, {}).update(by_year)

    for year in years:
        baselines: dict[str, pd.DataFrame] = {}

        def baseline_for(reform: str) -> pd.DataFrame:
            family = "certrepro" if reform in CERTREPRO_PREFIXES else "published"
            if family not in baselines:
                print(f"baseline {year} ({family})…", flush=True)
                baselines[family] = (
                    certrepro_baseline_households(year)
                    if family == "certrepro"
                    else baseline_households(year)
                )
            return baselines[family]

        for reform in reforms:
            try:
                reform_frame = reform_net_income(year, reform)
            except FileNotFoundError:
                print(f"  {reform} {year}: scenario missing, skipping", file=sys.stderr)
                continue
            data[reform][str(year)] = decile_impacts(baseline_for(reform), reform_frame)
        print(
            f"  {year}: {sum(str(year) in data[r] for r in reforms)} reforms",
            flush=True,
        )
        baselines.clear()
        gc.collect()

    # The header must describe the merged artifact, not this invocation: a
    # per-reform merge run with a year subset previously clobbered the
    # header and hid 2028/2029 anchors from the dashboard's interpolation.
    merged_years = sorted(
        {int(year) for by_year in data.values() for year in by_year}
    )
    payload = {
        "schema": "crfb_distributional/v1",
        "metric": "change in household net income by baseline income decile",
        "anchor_years": merged_years,
        "reforms": REFORMS,
        "note": (
            "Deciles rank households by baseline net income. avg_change is the "
            "mean dollar change in net income per household in the decile; "
            "pct_change is the decile's aggregate net-income change as a "
            "percent of its baseline net income. Computed from saved reform "
            "microdata against a baseline simulation; anchor years only."
        ),
        "data": data,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
