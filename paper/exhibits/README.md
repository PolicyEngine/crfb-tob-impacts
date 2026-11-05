# Exhibits

These generated Markdown fragments mirror `paper/sections/exhibits/`, which the
manuscript sections include. Regenerate them instead of editing them:

- `scripts/generate_paper_static_exhibits.py` writes `results-overview.md`,
  `full-h5-results-summary.md`, `revenue-impacts.md`,
  `budget-window-anchors.md`, `external-benchmarks.md`,
  `labor-supply-response-status.md`, and `household-impacts.md`.
- `scripts/build_headline_summary.py` writes `headline-summary.md`.

`tests/test_paper_text.py` fails when a committed fragment differs from its
generator's output.
