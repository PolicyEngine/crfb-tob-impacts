from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RESULTS = REPO / "results"
PRIOR_REFERENCE = RESULTS / "oact_static_current.csv"
DASHBOARD_ALL_STATIC = REPO / "dashboard/public/data/all_static_results.csv"
DASHBOARD_ALL_STATIC_WITH_PRIOR_CSV = (
    REPO / "dashboard/public/data/all_static_results_with_prior_reference.csv"
)
DASHBOARD_ALL_STATIC_WITH_PRIOR_XLSX = (
    REPO / "dashboard/public/data/all_static_results_with_prior_reference.xlsx"
)
DASHBOARD_OPTION13 = REPO / "dashboard/public/data/option13_balanced_fix.csv"
STANDARD_RESULTS = (
    RESULTS / "trustees_modal_2026_2100_all_reforms_small_deployed_latesthf_stitched_billions.csv"
)
LATEST_SPECIAL_CASE_ROOT = (
    RESULTS
    / "recovered_special_case_runs"
    / "special_case_reruns__option13-14-exact-2035-2100-20260411"
)
DEFAULT_OPTION13_DIR = LATEST_SPECIAL_CASE_ROOT / "option13"
DEFAULT_OPTION14_DIR = LATEST_SPECIAL_CASE_ROOT / "option14"
DEFAULT_SPECIAL_START_YEAR = 2035
YEARS = list(range(2026, 2101))

OUT_COMBINED = RESULTS / "all_static_results_latesthf_2026_2100_14options.csv"
OUT_WITH_PRIOR_CSV = (
    RESULTS / "all_static_results_latesthf_2026_2100_14options_with_prior_reference.csv"
)
OUT_WITH_PRIOR_XLSX = (
    RESULTS / "all_static_results_latesthf_2026_2100_14options_with_prior_reference.xlsx"
)
OUT_METADATA = RESULTS / "all_static_results_latesthf_2026_2100_14options_metadata.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard-results", type=Path, default=STANDARD_RESULTS)
    parser.add_argument("--prior-reference", type=Path, default=PRIOR_REFERENCE)
    parser.add_argument("--option13-dir", type=Path, default=DEFAULT_OPTION13_DIR)
    parser.add_argument("--option14-dir", type=Path, default=DEFAULT_OPTION14_DIR)
    parser.add_argument("--special-start-year", type=int, default=DEFAULT_SPECIAL_START_YEAR)
    parser.add_argument("--special-manifest", type=Path, default=None)
    parser.add_argument("--dashboard-all-static", type=Path, default=DASHBOARD_ALL_STATIC)
    parser.add_argument(
        "--dashboard-with-prior-csv",
        type=Path,
        default=DASHBOARD_ALL_STATIC_WITH_PRIOR_CSV,
    )
    parser.add_argument(
        "--dashboard-with-prior-xlsx",
        type=Path,
        default=DASHBOARD_ALL_STATIC_WITH_PRIOR_XLSX,
    )
    parser.add_argument("--dashboard-option13", type=Path, default=DASHBOARD_OPTION13)
    parser.add_argument("--out-combined", type=Path, default=OUT_COMBINED)
    parser.add_argument("--out-with-prior-csv", type=Path, default=OUT_WITH_PRIOR_CSV)
    parser.add_argument("--out-with-prior-xlsx", type=Path, default=OUT_WITH_PRIOR_XLSX)
    parser.add_argument("--out-metadata", type=Path, default=OUT_METADATA)
    return parser.parse_args()


def load_standard(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.sort_values(["year", "reform_name"]).reset_index(drop=True)


def load_prior(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df.sort_values(["year", "reform_name"]).reset_index(drop=True)


def baseline_lookup(standard: pd.DataFrame) -> dict[int, dict]:
    baseline_cols = [
        "baseline_revenue",
        "baseline_tob_medicare_hi",
        "baseline_tob_oasdi",
        "baseline_tob_total",
        "scoring_type",
    ]
    lookup: dict[int, dict] = {}
    first_rows = (
        standard.sort_values(["year", "reform_name"]).groupby("year", as_index=False).first()
    )
    for row in first_rows.to_dict(orient="records"):
        lookup[int(row["year"])] = {col: row[col] for col in baseline_cols}
    return lookup


def standard_reform_lookup(standard: pd.DataFrame, reform_name: str) -> dict[int, dict]:
    rows = standard.loc[standard["reform_name"] == reform_name].copy()
    return {
        int(row["year"]): row
        for row in rows.sort_values("year").to_dict(orient="records")
    }


def load_raw_rows(path: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for csv in sorted(path.glob("*_static_results.csv")):
        raw = pd.read_csv(csv).iloc[0].to_dict()
        rows[int(raw["year"])] = raw
    return rows


def run_id_for(raw: dict, fallback: str) -> str:
    value = raw.get("special_case_run_id")
    if isinstance(value, str) and value:
        return value
    return fallback


def current_law_row(year: int, reform_name: str, baseline: dict, run_id: str) -> dict:
    return {
        "reform_name": reform_name,
        "year": year,
        "baseline_revenue": baseline["baseline_revenue"],
        "reform_revenue": baseline["baseline_revenue"],
        "revenue_impact": 0.0,
        "baseline_tob_medicare_hi": baseline["baseline_tob_medicare_hi"],
        "reform_tob_medicare_hi": baseline["baseline_tob_medicare_hi"],
        "tob_medicare_hi_impact": 0.0,
        "baseline_tob_oasdi": baseline["baseline_tob_oasdi"],
        "reform_tob_oasdi": baseline["baseline_tob_oasdi"],
        "tob_oasdi_impact": 0.0,
        "baseline_tob_total": baseline["baseline_tob_total"],
        "reform_tob_total": baseline["baseline_tob_total"],
        "tob_total_impact": 0.0,
        "scoring_type": baseline["scoring_type"],
        "employer_ss_tax_revenue": 0.0,
        "employer_medicare_tax_revenue": 0.0,
        "oasdi_gain": 0.0,
        "hi_gain": 0.0,
        "oasdi_loss": 0.0,
        "hi_loss": 0.0,
        "oasdi_net_impact": 0.0,
        "hi_net_impact": 0.0,
        "run_id": run_id,
    }


def option13_row(raw: dict, baseline: dict, fallback_run_id: str) -> dict:
    tob_hi_impact = raw["tob_hi_impact"] / 1e9
    tob_oasdi_impact = raw["tob_oasdi_impact"] / 1e9
    baseline_tob_hi = baseline["baseline_tob_medicare_hi"]
    baseline_tob_oasdi = baseline["baseline_tob_oasdi"]
    reform_tob_hi = baseline_tob_hi + tob_hi_impact
    reform_tob_oasdi = baseline_tob_oasdi + tob_oasdi_impact
    return {
        "reform_name": "option13",
        "year": int(raw["year"]),
        "baseline_revenue": raw["baseline_income_tax"] / 1e9,
        "reform_revenue": raw["reform_income_tax"] / 1e9,
        "revenue_impact": raw["income_tax_impact"] / 1e9,
        "baseline_tob_medicare_hi": baseline_tob_hi,
        "reform_tob_medicare_hi": reform_tob_hi,
        "tob_medicare_hi_impact": tob_hi_impact,
        "baseline_tob_oasdi": baseline_tob_oasdi,
        "reform_tob_oasdi": reform_tob_oasdi,
        "tob_oasdi_impact": tob_oasdi_impact,
        "baseline_tob_total": baseline_tob_oasdi + baseline_tob_hi,
        "reform_tob_total": reform_tob_oasdi + reform_tob_hi,
        "tob_total_impact": tob_oasdi_impact + tob_hi_impact,
        "scoring_type": "static",
        "employer_ss_tax_revenue": 0.0,
        "employer_medicare_tax_revenue": 0.0,
        "oasdi_gain": raw["rate_increase_ss_revenue"] / 1e9,
        "hi_gain": raw["rate_increase_hi_revenue"] / 1e9,
        "oasdi_loss": raw["tob_oasdi_loss"] / 1e9,
        "hi_loss": raw["tob_hi_loss"] / 1e9,
        "oasdi_net_impact": (
            raw["benefit_cut"] + raw["rate_increase_ss_revenue"] - raw["tob_oasdi_loss"]
        )
        / 1e9,
        "hi_net_impact": (raw["rate_increase_hi_revenue"] - raw["tob_hi_loss"]) / 1e9,
        "run_id": run_id_for(raw, fallback_run_id),
    }


def option14_row(option13: dict, option12_standard: dict, fallback_run_id: str) -> dict:
    baseline_tob_hi = option13["reform_tob_medicare_hi"]
    baseline_tob_oasdi = option13["reform_tob_oasdi"]
    reform_tob_hi = option12_standard["reform_tob_medicare_hi"]
    reform_tob_oasdi = option12_standard["reform_tob_oasdi"]
    tob_hi_impact = reform_tob_hi - baseline_tob_hi
    tob_oasdi_impact = reform_tob_oasdi - baseline_tob_oasdi
    oasdi_gain = option12_standard["employer_ss_tax_revenue"]
    hi_gain = option12_standard["employer_medicare_tax_revenue"]
    oasdi_loss = baseline_tob_oasdi - reform_tob_oasdi
    hi_loss = baseline_tob_hi - reform_tob_hi
    return {
        "reform_name": "option14_stacked",
        "year": int(option13["year"]),
        "baseline_revenue": option13["reform_revenue"],
        "reform_revenue": option12_standard["reform_revenue"],
        "revenue_impact": option12_standard["reform_revenue"] - option13["reform_revenue"],
        "baseline_tob_medicare_hi": baseline_tob_hi,
        "reform_tob_medicare_hi": reform_tob_hi,
        "tob_medicare_hi_impact": tob_hi_impact,
        "baseline_tob_oasdi": baseline_tob_oasdi,
        "reform_tob_oasdi": reform_tob_oasdi,
        "tob_oasdi_impact": tob_oasdi_impact,
        "baseline_tob_total": baseline_tob_oasdi + baseline_tob_hi,
        "reform_tob_total": reform_tob_oasdi + reform_tob_hi,
        "tob_total_impact": tob_oasdi_impact + tob_hi_impact,
        "scoring_type": "static",
        "employer_ss_tax_revenue": oasdi_gain,
        "employer_medicare_tax_revenue": hi_gain,
        "oasdi_gain": oasdi_gain,
        "hi_gain": hi_gain,
        "oasdi_loss": oasdi_loss,
        "hi_loss": hi_loss,
        "oasdi_net_impact": oasdi_gain - oasdi_loss,
        "hi_net_impact": hi_gain - hi_loss,
        "run_id": option13["run_id"] or fallback_run_id,
    }


def build_special_cases(
    standard: pd.DataFrame,
    *,
    option13_dir: Path,
    special_start_year: int,
    fallback_run_id: str,
) -> pd.DataFrame:
    baseline = baseline_lookup(standard)
    option12_standard = standard_reform_lookup(standard, "option12")
    option13_raw = load_raw_rows(option13_dir)

    rows: list[dict] = []
    for year in YEARS:
        if year < special_start_year:
            rows.append(
                current_law_row(
                    year,
                    "option13",
                    baseline[year],
                    f"{fallback_run_id}:prestart-current-law",
                )
            )
            rows.append(
                current_law_row(
                    year,
                    "option14_stacked",
                    baseline[year],
                    f"{fallback_run_id}:prestart-current-law",
                )
            )
            continue

        if year not in option13_raw:
            raise FileNotFoundError(f"Missing option13 output for year {year} in {option13_dir}")
        if year not in option12_standard:
            raise FileNotFoundError(f"Missing option12 standard result for year {year}")

        option13 = option13_row(option13_raw[year], baseline[year], fallback_run_id)
        rows.append(option13)
        rows.append(option14_row(option13, option12_standard[year], fallback_run_id))

    return pd.DataFrame(rows)


def build_option13_dashboard_data(option13_dir: Path, special_start_year: int) -> pd.DataFrame:
    option13_raw = load_raw_rows(option13_dir)
    missing = sorted(set(range(special_start_year, 2101)) - set(option13_raw))
    if missing:
        raise FileNotFoundError(
            "Missing option13 dashboard artifacts for years: " + ", ".join(map(str, missing))
        )
    rows = [option13_raw[year] for year in sorted(option13_raw)]
    df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    df["year"] = df["year"].astype(int)
    return df


def merge_with_prior(combined: pd.DataFrame, prior: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["year", "reform_name"]
    new_cols = [c for c in combined.columns if c not in key_cols]
    prior_cols = [c for c in prior.columns if c not in key_cols]

    merged = combined.merge(prior, on=key_cols, how="left", suffixes=("_new", "_prior"))
    out = merged[key_cols].copy()

    ordered_cols = ["scoring_type", "run_id"] + [
        c for c in new_cols if c not in {"scoring_type", "run_id"}
    ]
    for col in ordered_cols:
        new_name = f"{col}_new" if f"{col}_new" in merged.columns else col
        if col == "run_id":
            out["run_id"] = merged["run_id"]
            continue
        out[new_name] = merged[new_name]
        if col in prior_cols:
            prior_name = f"{col}_prior"
            delta_name = f"{col}_delta"
            out[prior_name] = merged[prior_name]
            if pd.api.types.is_numeric_dtype(out[new_name]):
                out[delta_name] = out[new_name] - out[prior_name]
            else:
                out[delta_name] = ""
    return out


def write_workbook(
    with_prior: pd.DataFrame,
    *,
    out_path: Path,
    standard_results: Path,
    option13_dir: Path,
    option14_dir: Path,
    prior_reference: Path,
    dashboard_all_static: Path,
    dashboard_option13: Path,
    special_manifest: Path | None,
) -> None:
    delta_cols = [c for c in with_prior.columns if c.endswith("_delta")]
    delta_summary = with_prior.groupby("reform_name", as_index=False)[delta_cols].mean(
        numeric_only=True
    )
    metadata_rows = [
        {
            "artifact": "standard_results",
            "path": str(standard_results),
            "note": "Refreshed option1-option12 results on latest HF microdata.",
        },
        {
            "artifact": "special_option13_dir",
            "path": str(option13_dir),
            "note": "Balanced-fix outputs used directly for 2035-2100; pre-2035 is current-law no-op.",
        },
        {
            "artifact": "special_option14_dir",
            "path": str(option14_dir),
            "note": "Legacy raw option14 dir kept only for reference; stacked rows are rebuilt from option13 plus standard option12 outputs.",
        },
        {
            "artifact": "prior_reference",
            "path": str(prior_reference),
            "note": "Prior delivered all_static_results file used for reference columns.",
        },
        {
            "artifact": "dashboard_all_static",
            "path": str(dashboard_all_static),
            "note": "Dashboard-facing refreshed values without prior-reference columns.",
        },
        {
            "artifact": "dashboard_option13",
            "path": str(dashboard_option13),
            "note": "Dashboard-facing raw option13 balanced-fix series.",
        },
    ]
    if special_manifest is not None:
        metadata_rows.append(
            {
                "artifact": "special_manifest",
                "path": str(special_manifest),
                "note": "Manifest for the special-case rerun backing option13 and option14_stacked.",
            }
        )
    metadata = pd.DataFrame(metadata_rows)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        with_prior.to_excel(writer, sheet_name="full_results", index=False)
        delta_summary.to_excel(writer, sheet_name="delta_summary", index=False)
        metadata.to_excel(writer, sheet_name="metadata", index=False)


def main() -> None:
    args = parse_args()
    special_manifest_data = None
    fallback_run_id = "special-case-adhoc"
    if args.special_manifest is not None:
        special_manifest_data = json.loads(args.special_manifest.read_text(encoding="utf-8"))
        fallback_run_id = str(special_manifest_data.get("run_id", fallback_run_id))

    standard = load_standard(args.standard_results)
    prior = load_prior(args.prior_reference)
    special = build_special_cases(
        standard,
        option13_dir=args.option13_dir,
        special_start_year=args.special_start_year,
        fallback_run_id=fallback_run_id,
    )
    option13_dashboard = build_option13_dashboard_data(
        args.option13_dir,
        args.special_start_year,
    )
    standard_and_special = pd.concat([standard, special], ignore_index=True, sort=False)
    standard_and_special = (
        standard_and_special.sort_values(["year", "reform_name"]).reset_index(drop=True)
    )

    with_prior = merge_with_prior(standard_and_special, prior)

    standard_and_special.to_csv(args.out_combined, index=False)
    with_prior.to_csv(args.out_with_prior_csv, index=False)
    write_workbook(
        with_prior,
        out_path=args.out_with_prior_xlsx,
        standard_results=args.standard_results,
        option13_dir=args.option13_dir,
        option14_dir=args.option14_dir,
        prior_reference=args.prior_reference,
        dashboard_all_static=args.dashboard_all_static,
        dashboard_option13=args.dashboard_option13,
        special_manifest=args.special_manifest,
    )
    standard_and_special.drop(columns=["run_id"]).to_csv(
        args.dashboard_all_static,
        index=False,
    )
    with_prior.drop(columns=["run_id"]).to_csv(
        args.dashboard_with_prior_csv,
        index=False,
    )
    shutil.copy2(args.out_with_prior_xlsx, args.dashboard_with_prior_xlsx)
    option13_dashboard.to_csv(args.dashboard_option13, index=False)

    metadata = {
        "rows": int(len(standard_and_special)),
        "years": [min(YEARS), max(YEARS)],
        "reforms": sorted(standard_and_special["reform_name"].unique().tolist()),
        "special_case_start_year": args.special_start_year,
        "special_case_manifest": str(args.special_manifest) if args.special_manifest else None,
        "option14_active_years": sorted(
            with_prior.loc[
                (with_prior["reform_name"] == "option14_stacked")
                & (
                    (with_prior["revenue_impact_new"] != 0)
                    | (with_prior["oasdi_net_impact_new"] != 0)
                    | (with_prior["hi_net_impact_new"] != 0)
                ),
                "year",
            ].astype(int).tolist()
        ),
    }
    args.out_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote {args.out_combined}")
    print(f"Wrote {args.out_with_prior_csv}")
    print(f"Wrote {args.out_with_prior_xlsx}")


if __name__ == "__main__":
    main()
