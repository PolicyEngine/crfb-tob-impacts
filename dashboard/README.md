# Dashboard

This directory contains the Next.js dashboard for `crfb-tob-impacts`.

## Local development

```bash
cd dashboard
npm ci
npm run dev
```

The dashboard runs at `http://localhost:3000`.

## Production-style builds

GitHub Pages builds use a base path:

```bash
cd dashboard
NEXT_PUBLIC_BASE_PATH=/crfb-tob-impacts/dashboard npm run build
```

Vercel preview builds should leave `NEXT_PUBLIC_BASE_PATH` empty.

## Vercel preview CI

PR previews are driven by `.github/workflows/vercel-preview.yml`.

Required GitHub repository secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Those secrets should point to a Vercel project for this dashboard. The workflow deploys from the `dashboard/` directory, builds with `vercel build`, and publishes a preview with `vercel deploy --prebuilt`.
