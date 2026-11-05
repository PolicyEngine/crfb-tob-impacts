# Paper

This directory holds the Quarto manuscript for the CRFB taxation-of-benefits
study. The site serves the rendered paper at
<https://policyengine.org/us/taxation-of-benefits-reforms/paper/>, next to the
interactive dashboard.

## Publication roles

The project publishes in three places:

- `dashboard/`: the interactive results explorer and the public results files
  under `dashboard/public/data/`
- `paper/`: the citable manuscript, with methods, validation, external
  benchmarks, and bibliography
- `docs/current/` and `analysis/`: operational methodology, pipeline and
  delivery notes, audit findings, and rerun diagnostics

The paper and dashboard cite only results that trace to full-H5 microsimulation
outputs. Each exact anchor in `results.csv` records its run prefix and the SHA-256 hash
of its reform H5 file, and the paper's results tables come from generators that
read the same file. Rerun state, launch identifiers, and recovery details belong
in the operational notes, not in the paper.

## Build

From the repo root:

```bash
quarto render paper/index.qmd
```

Quarto writes `paper/_build/index.html`. `scripts/build_vercel_site.sh` renders
the paper, builds the dashboard, and copies the rendered paper to
`.vercel-site/us/taxation-of-benefits-reforms/paper/` for deployment.

## Authoring model

- `index.qmd` holds the title, abstract, and section includes.
- `sections/` holds the manuscript sections.
- `sections/exhibits/`, mirrored in `exhibits/`, holds generated Markdown
  fragments that the sections include. Regenerate them instead of editing them:
  - `scripts/generate_paper_static_exhibits.py` writes every fragment except
    `headline-summary.md`.
  - `scripts/build_headline_summary.py` writes `headline-summary.md` and
    `dashboard/public/data/headline_summary.csv`.
- `references.bib` holds the bibliography.

`tests/test_paper_text.py` checks that the committed fragments match both
generators, that the paper's reform count matches the dashboard menu, that the
figures written into the prose match `results.csv` and the projected datasets'
metadata, and that the manuscript carries no drafting notes.

## Updating results

1. Publish the new panel to `dashboard/public/data/results.csv`.
2. Run both generators.
3. Run `tests/test_paper_text.py`, `tests/test_headline_summary.py`, and
   `tests/test_release_artifacts.py`, and update any prose figure a test flags.
4. Render the paper and read every changed section.
