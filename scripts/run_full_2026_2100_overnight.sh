#!/bin/zsh
set -euo pipefail

ROOT="/Users/maxghenis"
CRFB_REPO="$ROOT/PolicyEngine/crfb-tob-impacts"
USDATA_REPO="$ROOT/.codex-worktrees/us-data-crfb-integration"
US_REPO="$ROOT/.codex-worktrees/us-crfb-integration"
UV_BIN="$ROOT/.local/bin/uv"

LONG_TERM_DIR="$USDATA_REPO/policyengine_us_data/datasets/cps/long_term"
CRFB_RESULTS_DIR="$CRFB_REPO/results/modal_runs_production"
LOG_DIR="$CRFB_REPO/results/overnight_logs"
HF_CACHE_ROOT="$ROOT/.cache/huggingface/hub/models--policyengine--policyengine-us-data/snapshots"

EARLY_OUT="$USDATA_REPO/tmp/trustees_core_threshold_grid_2026_2074_latesthf"
LATE_OUT="$USDATA_REPO/tmp/trustees_core_threshold_grid_2075_2100_latesthf"
ALL_REFORMS="option1,option2,option3,option4,option5,option6,option7,option8,option9,option10,option11,option12"

rm -rf "$EARLY_OUT" "$LATE_OUT"
mkdir -p "$LOG_DIR" "$CRFB_RESULTS_DIR" "$EARLY_OUT" "$LATE_OUT"

timestamp() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*" | tee -a "$LOG_DIR/overnight_full_2026_2100.log"
}

run_in_long_term() {
  (
    cd "$LONG_TERM_DIR"
    export PYTHONPATH="$US_REPO:$USDATA_REPO"
    "$@"
  )
}

run_in_crfb() {
  (
    cd "$CRFB_REPO"
    export CRFB_POLICYENGINE_US_PATH="$US_REPO"
    "$@"
  )
}

submit_modal_run() {
  local years="$1"
  local datasets_path="$2"
  local label="$3"
  local minimum_quality="$4"
  local submit_log="$LOG_DIR/${label}.submit.log"

  log "Submitting Modal scoring run label=$label years=$years quality>=$minimum_quality"
  run_in_crfb \
    "$UV_BIN" run python scripts/submit_modal_scenario_run.py \
      --years "$years" \
      --reforms "$ALL_REFORMS" \
      --label "$label" \
      --projected-datasets-path "$datasets_path" \
      --required-profile ss-payroll-tob \
      --required-target-source trustees_2025_current_law \
      --required-tax-assumption trustees-core-thresholds-v1 \
      --minimum-calibration-quality "$minimum_quality" \
      --modal-worker-profile small \
      --launch-jobs 0 \
      --output-root "$CRFB_RESULTS_DIR" \
      > "$submit_log" 2>&1

  local run_id
  run_id="$(python3 - <<'PY' "$submit_log"
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
matches = re.findall(r"Run ID: ([^\s]+)", text)
print(matches[-1] if matches else "")
PY
)"

  if [[ -z "$run_id" ]]; then
    log "Modal submit log did not contain a run id: $submit_log"
    return 1
  fi

  log "Submitted Modal run $run_id"
  printf '%s\n' "$run_id" > "$LOG_DIR/${label}.run_id"
}

collect_valid_late_years() {
  python3 - <<'PY' "$LATE_OUT"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
years = []
for meta_path in sorted(root.glob("*.h5.metadata.json")):
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    audit = data.get("calibration_audit", {})
    quality = audit.get("calibration_quality")
    year = int(data["year"])
    if year in {2075, 2076, 2077, 2078}:
        if quality != "exact":
            continue
    elif quality not in {"exact", "approximate"}:
        continue
    years.append(str(year))
print(",".join(years))
PY
}

log "Starting overnight 2026-2100 run"
log "Using policyengine-us-data worktree: $USDATA_REPO"
log "Using policyengine-us worktree: $US_REPO"
if [[ -d "$HF_CACHE_ROOT" ]]; then
  latest_snapshot="$(ls -td "$HF_CACHE_ROOT"/* 2>/dev/null | head -n 1 || true)"
else
  latest_snapshot=""
fi

if [[ -n "$latest_snapshot" ]]; then
  log "Using cached HF microdata snapshot: $latest_snapshot"
else
  log "No cached HF snapshot found; downloading current published microdata"
  run_in_long_term \
    "$UV_BIN" run python - <<'PY' > "$LOG_DIR/hf_snapshot_refresh.log" 2>&1
from huggingface_hub import snapshot_download

path = snapshot_download(
    repo_id="policyengine/policyengine-us-data",
    repo_type="model",
    revision="main",
)
print(path)
PY
  log "HF microdata refresh complete"
fi

log "Early exact calibration batch 2026-2074 starting"
run_in_long_term \
  "$UV_BIN" run python run_household_projection_parallel.py \
    --years 2026-2074 \
    --jobs 2 \
    --output-dir "$EARLY_OUT" \
    --profile ss-payroll-tob \
    --target-source trustees_2025_current_law \
    --tax-assumption trustees-core-thresholds-v1 \
    > "$LOG_DIR/calibration_2026_2074.log" 2>&1
log "Early exact calibration batch finished"

submit_modal_run \
  "2026-2074" \
  "$EARLY_OUT" \
  "trustees-all-reforms-2026-2074-small-deployed-latesthf" \
  "exact"

log "Late augmented calibration loop 2075-2100 starting"
for year in $(seq 2075 2100); do
  year_log="$LOG_DIR/calibration_${year}.log"
  log "Calibrating late year $year"
  if run_in_long_term \
    "$UV_BIN" run python run_household_projection.py \
      "$year" "$year" \
      --profile ss-payroll-tob \
      --target-source trustees_2025_current_law \
      --tax-assumption trustees-core-thresholds-v1 \
      --output-dir "$LATE_OUT" \
      --support-augmentation-profile donor-backed-composite-v1 \
      --support-augmentation-align-to-run-year \
      --support-augmentation-blueprint-base-weight-scale 0.5 \
      --support-augmentation-sanitize-clone-non-target-income \
      --save-h5 \
      > "$year_log" 2>&1; then
    log "Finished late year $year"
  else
    log "Late year $year failed; see $year_log"
  fi
done
log "Late augmented calibration loop finished"

late_years="$(collect_valid_late_years)"
if [[ -n "$late_years" ]]; then
  submit_modal_run \
    "$late_years" \
    "$LATE_OUT" \
    "trustees-all-reforms-2075-2100-small-deployed-latesthf" \
    "approximate"
else
  log "No late years passed the scoring contract; skipping late Modal submission"
fi

log "Overnight orchestrator finished"
