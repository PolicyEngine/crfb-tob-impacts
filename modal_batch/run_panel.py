"""One command to build the full CRFB reform panel — resumable and self-pipelining.

    modal run modal_batch/run_panel.py
    modal run modal_batch/run_panel.py --years 2026,2030,2035-2100:5 --reforms option1,tax93
    modal run --detach modal_batch/run_panel.py            # survives client disconnect

What it does, end to end:

1. Surveys the two Volumes to see which baselines are already built and which
   (reform, year) cells are already scored — so a re-run only does what's
   missing. Nothing is recomputed; the command is idempotent and resumable.
2. Builds every missing baseline year (Stage A-D on the certified populace base)
   in its own container, in parallel.
3. Pipelines, not barriers: the moment a year's baseline commits, that same
   build *spawns the 14 reform-scoring cells for that year*. Scoring for 2026
   starts while 2100 is still calibrating — and it self-propagates on Modal even
   if the local client is killed.
4. Both functions are ``nonpreemptible`` with ``retries=2`` — the two failure
   modes that stalled earlier runs (spot preemption killing long far-horizon
   builds, and scoring cells thrashing on preemption to zero commits) cannot
   recur.
5. When every cell is present, assembles the delta-by-reform-by-year panel,
   writes it (provenance-stamped with the certified base build id) to
   ``results/reform_panel.json``, and prints the table.

Reform revenue is scored as the income-tax delta vs the current-law baseline;
for years >= 2035 the Trustees long-run tax assumption (current law) is stacked
under both baseline and reform, matching how the baselines were calibrated.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import modal

LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "crfb-panel"

# Certified-base runtime: policyengine.py 4.17.5 certifies the SS-calibrated
# populace base for policyengine-us 1.729.0.
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
baselines = modal.Volume.from_name("crfb-baseline-builds", create_if_missing=True)
scores = modal.Volume.from_name("crfb-reform-scores", create_if_missing=True)
BUILDS = "/builds"
SCORES = "/scores"

REFORMS = [
    "option1", "option2", "option3", "option4", "option5", "option6",
    "option7", "option8", "option9", "option10", "option11", "option12",
    "tax93", "reverse_roth",
]
# Default years are NOT a flat 5-year grid: src.selected_cells is the single
# source of truth — annual 2026-2035 (catches the OBBBA senior-deduction sunset
# in 2029 and the 2034/35 tax-assumption switch), every five years 2040-2100,
# and the option12 OASDI->HI phase junctures (2048, 2049, 2062, 2063).

# Behavioral (conventional / labor-supply-response) scoring is ENDPOINT-ONLY BY
# CONSTRUCTION. The behavioral/static revenue ratio is stable, so it is computed
# only at these two endpoints and interpolated across years downstream
# (scripts/assemble_reform_panel.py). Fanning LSR out per year is ~25x the cost
# for zero added accuracy and is the over-run this guard exists to prevent:
# every spawn site below derives behavioral years from this tuple, never the
# full panel. Static scoring uses the full year list.
BEHAVIORAL_ENDPOINT_YEARS = (2026, 2100)


def _years_for_scoring(scoring_type: str, year_list) -> list[int]:
    if scoring_type == "static":
        return list(year_list)
    return [y for y in BEHAVIORAL_ENDPOINT_YEARS if y in year_list]


# --------------------------------------------------------------------------- #
# Spec parsing
# --------------------------------------------------------------------------- #
def _parse_years(spec: str) -> list[int]:
    years: list[int] = []
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry:
            continue
        step = 1
        if ":" in entry:
            entry, step_text = entry.split(":")
            step = int(step_text)
        if "-" in entry:
            start_text, end_text = entry.split("-")
            years.extend(range(int(start_text), int(end_text) + 1, step))
        else:
            years.append(int(entry))
    return sorted(set(years))


def _parse_reforms(spec: str) -> list[str]:
    return [r.strip() for r in spec.split(",") if r.strip()] if spec else list(REFORMS)


def _cell_key(reform_id: str, year: int, scoring_type: str = "static") -> str:
    # Static cells keep the bare name so the already-computed static panel is
    # reused; behavioral (conventional) cells get a scoring suffix.
    suffix = "" if scoring_type == "static" else f"_{scoring_type}"
    return f"{reform_id}_{year}{suffix}"


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return float(value)


# --------------------------------------------------------------------------- #
# Survey / collect (read-only volume views)
# --------------------------------------------------------------------------- #
@app.function(image=image, volumes={BUILDS: baselines, SCORES: scores})
def survey() -> dict:
    """Current committed state of both Volumes: built years + scored cell keys."""
    import re

    baselines.reload()
    scores.reload()
    built = sorted(
        int(m.group(1))
        for p in Path(BUILDS).glob("*.sentinel.json")
        for m in [re.match(r"(\d{4})\.sentinel\.json", p.name)]
        if m
    )
    scored = sorted(p.stem for p in Path(SCORES).glob("*.json"))
    return {"built": built, "scored": scored}


@app.function(image=image, volumes={SCORES: scores})
def collect() -> list[dict]:
    """Every scored cell record, for panel assembly."""
    scores.reload()
    out = []
    for p in sorted(Path(SCORES).glob("*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:  # noqa: BLE001 — skip an unreadable/partial cell
            continue
    return out


# --------------------------------------------------------------------------- #
# Build one baseline year (idempotent) -> self-pipeline its reform cells
# --------------------------------------------------------------------------- #
@app.function(
    image=image,
    cpu=4,
    memory=98304,
    timeout=21600,
    # Mounts both volumes: BUILDS to write the baseline, SCORES so the
    # self-pipeline step can dedup against already-scored cells before spawning.
    volumes={BUILDS: baselines, SCORES: scores},
    secrets=[modal.Secret.from_name("huggingface-token")],
    retries=2,
    nonpreemptible=True,
)
def build_one_year(
    year: int, reforms: list[str], scoring_types: tuple[str, ...] = ("static",)
) -> dict:
    """Build {year}'s baseline on the certified base if missing, then spawn its
    reform-scoring cells (every scoring type, only those not already scored)."""
    sys.path.insert(0, "/app")
    import importlib.metadata as metadata
    import shutil

    from src.engine import certified_base_build_id, certified_base_uri

    dest = Path(BUILDS)
    sentinel_path = dest / f"{year}.sentinel.json"

    baselines.reload()
    if sentinel_path.exists():
        sentinel = json.loads(sentinel_path.read_text())
        built = False
    else:
        from src.pipeline import build_year

        out = Path("/tmp/out")
        out.mkdir(parents=True, exist_ok=True)
        base_uri = certified_base_uri()
        sentinel = build_year(
            year,
            base_uri,
            out,
            base_dataset_label=base_uri,
            policyengine_us_version=metadata.version("policyengine-us"),
        )
        sentinel = {k: _json_safe(v) for k, v in dict(sentinel).items()}
        shutil.copy(out / f"{year}.h5", dest / f"{year}.h5")
        shutil.copy(out / f"{year}.h5.metadata.json", dest / f"{year}.h5.metadata.json")
        sentinel_path.write_text(json.dumps(sentinel, sort_keys=True))
        baselines.commit()
        built = True

    # Self-pipeline: kick off this year's reform cells now that the baseline
    # exists. score_cell is idempotent, so already-scored cells are no-ops.
    scores.reload()
    scored = {p.stem for p in Path(SCORES).glob("*.json")}
    spawned = []
    for scoring_type in scoring_types:
        # Behavioral is endpoint-only: a build at a non-endpoint year never
        # self-pipelines LSR cells (this is where the per-year over-run happened).
        if scoring_type != "static" and year not in BEHAVIORAL_ENDPOINT_YEARS:
            continue
        for reform_id in reforms:
            if _cell_key(reform_id, year, scoring_type) not in scored:
                score_cell.spawn(reform_id, year, scoring_type)
                spawned.append(_cell_key(reform_id, year, scoring_type))

    return {
        "year": year,
        "built": built,
        "spawned_cells": spawned,
        "certified_base_build_id": certified_base_build_id(),
        "sentinel": sentinel,
    }


# --------------------------------------------------------------------------- #
# Score one (reform, year) cell (idempotent)
# --------------------------------------------------------------------------- #
@app.function(
    image=image,
    cpu=4,
    memory=65536,
    timeout=10800,
    volumes={BUILDS: baselines, SCORES: scores},
    retries=2,
    nonpreemptible=True,
)
def score_cell(reform_id: str, year: int, scoring_type: str = "static") -> dict:
    sys.path.insert(0, "/app")
    out = Path(SCORES)
    out.mkdir(parents=True, exist_ok=True)
    cell_path = out / f"{_cell_key(reform_id, year, scoring_type)}.json"

    scores.reload()
    if cell_path.exists():
        return json.loads(cell_path.read_text())

    from src import reforms as R
    from src.engine import dataset_microsimulation
    from src.pipeline import _tax_assumption_reform

    baselines.reload()
    h5 = f"{BUILDS}/{year}.h5"
    current_law = _tax_assumption_reform(year)  # None before 2035

    install_lsr = None
    if scoring_type == "static":
        policy = getattr(R, f"get_{reform_id}_reform")()
    elif scoring_type == "conventional":
        # CBO conventional (behavioral) scoring: policy + labor-supply
        # elasticities, with the LSR comparison anchored to the same
        # current-law baseline used for static aggregation.
        from policyengine_core.reforms import Reform
        from src.reform_full_h5_worker import install_behavioral_baseline_tax_system
        from src.year_runner import CONVENTIONAL_REFORM_DICT_FUNCTIONS

        install_lsr = install_behavioral_baseline_tax_system
        if reform_id in CONVENTIONAL_REFORM_DICT_FUNCTIONS:
            policy = Reform.from_dict(
                CONVENTIONAL_REFORM_DICT_FUNCTIONS[reform_id](), country_id="us"
            )
        else:  # reverse_roth carries its own conventional builder
            policy = getattr(R, f"get_{reform_id}_conventional_reform")()
    else:
        raise ValueError(f"unknown scoring_type {scoring_type!r}")

    # A reform may be a single reform or a reform set (tuple) — e.g. reverse_roth
    # returns (parameter_reform, deduction_reform). Flatten the stack so the
    # current-law baseline and the reform components apply as one flat set.
    def income_tax(*reforms, lsr: bool = False) -> float:
        parts: list = []
        for component in reforms:
            if component is None:
                continue
            parts.extend(component if isinstance(component, tuple) else [component])
        reform_arg = None if not parts else (parts[0] if len(parts) == 1 else tuple(parts))
        sim = (
            dataset_microsimulation(h5, reform=reform_arg)
            if reform_arg is not None
            else dataset_microsimulation(h5)
        )
        if lsr and install_lsr is not None and current_law is not None:
            install_lsr(sim, baseline_reform=current_law)
        return float(sim.calculate("income_tax", year).sum())

    baseline_it = income_tax(current_law)
    reformed_it = income_tax(current_law, policy, lsr=(scoring_type == "conventional"))
    record = {
        "reform_id": reform_id,
        "year": year,
        "scoring_type": scoring_type,
        "baseline_income_tax": baseline_it,
        "reformed_income_tax": reformed_it,
        "delta": reformed_it - baseline_it,
        "stacked_current_law": current_law is not None,
    }
    cell_path.write_text(json.dumps(record, sort_keys=True))
    scores.commit()
    return record


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
@app.local_entrypoint()
def main(
    years: str = "",
    reforms: str = "",
    scoring: str = "static",
    redo_baselines: bool = False,
    redo_scores: bool = False,
    wait_minutes: int = 180,
) -> None:
    if years:
        year_list = _parse_years(years)
    else:
        sys.path.insert(0, str(LOCAL_PROJECT_ROOT))
        from src.selected_cells import default_selected_years

        year_list = list(default_selected_years())
    reform_list = _parse_reforms(reforms)
    scoring_types = tuple(s.strip() for s in scoring.split(",") if s.strip()) or (
        "static",
    )
    want_cells = {
        _cell_key(r, y, st)
        for st in scoring_types
        for y in _years_for_scoring(st, year_list)
        for r in reform_list
    }

    state = survey.remote()
    built = set(state["built"])
    scored = set(state["scored"])
    need_build = [y for y in year_list if redo_baselines or y not in built]
    have_baseline_now = [y for y in year_list if y in built and not redo_baselines]

    print(
        f"panel: {len(year_list)} years x {len(reform_list)} reforms "
        f"= {len(want_cells)} cells",
        flush=True,
    )
    print(
        f"  state: {len(built & set(year_list))} baselines built, "
        f"{len(scored & want_cells)} cells scored",
        flush=True,
    )
    print(f"  to build: {need_build or 'none'}", flush=True)

    # Spawn missing baseline builds. Each build self-pipelines its reform cells
    # when it finishes, so the only scores we spawn here are for years whose
    # baseline ALREADY exists (no build will fire for them).
    build_calls = {
        y: build_one_year.spawn(y, reform_list, scoring_types) for y in need_build
    }
    head_start = 0
    for st in scoring_types:
        for y in _years_for_scoring(st, have_baseline_now):
            for r in reform_list:
                if redo_scores or _cell_key(r, y, st) not in scored:
                    score_cell.spawn(r, y, st)
                    head_start += 1
    if head_start:
        print(f"  spawned {head_start} cells for already-built years", flush=True)

    # Watch builds complete (surfaces a terminally-failed build) ...
    pending = dict(build_calls)
    failed_builds: list[int] = []
    while pending:
        for y, call in list(pending.items()):
            try:
                result = call.get(timeout=2)
            except TimeoutError:
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"  BUILD {y} FAILED terminally: {exc}", flush=True)
                failed_builds.append(y)
                del pending[y]
                continue
            del pending[y]
            s = result["sentinel"]
            print(
                f"  baseline {y} {'built' if result['built'] else 'present'} "
                f"(ESS {float(s.get('final_effective_sample_size', 0)):,.0f}, "
                f"gates {s.get('gates_passed')}) -> "
                f"spawned {len(result['spawned_cells'])} cells",
                flush=True,
            )
        if pending:
            time.sleep(5)

    # ... then poll the scores volume until every wanted cell is present
    # (cells are spawned by the builds themselves, so we watch the volume, not
    # FunctionCall handles — this is what makes a --detach run self-complete).
    reachable = {
        _cell_key(r, y, st)
        for st in scoring_types
        for y in _years_for_scoring(st, year_list)
        for r in reform_list
        if y not in failed_builds
    }
    deadline = time.time() + wait_minutes * 60
    last = -1
    while time.time() < deadline:
        scored = set(survey.remote()["scored"])
        done = len(scored & reachable)
        if done != last:
            print(f"  scoring: {done}/{len(reachable)} cells", flush=True)
            last = done
        if scored >= reachable:
            break
        time.sleep(30)

    _assemble(year_list, reform_list, scoring_types, failed_builds)


def _assemble(year_list, reform_list, scoring_types, failed_builds) -> None:
    records = collect.remote()
    by_key = {
        _cell_key(r["reform_id"], r["year"], r.get("scoring_type", "static")): r
        for r in records
    }

    panel = {
        "years": year_list,
        "metric": "income_tax delta vs current-law baseline (TOB revenue scoring)",
        "scoring": {},  # scoring_type -> {reform -> {year -> delta}}
        "certified_base_build_id": _certified_build_id_local(),
        "policyengine": "4.17.5",
        "policyengine_us": "1.729.0",
    }
    missing = []
    for st in scoring_types:
        block = {}
        for r in reform_list:
            row = {}
            for y in year_list:
                rec = by_key.get(_cell_key(r, y, st))
                if rec is None:
                    if y not in failed_builds:
                        missing.append(_cell_key(r, y, st))
                    row[str(y)] = None
                else:
                    row[str(y)] = rec["delta"]
            block[r] = row
        panel["scoring"][st] = block

    out_path = LOCAL_PROJECT_ROOT / "results" / "reform_panel.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(panel, indent=2, sort_keys=True))

    for st in scoring_types:
        block = panel["scoring"][st]
        print(f"\n=== {st} reform panel (Δ income tax, $B) ===", flush=True)
        print("reform        " + "".join(f"{y:>9}" for y in year_list), flush=True)
        for r in reform_list:
            cells = "".join(
                (f"{block[r][str(y)] / 1e9:>9.1f}"
                 if block[r][str(y)] is not None else f"{'—':>9}")
                for y in year_list
            )
            print(f"{r:<14}{cells}", flush=True)
    print(f"\nwrote {out_path}", flush=True)
    if failed_builds:
        print(f"FAILED baselines: {sorted(failed_builds)}", flush=True)
    if missing:
        print(f"MISSING {len(missing)} cells (rerun to fill): {missing[:15]}"
              + (" ..." if len(missing) > 15 else ""), flush=True)
    else:
        print("all cells present.", flush=True)


def _certified_build_id_local() -> str:
    try:
        sys.path.insert(0, str(LOCAL_PROJECT_ROOT))
        from src.engine import certified_base_build_id

        return certified_base_build_id()
    except Exception:  # noqa: BLE001
        return "unknown"
