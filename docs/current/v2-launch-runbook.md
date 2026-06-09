# V2 every-fifth-year reform panel: launch runbook

Authorization: Max, by chat on 2026-06-09 — "if you're really confident and
can do it stepwise with sentinels to see the data you can also rerun the
modal reform analysis (just every 5y)". Stepwise-with-sentinels is binding:
one paid sentinel cell, inspect the data, then the full panel.

Panel: years `2026, 2030, 2035, 2040, …, 2100` (16) × `option1–option12`
× `static` = 192 cells, followed by behavioral endpoints
(`2026, 2100` × 12 = 24 cells) under a second approval. Estimated compute
from v1 actuals (~$0.16/static cell, ~$1/behavioral cell): ≈$55 total.

## Sequence

1. **Build datasets** — `scripts/build_v2_projected_datasets.py` for all 16
   years; every year must pass its build-time gates.
2. **Local proof (free)** — `scripts/run_v2_local_proof.py` on 2026/option1/
   static against the local v2 dataset; writes the pre-approved expected
   schema manifest from the proof artifact
   (`docs/current/schemas/reform-full-h5-expected-schema-v2-…json`).
3. **Upload baselines** — `modal volume put policyengine-us-data-long-term
   projected_datasets_v2/{year}.h5 /crfb-longrun-v2-<stamp>/{year}.h5` plus
   each `.metadata.json` sidecar.
4. **Baseline manifest** — `scripts/build_v2_baseline_manifest.py`
   → `docs/current/manifests/baseline-dataset-manifest-v2-<stamp>.json`;
   record its SHA.
5. **Ledger: G5.5 sentinel approval** — update
   `docs/current/reform-modeling-progress.json`: gate `G5.5`,
   `sentinel_launch_allowed=true`, `paid_modal_launch_allowed=true`, one
   approved cell `2026/option1/static`, nonce
   `v2-every5y-sentinel-<stamp>`, worker/code-bundle SHAs (computed via
   `compute_reform_full_h5_bundle_sha`), schema + baseline manifest paths
   and SHAs, durable target `r2://axiom-corpus/crfb/reform_full_h5`,
   transaction store under the new run prefix, `allowed_paid_call_count=1`,
   `approval_text_or_id` quoting the chat authorization.
6. **Sentinel launch** — `modal run modal_batch/reform_full_h5.py::
   submit_reform_full_h5` with `launch_mode=sentinel`, the v2
   `dataset_template`, both manifests, and `wait_for_completion`. Set
   `CRFB_REQUIRED_TARGET_SOURCE=post_obbba_tob_75y` so worker provenance
   records the v2 target source.
7. **Sentinel verification** — R2 `scenario.h5` + `metadata.json` +
   `complete.json` exist; object SHA equals `metadata.output_h5_sha256`;
   schema validation passed; aggregate the sentinel post-H5 (MicroDF only)
   and compare option1/2026 against the v1 value with the post-OBBBA
   baseline difference explained.
8. **Ledger: G8 full approval** — same fields with the full 192-cell set,
   nonce `v2-every5y-full-<stamp>`, `full_launch_allowed=true`, gate `G8`,
   `approved_pip_freeze_sha256` from the sentinel metadata.
9. **Full launch, recovery, aggregation** — submit, wait, verify every cell
   in R2, aggregate from saved H5s with
   `scripts/aggregate_reform_full_h5_results.py
   --compute-missing-baselines --baseline-dir projected_datasets_v2`,
   publish with the existing dashboard publishers (anchor rows exact,
   intermediate years linearly interpolated and flagged, as in v1).
10. **Behavioral endpoints** — third approval, 24 cells, then the
    behavioral publisher.

## Non-negotiables carried from the Bible

- Full reform output H5 per cell in R2 before any cell is
  production-complete; no aggregate-CSV production path.
- Post-H5 aggregation uses MicroDF/MicroSeries weighted operations only.
- The expected-schema manifest comes from the local proof, never from a
  paid candidate H5; per-year entity rows come from the baseline manifest
  (late years carry donor-clone rows).
- Every paid submitter and worker passes the shared
  preflight-and-consume guard against the canonical ledger.
