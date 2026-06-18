"""Modal fan-out for the TOB trust-fund decomposition at the two endpoints.

The OASDI vs Medicare-HI split of taxation-of-benefits revenue is computed by
reusing the established branch-based method (src.reform_full_h5_worker
.materialize_tob_revenue_pair): total TOB = income_tax(full) - income_tax(no
taxable SS), split into OASDI (capped portion) and HI (above-cap). This is the
SAME function the prior pipeline used; we do not reinvent it.

The split ratio is stable across years, so it is computed only at 2026 and 2100
(28 cells = 14 reforms x 2 endpoints), then interpolated across years and
applied to the exact static revenue panel by scripts/assemble_reform_panel.py.
Static only (no labor-supply response); cells run nonpreemptible because the
clone-system branch split is long enough that preemptions wasted prior runs.

Run:
    modal run --detach modal_batch/decomposition.py
Then download:
    modal volume get crfb-decomposition / <local dir>
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import modal

LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "crfb-decomposition"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "policyengine[us]==4.17.5",
        "scipy>=1.15.3",
        "tables>=3.10",
        "h5py>=3.10",
    )
    .add_local_dir(str(LOCAL_PROJECT_ROOT / "src"), "/app/src", copy=True)
    .add_local_dir(str(LOCAL_PROJECT_ROOT / "data"), "/app/data", copy=True)
)

app = modal.App(APP_NAME)
baselines = modal.Volume.from_name("crfb-baseline-builds", create_if_missing=False)
decomp = modal.Volume.from_name("crfb-decomposition", create_if_missing=True)

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
ENDPOINTS = [2026, 2100]
# Weighted-sum variables that feed the trust-fund decomposition columns.
SUM_VARS = (
    "income_tax",
    "tob_revenue_oasdi",
    "tob_revenue_medicare_hi",
    "employer_ss_tax_income_tax_revenue",
    "employer_medicare_tax_income_tax_revenue",
)


@app.function(
    image=image,
    cpu=4,
    memory=65536,
    timeout=10800,
    volumes={"/baselines": baselines, "/decomp": decomp},
    retries=2,
    # ~12 min/cell (the clone_system branch split is heavy) — too long for
    # preemptible (cells get reclaimed mid-run and never commit). Only 28 cells,
    # so nonpreemptible is ~$24 and actually completes.
    nonpreemptible=True,
)
def decompose_cell(reform_id: str, year: int) -> dict:
    sys.path.insert(0, "/app")
    out = Path("/decomp")
    out.mkdir(parents=True, exist_ok=True)
    cell_path = out / f"{reform_id}_{year}.json"
    decomp.reload()
    if cell_path.exists():
        return json.loads(cell_path.read_text())

    from src import reforms as R
    from src.engine import dataset_microsimulation
    from src.pipeline import _tax_assumption_reform
    from src.reform_full_h5_worker import materialize_tob_revenue_pair

    baselines.reload()
    h5 = f"/baselines/{year}.h5"
    current_law = _tax_assumption_reform(year)  # None before 2035

    def metrics(reform) -> dict:
        sim = (
            dataset_microsimulation(h5, reform=reform)
            if reform is not None
            else dataset_microsimulation(h5)
        )
        materialize_tob_revenue_pair(sim, year=year)

        def s(variable: str) -> float:
            variables = getattr(
                getattr(sim, "tax_benefit_system", None),
                "variables",
                {},
            )
            if variable not in variables:
                return 0.0
            return float(sim.calculate(variable, year).sum())

        return {v: s(v) for v in SUM_VARS}

    policy = getattr(R, f"get_{reform_id}_reform")()
    base = metrics(current_law)
    combined = (current_law, policy) if current_law is not None else policy
    ref = metrics(combined)
    record = {
        "reform_id": reform_id,
        "year": year,
        "baseline": base,
        "reform": ref,
        "stacked_current_law": current_law is not None,
    }
    cell_path.write_text(json.dumps(record, sort_keys=True))
    decomp.commit()
    return record


@app.local_entrypoint()
def main(reforms: str = "", years: str = "") -> None:
    rlist = reforms.split(",") if reforms else REFORMS
    ylist = [int(y) for y in years.split(",")] if years else ENDPOINTS
    cells = [(r, y) for r in rlist for y in ylist]
    print(
        f"decomposing {len(cells)} cells ({len(rlist)} reforms x {len(ylist)} endpoints)",
        flush=True,
    )
    done = 0
    for rec in decompose_cell.starmap(cells):
        if rec:
            done += 1
            b, f = rec["baseline"], rec["reform"]
            d_oasdi = (f["tob_revenue_oasdi"] - b["tob_revenue_oasdi"]) / 1e9
            d_hi = (f["tob_revenue_medicare_hi"] - b["tob_revenue_medicare_hi"]) / 1e9
            print(
                f"  {rec['reform_id']:13s} {rec['year']}: "
                f"tob_oasdi {d_oasdi:+.1f}B  tob_hi {d_hi:+.1f}B",
                flush=True,
            )
    print(f"done: {done}/{len(cells)} cells -> volume crfb-decomposition", flush=True)
