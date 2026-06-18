"""Assemble the CRFB reform panel: exact static deltas + behavioral deltas via
the endpoint-ratio method.

Behavioral scoring is NOT a per-year LSR recompute. Following the established
CRFB method, the behavioral/static revenue ratio is computed at two endpoints
(2026 and 2100), linearly interpolated across years, and applied to the exact
static panel. Two LSR runs per reform produce the whole behavioral column.

Inputs: per-cell score JSONs (reform_id, year, scoring_type, delta) downloaded
from the crfb-reform-scores volume into a local directory.
Outputs: results/reform_panel.csv (reform, year, static, behavioral, ratio) and
results/reform_panel.json.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import warnings

ROOT = Path(__file__).resolve().parents[1]
REFORMS = [
    "option1",
    "option2",
    "option3",
    "option4",
    "option5",
    "option6",
    "option7",
    "option8",
    "option9",
    "option10",
    "option11",
    "option12",
    "tax93",
    "reverse_roth",
]
ENDPOINTS = (2026, 2100)
NEAR_ZERO_STATIC_DELTA_TOLERANCE = 1_000_000.0
# Reforms whose behavioral delta is taken equal to the static delta (ratio 1.0)
# rather than from a computed LSR endpoint ratio. reverse_roth's labor-supply
# response is assumed negligible, consistent with the ~1.00 endpoint multipliers
# every other taxation-of-benefits reform produced; its behavioral column is an
# assumption, not a separately-computed LSR result, and is flagged as such.
BEHAVIORAL_ASSUMED_STATIC = {"reverse_roth"}


def load_cells(scores_dir: Path) -> dict:
    cells: dict = {}
    for path in scores_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            continue
        cells[(d["reform_id"], int(d["year"]), d.get("scoring_type", "static"))] = (
            float(d["delta"])
        )
    return cells


def behavioral_static_ratio(
    *,
    reform_id: str,
    year: int,
    static_delta: float | None,
    behavioral_delta: float | None,
    tolerance: float = NEAR_ZERO_STATIC_DELTA_TOLERANCE,
) -> float | None:
    if behavioral_delta is None:
        return None
    if static_delta is None or abs(static_delta) < tolerance:
        warnings.warn(
            f"{reform_id}_{year} static endpoint delta is near zero "
            f"({static_delta}); using behavioral/static ratio 1.0.",
            RuntimeWarning,
            stacklevel=2,
        )
        return 1.0
    return behavioral_delta / static_delta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default="/tmp/scores_dl")
    args = ap.parse_args()

    cells = load_cells(Path(args.scores))
    years = sorted({y for (_, y, _) in cells})
    lo, hi = ENDPOINTS

    panel = {
        "years": years,
        "method": "static exact; behavioral = static x linear-interpolated endpoint ratio (2026,2100)",
        "reforms": {},
    }
    missing_endpoints = []

    for r in REFORMS:
        static = {y: cells.get((r, y, "static")) for y in years}
        assumed_static = r in BEHAVIORAL_ASSUMED_STATIC
        # endpoint behavioral/static ratios
        ratios = {}
        if assumed_static:
            ratios = {
                ep: 1.0 for ep in ENDPOINTS
            }  # behavioral == static, by assumption
        else:
            for ep in ENDPOINTS:
                s = cells.get((r, ep, "static"))
                c = cells.get((r, ep, "conventional"))
                if c is None:
                    missing_endpoints.append(f"{r}_{ep}_conventional")
                    ratios[ep] = None
                else:
                    ratios[ep] = behavioral_static_ratio(
                        reform_id=r,
                        year=ep,
                        static_delta=s,
                        behavioral_delta=c,
                    )
        row = {}
        for y in years:
            s = static.get(y)
            if s is None:
                row[str(y)] = {"static": None, "behavioral": None, "ratio": None}
                continue
            if ratios[lo] is None or ratios[hi] is None:
                row[str(y)] = {"static": s, "behavioral": None, "ratio": None}
                continue
            w = (y - lo) / (hi - lo)
            ratio = ratios[lo] * (1 - w) + ratios[hi] * w
            row[str(y)] = {"static": s, "behavioral": s * ratio, "ratio": ratio}
        panel["reforms"][r] = {
            "endpoint_ratio_2026": ratios[lo],
            "endpoint_ratio_2100": ratios[hi],
            "behavioral_assumed_static": assumed_static,
            "by_year": row,
        }

    out_json = ROOT / "results" / "reform_panel.json"
    out_csv = ROOT / "results" / "reform_panel.csv"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(panel, indent=2, sort_keys=True))

    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "reform",
                "year",
                "static_delta_usd",
                "behavioral_delta_usd",
                "behavioral_static_ratio",
            ]
        )
        for r in REFORMS:
            for y in years:
                cell = panel["reforms"][r]["by_year"][str(y)]
                w.writerow([r, y, cell["static"], cell["behavioral"], cell["ratio"]])

    # console summary
    print("endpoint behavioral/static ratios (the per-reform multipliers):")
    print(f"{'reform':14}{'ratio@2026':>12}{'ratio@2100':>12}")
    for r in REFORMS:
        p = panel["reforms"][r]
        r26 = p["endpoint_ratio_2026"]
        r100 = p["endpoint_ratio_2100"]
        print(
            f"{r:14}{(f'{r26:.4f}' if r26 is not None else 'MISSING'):>12}"
            f"{(f'{r100:.4f}' if r100 is not None else 'MISSING'):>12}"
        )
    print(f"\nwrote {out_csv}\nwrote {out_json}")
    if missing_endpoints:
        print(f"\nMISSING endpoint conventional cells: {missing_endpoints}")
    else:
        print("\nall endpoint multipliers present.")


if __name__ == "__main__":
    main()
