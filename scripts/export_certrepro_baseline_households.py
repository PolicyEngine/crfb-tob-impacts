"""Export per-household baseline net income for one certrepro anchor year.

Runs in the certified worktree venv (policyengine-us 1.700.2) against
projected_datasets_certrepro/<year>.h5 with the dataset's own tax-assumption
reform resolved by the canonical path (src.year_runner), so the baseline leg
matches the family the magi100 / tax_panel_2005 cells were scored on.

Usage (from ~/PolicyEngine/crfb-cert): .venv/bin/python <this file> <year>
Writes tmp/baseline_households_certrepro/<year>.csv with
household_id, baseline_net_income, weight.
"""

import sys
from pathlib import Path

REPO = Path.home() / "PolicyEngine" / "crfb-cert"
sys.path.insert(0, str(REPO))  # certified worktree src


def main() -> int:
    year = int(sys.argv[1])
    out_dir = REPO / "tmp" / "baseline_households_certrepro"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{year}.csv"
    if out.exists():
        print(f"{year}: already exported, skip")
        return 0

    import pandas as pd

    from policyengine_us import Microsimulation
    from src.year_runner import _resolve_baseline_reform_for_dataset

    dataset = str(REPO / "projected_datasets_certrepro" / f"{year}.h5")
    reform = _resolve_baseline_reform_for_dataset(
        year=year, dataset_name=dataset, baseline_reform=None
    )
    sim = Microsimulation(dataset=dataset, reform=reform)
    hh_id = sim.calc("household_id", period=year)
    net = sim.calc("household_net_income", period=year)
    frame = pd.DataFrame(
        {
            "household_id": pd.Series(hh_id).reset_index(drop=True),
            "baseline_net_income": pd.Series(net).reset_index(drop=True),
            "weight": pd.Series(net.weights).reset_index(drop=True),
        }
    )
    frame.to_csv(out, index=False)
    print(f"{year}: wrote {out} ({len(frame)} households)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
