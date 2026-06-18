from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd

from scripts.publish_behavioral_endpoint_dashboard_results import (
    DEFAULT_BEHAVIORAL_ENDPOINT_AGGREGATE,
    build_behavioral_display,
)
from scripts.publish_full_h5_static_dashboard_results import (
    DEFAULT_FULL_H5_AGGREGATE,
    DEFAULT_TOB_BASELINE,
    publish_full_h5_static_results,
)


REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
STATIC_SOURCE = DEFAULT_FULL_H5_AGGREGATE
BEHAVIORAL_SOURCE = DEFAULT_BEHAVIORAL_ENDPOINT_AGGREGATE
TOB_BASELINE = DEFAULT_TOB_BASELINE
OUT_METADATA = REPO / "results.csv.metadata.json"
DASHBOARD_OUT = REPO / "dashboard" / "public" / "data" / "results.csv"
ROOT_OUT = REPO / "results.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the unified dashboard results.csv with all scoring rows."
    )
    parser.add_argument("--static-source", type=Path, default=STATIC_SOURCE)
    parser.add_argument("--behavioral-source", type=Path, default=BEHAVIORAL_SOURCE)
    parser.add_argument("--tob-baseline", type=Path, default=TOB_BASELINE)
    parser.add_argument("--out-metadata", type=Path, default=OUT_METADATA)
    parser.add_argument("--dashboard-out", type=Path, default=DASHBOARD_OUT)
    parser.add_argument("--root-out", type=Path, default=ROOT_OUT)
    return parser.parse_args()


def load_source(path: Path, scoring_type: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["scoring_type"] = scoring_type
    return frame


def build_results(
    static_source: Path, behavioral_source: Path, tob_baseline: Path
) -> pd.DataFrame:
    with tempfile.TemporaryDirectory(prefix="crfb-results-") as tmpdir:
        tmp = Path(tmpdir)
        static_exact = tmp / "static_exact.csv"
        static_display = tmp / "static_display.csv"
        static_metadata = tmp / "static_metadata.json"
        behavioral_exact = tmp / "behavioral_exact.csv"
        behavioral_display = tmp / "behavioral_display.csv"
        behavioral_metadata = tmp / "behavioral_metadata.json"

        publish_full_h5_static_results(
            full_h5_aggregate_path=static_source,
            reference_static_path=static_display,
            tob_baseline_path=tob_baseline,
            exact_output_path=static_exact,
            display_output_path=static_display,
            metadata_output_path=static_metadata,
            require_complete=True,
        )
        build_behavioral_display(
            endpoint_aggregate_path=behavioral_source,
            static_display_path=static_display,
            tob_baseline_path=tob_baseline,
            exact_output_path=behavioral_exact,
            display_output_path=behavioral_display,
            metadata_output_path=behavioral_metadata,
        )
        sources = [
            load_source(static_display, "static"),
            load_source(behavioral_display, "behavioral"),
        ]
    columns = list(
        dict.fromkeys(column for source in sources for column in source.columns)
    )
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
    behavioral_source: Path,
    tob_baseline: Path,
    dashboard_out: Path,
    root_out: Path,
) -> dict:
    return {
        "schema": "crfb_dashboard_results/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "static_source": str(static_source),
        "behavioral_source": str(behavioral_source),
        "tob_baseline": str(tob_baseline),
        "output_results": str(root_out),
        "dashboard_output": str(dashboard_out),
        "rows": int(len(results)),
        "post_obbba_tob_baseline_applied": False,
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
        args.behavioral_source,
        args.tob_baseline,
    )
    metadata = build_metadata(
        results,
        static_source=args.static_source,
        behavioral_source=args.behavioral_source,
        tob_baseline=args.tob_baseline,
        dashboard_out=args.dashboard_out,
        root_out=args.root_out,
    )

    args.dashboard_out.parent.mkdir(parents=True, exist_ok=True)
    args.root_out.parent.mkdir(parents=True, exist_ok=True)

    results.to_csv(args.root_out, index=False, float_format="%.10f")
    args.out_metadata.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy2(args.root_out, args.dashboard_out)

    print(f"Wrote {args.root_out} ({len(results)} rows)")
    print(f"Wrote {args.dashboard_out} (deployment copy)")
    print(f"Wrote {args.out_metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
