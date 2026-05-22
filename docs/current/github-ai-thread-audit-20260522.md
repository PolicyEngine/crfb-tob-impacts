# GitHub AI Thread Audit - 2026-05-22

This audits the current working tree against the GitHub AI discussion trail,
especially Discussion #114 and issues #85-#115.

## Current Status

The current artifact pipeline mostly satisfies the newer full-H5 contract:

- `results.csv` and `dashboard/public/data/results.csv` are the unified public
  result surface.
- Public results contain 1,800 rows: 12 reforms, 75 years, and static plus
  labor-supply response scoring.
- Static rows contain 276 exact selected-year full-H5 rows and 624 display
  interpolation rows.
- Labor-supply response rows contain 24 exact endpoint full-H5 rows and 876
  documented endpoint-ratio interpolation rows.
- Exact rows carry durable R2 `scenario.h5`, `metadata.json`, and
  `complete.json` URIs.
- `results.csv` applies no reference baseline substitution, display
  normalization, or post-hoc TOB calibration.
- Old public CSV surfaces such as `all_static_results.csv`,
  `all_dynamic_results.csv`, old prior-reference workbooks, and special-case
  CSVs are deleted from the active checkout.

## Addressed

- Full 2026-2100 annual dashboard coverage is present.
- Static and labor-supply response rows are in one public CSV with
  `scoring_type` labels.
- Labor-supply response is the public term; generated public CSVs no longer
  expose `conventional` or `dynamic`.
- Raw reform H5 persistence is present for exact static rows and behavioral
  endpoint rows.
- Baseline assumptions and model-output artifacts exist for aggregates,
  targets, diagnostics, indexed parameters, policy parameters, and reform
  parameters.
- Release tests now fail if stale CSV artifacts reappear outside the current
  full-H5/input allowlist.
- Release tests guard that public exact rows match the raw full-H5 aggregate
  artifact and that the post-OBBBA TOB baseline remains diagnostic-only.

## Not Fully Closed

- Discussion #114 is stale. It still says the dashboard/static artifacts were
  rebuilt so current-law TOB baselines match Trustees through the 2035
  transition. Current artifacts intentionally expose raw microsimulation TOB
  gaps versus the post-OBBBA target instead of forcing alignment.
- Issue #103 remains substantively relevant. The late-horizon Roth-family
  deterioration from 2095 to 2100 is an exact full-H5 result, not interpolation,
  and should remain a caveat until fully explained.
- Issue #111 remains substantively relevant. Late-year support/provenance
  treatment needs to be carried as a visible caveat rather than silently treated
  as clean.
- Issue #85 is only partially addressed under the newer endpoint-ratio approach.
  Exact endpoints and interpolation provenance are labeled, but there is not a
  same-record sample/BOTEC ratio audit table matching the old ask.
- Email and Granola cross-checks were not completed in this pass: `gog` has no
  active account configured, and the local Granola CLI cache path/config did not
  load Max's cache.

## Result Readout

Mechanically, the current outputs are much cleaner than the prior aggregate
surface: they are unified, current-contract, provenance-labeled, and backed by
durable H5s for exact rows.

Substantively, they are not caveat-free. The raw baseline income-tax series is
very high, peaking at 251.1 percent of GDP in 2045 in
`baseline_aggregates.csv`. This is intentionally no longer hidden by display
normalization, but it must be described as a model diagnostic/caveat wherever
baseline levels are interpreted.

The Roth-family endpoint movement is also material. For `option12`, the exact
static revenue impact changes from -$597.4B in 2095 to -$1,401.5B in 2100.
Because both are exact selected-year H5 rows, the dashboard should not describe
that as a chart artifact.

Bottom line: the artifact pipeline is largely implemented, but the GitHub
discussion should be updated before using it as the authoritative audit trail,
and the current results should be presented as reproducible full-H5 results
with explicit income-tax and late-horizon caveats.
