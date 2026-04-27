# Exhibits

This directory contains generated Markdown fragments that the Quarto manuscript
includes directly.

Why this exists:

- it gives the paper a stable structure before results are frozen
- it lets the dashboard and paper consume the same underlying artifacts
- it reduces manual copy-paste drift between the paper and the live app

Expected files:

- `validation-sentinels.md`
- `external-benchmarks.md`
- `results-overview.md`
- `household-impacts.md`
- `revenue-impacts.md`
- `balanced-fix.md`
- `conventional-results.md`

During drafting these files may contain placeholders. Before publication they
should be overwritten by generated content derived from the checked result
artifacts.

Current generator:

- `python ../scripts/generate_paper_static_exhibits.py`
- `python ../scripts/generate_paper_conventional_exhibits.py`
