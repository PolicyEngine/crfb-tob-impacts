# Paper

This directory is the citable manuscript track for the Social Security
taxation-of-benefits project.

It is intentionally separate from:

- `dashboard/` - the live interactive current-results app
- `docs/current/` - operational methodology, pipeline, and delivery notes
- `analysis/` - audit findings and rerun diagnostics

## Why this exists

The project now has two distinct publication needs:

1. a stable narrative surface that CRFB and external readers can cite
2. a live interactive surface for exploring current results

This Quarto manuscript is for the first need. The dashboard remains the second.

## Build

From the repo root:

```bash
quarto render paper/index.qmd
```

Rendered output will be written to:

- `paper/_build/index.html`
- `paper/_build/index.pdf` if a working PDF toolchain is available

## Authoring model

- `index.qmd` is the main manuscript entrypoint
- `sections/` contains manuscript sections
- `exhibits/` contains generated Markdown fragments that the paper includes
- `references.bib` carries forward the source spine from the original paper and
  adds the current Trustees and PolicyEngine documentation references

## Intended workflow

1. keep the manuscript structure and source coverage current as release
   artifacts evolve
2. generate Markdown exhibit fragments from shared artifacts into `exhibits/`
3. update the small amount of interpretation text that depends on frozen values
4. render and circulate the manuscript as the citable companion to the dashboard

## Current status

This is the citable manuscript track for the current release package. It
preserves the full option menu, methodology, validation framing, exhibit
contract, and source spine. Remaining work before journal-style circulation is
primarily editorial: tighten the abstract/conclusion around the frozen release
and copyedit the generated exhibits.
