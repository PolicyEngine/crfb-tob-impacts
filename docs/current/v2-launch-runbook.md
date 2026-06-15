# V2 every-fifth-year reform panel: launch runbook

Authorization: Max, by chat on 2026-06-09 — "if you're really confident and
can do it stepwise with sentinels to see the data you can also rerun the
modal reform analysis (just every 5y)". Stepwise-with-sentinels is binding:
one paid sentinel cell, inspect the data, then the full panel. All
targets are the 2026 Trustees Reports (released June 9, 2026; OBBBA in
current law).

Panel: years `2026, 2030, 2035, 2040, …, 2100` (16) × 14 reforms
(`option1–option12`, `reverse_roth`, `tax93`) × `static` = 224 cells,
followed by behavioral endpoints (`2026, 2100` × 14 = 28 cells). The
current public release is the full-H5 v2/populace/TR2026 run
documented in `docs/current/REFORM_MODELING_BIBLE.md`; historical May
ledgers are not part of the current release surface.

## Sequence

1. **Build datasets** — produce the 16 v2/populace/TR2026 baseline
   H5s and metadata sidecars; every year must pass its build-time gates.
2. **Local proof** — run one static proof cell against a local v2 dataset and
   record the expected schema manifest under
   `docs/current/schemas/reform-full-h5-expected-schema-v2pop-...json`.
3. **Upload baselines** — upload every baseline H5 and metadata sidecar to the
   durable run prefix used by the full-H5 workers.
4. **Baseline manifest** — record all baseline H5 URIs, hashes, row counts,
   policyengine-us/data provenance, and target-source metadata under
   `docs/current/manifests/baseline-dataset-manifest-v2pop*.json`.
5. **Sentinel launch and verification** — run one paid sentinel cell; require
   R2 `scenario.h5`, `metadata.json`, and `complete.json`; verify object hash,
   schema, row counts, and MicroDF-only aggregate sanity before the full run.
6. **Full static launch** — submit all approved static cells only after the
   sentinel passes. Workers write full reform H5s; aggregate CSVs are derived
   artifacts only.
7. **Behavioral endpoints** — submit endpoint behavioral cells after static
   coverage is complete; publish exact endpoint rows and linearly interpolated
   behavioral rows with interpolation flags.
8. **Publication** — rebuild `results.csv`, dashboard data, results contract,
   distributional JSON, and the release package from the current full-H5 run.

## Non-negotiables carried from the Bible

- Full reform output H5 per cell in R2 before any cell is
  production-complete; no aggregate-CSV production path.
- Post-H5 aggregation uses MicroDF/MicroSeries weighted operations only.
- The expected-schema manifest comes from the local proof, never from a
  paid candidate H5; per-year entity rows come from the baseline manifest.
- The current release uses the v2/populace long-run data. Historical
  selected-panel artifacts are archival only.
