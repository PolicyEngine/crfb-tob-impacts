# TOB Baseline Harness

This directory now separates the **raw current-law series** from the **generated post-OBBBA baseline**.

## Files

- `tob_current_law_tr2025.csv`
  - Raw current-law TOB annual series used previously in the project.
  - Represents the 2025 Trustees / CMS-style current-law baseline.
- `oasdi_oact_20250805_nominal_delta.csv`
  - Official annual OASDI nominal cash-flow changes from SSA OACT's August 5, 2025 letter, Table 1b.n.
  - Covers 2025-2099.
- `ssa_tob_baseline_75year.csv`
  - Generated output baseline used by downstream scripts.

## Build

Generate a baseline with an explicit HI method:

```bash
python3 scripts/build_tob_baseline.py --hi-method match_oasdi_pct_change
```

Or:

```bash
python3 scripts/build_tob_baseline.py --hi-method current_law
```

## Validation

```bash
python3 scripts/validate_tob_baseline.py
```

or validate an explicit output file:

```bash
python3 scripts/validate_tob_baseline.py data/ssa_tob_baseline_75year.csv
```

## Method notes

- **OASDI** is source-backed from SSA OACT's August 5, 2025 letter, using the nominal annual OASDI cash-flow changes in Table 1b.n.
- **2100 OASDI** is not in Table 1b.n and is currently bridged by carrying forward the 2099 nominal delta.
- **HI** does not yet have a public annual post-OBBBA replacement series in this repo. The harness therefore makes the HI method explicit:
  - `current_law`: keep the 2025 Trustees/CMS current-law HI series unchanged
  - `match_oasdi_pct_change`: scale HI by the same percentage reduction as OASDI until a source-backed annual HI series is available
