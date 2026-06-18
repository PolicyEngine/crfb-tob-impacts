# Analysis Notes

This folder contains historical analysis notes and execution specs. It is **not**
the source of the public dashboard data.

The current CRFB result pipeline is the canonical full-H5 pipeline documented in
the repo root README and `docs/current/REFORM_MODELING_BIBLE.md`:

- Static scoring uses the full selected-cell panel.
- Behavioral scoring uses 2026/2100 full-H5 endpoints, with downstream
  multiplier interpolation.
- Dashboard/public data are generated from the canonical `results.csv` surface.

Do not regenerate or publish data from old notebooks or ad hoc CSV exports.
