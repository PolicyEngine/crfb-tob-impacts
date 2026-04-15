from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd


REPO = Path("/Users/maxghenis/PolicyEngine/crfb-tob-impacts")
RESULTS = REPO / "results"
SOURCE = RESULTS / "trustees_modal_2026_2100_standard_reforms_latesthf_dynamic.csv"
OUT_RESULTS = RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options.csv"
OUT_METADATA = (
    RESULTS / "all_dynamic_results_latesthf_2026_2100_standard_options_metadata.json"
)
DASHBOARD_OUT = REPO / "dashboard" / "public" / "data" / "all_dynamic_results.csv"

MONETARY_COLUMNS = [
    "baseline_revenue",
    "reform_revenue",
    "revenue_impact",
    "baseline_tob_medicare_hi",
    "reform_tob_medicare_hi",
    "tob_medicare_hi_impact",
    "baseline_tob_oasdi",
    "reform_tob_oasdi",
    "tob_oasdi_impact",
    "baseline_tob_total",
    "reform_tob_total",
    "tob_total_impact",
    "employer_ss_tax_revenue",
    "employer_medicare_tax_revenue",
    "oasdi_gain",
    "hi_gain",
    "oasdi_loss",
    "hi_loss",
    "oasdi_net_impact",
    "hi_net_impact",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the final dynamic standard-option panel in billions."
    )
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-results", type=Path, default=OUT_RESULTS)
    parser.add_argument("--out-metadata", type=Path, default=OUT_METADATA)
    parser.add_argument("--dashboard-out", type=Path, default=DASHBOARD_OUT)
    return parser.parse_args()


def load_and_scale(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path).sort_values(["year", "reform_name"]).reset_index(drop=True)
    for column in MONETARY_COLUMNS:
        if column in df.columns:
            df[column] = df[column] / 1e9
    return df


def build_metadata(df: pd.DataFrame, source: Path) -> dict:
    return {
        "source": str(source),
        "rows": int(len(df)),
        "reforms": sorted(df["reform_name"].unique().tolist()),
        "year_start": int(df["year"].min()),
        "year_end": int(df["year"].max()),
        "monetary_unit": "billions_of_nominal_dollars",
        "scoring_type": sorted(df["scoring_type"].dropna().unique().tolist()),
    }


def write_outputs(
    df: pd.DataFrame,
    *,
    out_results: Path,
    out_metadata: Path,
    dashboard_out: Path,
    source: Path,
) -> None:
    out_results.parent.mkdir(parents=True, exist_ok=True)
    dashboard_out.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_results, index=False, float_format="%.10f")
    shutil.copy2(out_results, dashboard_out)

    metadata = build_metadata(df, source)
    out_metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    df = load_and_scale(args.source)
    write_outputs(
        df,
        out_results=args.out_results,
        out_metadata=args.out_metadata,
        dashboard_out=args.dashboard_out,
        source=args.source,
    )
    print(f"Wrote {args.out_results}")
    print(f"Wrote {args.dashboard_out}")
    print(f"Wrote {args.out_metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
