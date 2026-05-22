from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
STATIC_SOURCE = RESULTS / "all_static_results_full_h5_selected_panel_display_20260522.csv"
BEHAVIORAL_SOURCE = RESULTS / "behavioral_endpoint_ratio_display_20260522.csv"
OUT_RESULTS = RESULTS / "results_full_h5_selected_panel_display_20260522.csv"
OUT_METADATA = RESULTS / "results_full_h5_selected_panel_display_20260522_metadata.json"
DASHBOARD_OUT = REPO / "dashboard" / "public" / "data" / "results.csv"
ROOT_OUT = REPO / "results.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the unified dashboard results.csv with all scoring rows."
    )
    parser.add_argument("--static-source", type=Path, default=STATIC_SOURCE)
    parser.add_argument("--conventional-source", type=Path, default=None)
    parser.add_argument("--behavioral-source", type=Path, default=BEHAVIORAL_SOURCE)
    parser.add_argument("--out-results", type=Path, default=OUT_RESULTS)
    parser.add_argument("--out-metadata", type=Path, default=OUT_METADATA)
    parser.add_argument("--dashboard-out", type=Path, default=DASHBOARD_OUT)
    parser.add_argument("--root-out", type=Path, default=ROOT_OUT)
    return parser.parse_args()


def load_source(path: Path, scoring_type: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["scoring_type"] = scoring_type
    return frame


def build_results(
    static_source: Path,
    conventional_source: Path | None,
    behavioral_source: Path | None,
) -> pd.DataFrame:
    sources = [load_source(static_source, "static")]
    if conventional_source is not None and conventional_source.exists():
        sources.append(load_source(conventional_source, "conventional"))
    if behavioral_source is not None and behavioral_source.exists():
        sources.append(load_source(behavioral_source, "behavioral"))

    columns = list(dict.fromkeys(column for source in sources for column in source.columns))
    combined = pd.concat(
        [source.reindex(columns=columns) for source in sources],
        ignore_index=True,
    )
    return combined.sort_values(["scoring_type", "reform_name", "year"]).reset_index(
        drop=True
    )


def build_metadata(
    results: pd.DataFrame,
    *,
    static_source: Path,
    conventional_source: Path | None,
    behavioral_source: Path | None,
    out_results: Path,
    dashboard_out: Path,
    root_out: Path,
) -> dict:
    return {
        "schema": "crfb_dashboard_results/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "static_source": str(static_source),
        "conventional_source": (
            str(conventional_source)
            if conventional_source is not None and conventional_source.exists()
            else None
        ),
        "behavioral_source": (
            str(behavioral_source)
            if behavioral_source is not None and behavioral_source.exists()
            else None
        ),
        "output_results": str(out_results),
        "dashboard_output": str(dashboard_out),
        "root_compat_output": str(root_out),
        "rows": int(len(results)),
        "scoring_types": sorted(results["scoring_type"].dropna().unique().tolist()),
        "reforms_by_scoring_type": {
            scoring_type: sorted(group["reform_name"].dropna().unique().tolist())
            for scoring_type, group in results.groupby("scoring_type")
        },
        "year_start": int(results["year"].min()),
        "year_end": int(results["year"].max()),
        "public_dashboard_contract": (
            "Dashboard reads this single results.csv and filters by scoring_type."
        ),
    }


def main() -> int:
    args = parse_args()
    results = build_results(
        args.static_source,
        args.conventional_source,
        args.behavioral_source,
    )
    metadata = build_metadata(
        results,
        static_source=args.static_source,
        conventional_source=args.conventional_source,
        behavioral_source=args.behavioral_source,
        out_results=args.out_results,
        dashboard_out=args.dashboard_out,
        root_out=args.root_out,
    )

    args.out_results.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_out.parent.mkdir(parents=True, exist_ok=True)
    args.root_out.parent.mkdir(parents=True, exist_ok=True)

    results.to_csv(args.out_results, index=False, float_format="%.10f")
    args.out_metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(args.out_results, args.dashboard_out)
    shutil.copy2(args.out_results, args.root_out)

    print(f"Wrote {args.out_results} ({len(results)} rows)")
    print(f"Wrote {args.dashboard_out}")
    print(f"Wrote {args.root_out}")
    print(f"Wrote {args.out_metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
