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

Optional subpath builds use a base path:

```bash
cd dashboard
NEXT_PUBLIC_BASE_PATH=/crfb-tob-impacts/dashboard npm run build
```

Vercel builds leave `NEXT_PUBLIC_BASE_PATH` empty so the dashboard is served at
the site root. The Quarto paper is published separately at `/paper/`.

## Vercel deployment

Repo-level Vercel deploys are driven by `.github/workflows/deploy-vercel.yml`.

Required GitHub repository secrets:

- `VERCEL_TOKEN`
- `VERCEL_ORG_ID`
- `VERCEL_PROJECT_ID`

Those secrets should point to the combined-site Vercel project at repo root. The workflow builds the dashboard plus Quarto paper together and deploys previews for pull requests and production on `main`.
