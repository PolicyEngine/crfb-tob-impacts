# CRFB Reform Modeling Bible

This is the controlling document for the current CRFB reform-modeling release.
If any script default, old run ledger, chat summary, or stale artifact conflicts
with this file, stop and resolve the conflict here before using it for current
results.

## Current Release Contract

- Baseline method: v2 populace/TR2026, documented in
  [v2-baseline-method.md](v2-baseline-method.md).
- Baseline manifest:
  `docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json`.
- Public baseline run ID:
  `crfb-longrun-v2pop-tr2026-noclone-9f1260b-20260612`.
- Populace base: `populace-us-2024-9f1260b-20260611`.
- Trustees target vintage: 2026 Trustees Reports, intermediate assumptions,
  with OBBBA in current law.
- Tax-threshold assumption actually used by the H5s:
  `trustees-2025-core-thresholds-v1`.
- Static exact years: `2026`, `2028`-`2030`, and every fifth year from `2035`
  through `2100` for all reforms; plus completion anchors where a schedule
  bends — `2032`/`2033` for `option6` and `2062` for `option12`/`option5`
  (see the budget-window-infill, option6-bracket-rescore, and anchor-2062
  provenance docs).
- Behavioral exact years: the `2026`/`2100` endpoints for all reforms, plus
  interior anchors `option12`/`option5`@`2062` and `option6`@`2033`.
  Non-anchor behavioral years use piecewise behavioral/static ratio
  interpolation between consecutive exact anchors; segments whose static
  anchors have opposite signs interpolate behavioral values directly
  (behavioral-anchor-provenance.md). All must be marked as interpolated.
- Reforms in scope: `option1` through `option12`, `reverse_roth`, `tax93`,
  `magi100`, and `tax_panel_2005`.

The `trustees-2025-core-thresholds-v1` name is a PolicyEngine tax-indexing
assumption name, not a target-data vintage. Do not rewrite it in generated
metadata unless the underlying PolicyEngine reform changes.

## Non-Negotiable Artifact Contract

Each exact reform cell must be backed by a durable full reform output H5:

```text
reform_full_h5/year=YYYY/reform=REFORM/scenario.h5
reform_full_h5/year=YYYY/reform=REFORM/metadata.json
reform_full_h5/year=YYYY/reform=REFORM/complete.json
```

Aggregate CSVs are outputs, not production inputs. If an exact result cannot be
traced to a full reform H5 and SHA-256 metadata, it is not a production exact
row.

Current public exact static rows come from:

- `v2pop_tr2026_20260611` and `v2pop_tr2026_noclone_20260612` (June
  production panel)
- `certinfill_9f1260b_20260625` (budget-window infill)
- `magi100_certrepro_20260706` and `tax_panel_2005_certrepro_20260717`
- `noclone_farfix_20260722` (far-anchor family fix)
- `anchor2062_20260723` and `option6_bracketfix_20260723` (2026-07 audit)

Current public exact behavioral rows come from:

- `lsrfix_behavioral_20260719` (endpoints; supersedes the June
  `v2pop_tr2026_*behavioral_20260612` runs, whose substitution channel was
  dead — lsr-substitution-fix-provenance.md)
- `anchor_behavioral_20260723` (interior completion anchors)

Locally scored certified-proof cells carry `scenario.h5` + `metadata.json`
with SHA-256 lineage; `complete.json` markers exist for Modal-run cells
only.

The unified public results are:

- `results.csv`
- `dashboard/public/data/results.csv`

The machine-readable lineage contract is:

- `dashboard/public/data/results_contract.json`

## Aggregation Rules

- All totals, means, shares, and distributional calculations must use
  MicroSeries or MicroDataFrame operations such as `.sum()` and `.mean()`.
- Do not manually multiply by `household_weight`, `person_weight`,
  `tax_unit_weight`, or `spm_unit_weight`.
- Do not fetch PolicyEngine weight variables directly for production
  aggregation.
- Row-level IDs may be used to join saved full reform H5 outputs to baseline
  rows, but weights must be carried from MicroSeries or MicroDataFrame metadata
  and aggregation must stay in MicroDF.
- Public `results.csv` values must be microsimulation outputs or documented
  interpolation between microsimulation outputs. No display normalization,
  post-hoc TOB calibration, or target substitution is allowed.

## Current Interpolation Rules

Static rows:

- Exact rows are the full-H5 anchor years.
- Non-anchor annual rows are linear interpolation between exact full-H5 years.
- `full_h5_result_type` must distinguish exact from interpolated rows.

Behavioral rows:

- Exact full-H5 behavioral anchors are the 2026/2100 endpoints plus the
  interior completion anchors listed above.
- Non-anchor years interpolate behavioral/static ratios piecewise between
  consecutive anchors and apply them to the current static annual rows;
  segments whose static anchor values have opposite signs interpolate the
  behavioral values directly (a ratio has no meaning across a static
  zero-crossing).
- `run_prefix` for interpolated behavioral rows is
  `behavioral_anchor_ratio_interpolation_20260723`.

## Current Documentation And Release Surface

Current docs must not ship old run ledgers as release controls. Release packages
should include:

- this file
- [methodology.md](methodology.md)
- [pipeline.md](pipeline.md)
- [deliverables.md](deliverables.md)
- [v2-baseline-method.md](v2-baseline-method.md)
- [v2-launch-runbook.md](v2-launch-runbook.md)
- current public CSV/JSON artifacts under `dashboard/public/data/` and
  `results/`

Historical May 2026 run ledgers, 20260522 selected-panel metadata, and 5a35713
submission manifests belong in git history or an explicit archive, not in the
current release package.

## Validation Checklist

Before merge or publication:

- `dashboard/public/data/results.csv` and root `results.csv` contain only the
  current v2/TR2026 row set.
- No current public results contain stale `20260522`, `5a35713`, or selected
  panel source labels.
- Exact rows preserve scenario H5 URIs and output hashes.
- `dashboard/public/data/results_contract.json` validates against
  `contracts/results.schema.json`.
- `dashboard/public/data/distributional.json` is regenerated from saved reform
  H5s and baseline MicroSeries/MicroDataFrame weighting.
- Release package tests pass and package only the current contract outputs.
