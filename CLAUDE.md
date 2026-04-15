# Project Notes

This repository now has two public publication surfaces:

- `dashboard/`: the Next.js/Tailwind current-results dashboard. In the Vercel
  combined site it is served at `/`.
- `paper/`: the Quarto manuscript. In the Vercel combined site it is served at
  `/paper/`.

The old Jupyter Book/MyST report has been deleted. Do not recreate
`jupyterbook/` or add MyST build steps.

## Common Commands

```bash
make dashboard      # build the Next dashboard
make paper          # render the Quarto paper HTML
make site           # build the combined Vercel output in .vercel-site/
make test           # run Python tests
```

## Release Rule

The dashboard should show current results only. The paper should carry the
citable narrative, methodology, sources, and formal interpretation. Operational
docs under `docs/current/` and `analysis/` carry rerun provenance and audit
details.
