CRFB full-H5 reform run handoff, 2026-05-21 22:16 ET

User is restarting Codex, not computer. Resume in /Users/maxghenis/PolicyEngine/crfb-tob-impacts.

Current production run:
- full-H5 run prefix: full_h5_5a35713_standard_selected_panel_20260521_2150
- Modal app: ap-Vp1qjwDpJYFv0JzGjXCuRT
- tmux launcher: crfb_full_h5_reforms_5a35713_2150
- live dashboard refresh tmux: crfb_live_dashboard_refresh_5a35713
- dashboard status files now R2-aware via scripts/build_live_modeling_dashboard_data.py
- latest known dashboard status before pause: 268/276 complete, 8 pending at 2026-05-22T02:15:08Z
- active app was down to 4 tasks at 02:15Z; probably will drain soon.

Important code changes made this turn:
- scripts/build_live_modeling_dashboard_data.py now scans R2 complete.json markers using CRFB_R2_* env vars.
- scripts/aggregate_reform_full_h5_results.py added; aggregates saved reform H5s from R2 with microdf.MicroDataFrame(...).sum(), no manual weighted multiplication.
- smoke test aggregated 3 rows and matched known 2026 results.

Commands to resume:
1) Refresh status from R2:
export CRFB_R2_ACCOUNT_ID=011fb8d44f0e4d9832265ac9f748bc6b
export CRFB_R2_ENDPOINT_URL="https://${CRFB_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export CRFB_R2_BUCKET=axiom-corpus
export CRFB_R2_ACCESS_KEY_ID="$(agent-secret get agent/cloudflare-r2-axiom-access-key-id axiom-foundation)"
export CRFB_R2_SECRET_ACCESS_KEY="$(agent-secret get agent/cloudflare-r2-axiom-secret-access-key axiom-foundation)"
uv run --with boto3 python scripts/build_live_modeling_dashboard_data.py
jq '{complete:.reform_h5_complete_or_sentinel_count,pending:.reform_h5_pending_count,generated_at}' dashboard/public/data/live_modeling_status_metadata.json

2) Check active app/tasks:
MODAL_ENVIRONMENT=main uv run --with modal modal app list | grep ap-Vp1qjwDpJYFv0JzGjXCuRT || true

3) Show pending cells:
uv run python - <<'PY'
import pandas as pd
df=pd.read_csv('dashboard/public/data/live_reform_status.csv')
p=df[~df.reform_h5_status.isin(['complete','sentinel_complete'])]
print(p[['year','reform_name','reform_h5_status']].to_string(index=False))
PY

4) Run aggregation over complete cells:
export CRFB_R2_ACCOUNT_ID=011fb8d44f0e4d9832265ac9f748bc6b
export CRFB_R2_ENDPOINT_URL="https://${CRFB_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
export CRFB_R2_BUCKET=axiom-corpus
export CRFB_R2_ACCESS_KEY_ID="$(agent-secret get agent/cloudflare-r2-axiom-access-key-id axiom-foundation)"
export CRFB_R2_SECRET_ACCESS_KEY="$(agent-secret get agent/cloudflare-r2-axiom-secret-access-key axiom-foundation)"
uv run --with boto3 --with microdf-python python scripts/aggregate_reform_full_h5_results.py --compute-missing-baselines

Notes:
- If 276/276 complete: aggregate, review results, merge into dashboard data, build dashboard.
- If fewer than 276 complete and app drained/stopped: relaunch ONLY missing cells with patched idempotency code and a fresh run prefix/ledger approval. Do not rerun completed H5 cells.
- Aggregation from H5s is the source for rows, not old aggregate CSVs.
- Never manually multiply by weights; use MicroDataFrame weighted .sum() or PolicyEngine MicroSeries .sum().
