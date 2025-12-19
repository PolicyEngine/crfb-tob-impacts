# Social Security Taxation Reform Dashboard

Interactive React dashboard for visualizing the fiscal impacts of Social Security benefit taxation reform options.

## Quick Start

```bash
cd dashboard
npm install
npm run dev      # Development server at http://localhost:5173
npm run build    # Production build
npm test         # Run tests (14 tests)
```

## Deployment

The dashboard deploys automatically via GitHub Actions alongside the Jupyter Book:

- **Jupyter Book**: https://policyengine.github.io/crfb-tob-impacts/
- **Dashboard**: https://policyengine.github.io/crfb-tob-impacts/dashboard/

The workflow (`.github/workflows/deploy-jupyterbook.yml`) builds both and combines them into a single GitHub Pages deployment.

## Features

- **8 reform options** with descriptions and fiscal impacts
- **10-year and 75-year projections** with interactive Plotly charts
- **Trust fund breakdown** showing OASDI vs Medicare HI allocation
- **Economic context** showing impacts as % of taxable payroll and % of GDP
- **External estimates comparison** (CBO, JCT, Tax Foundation)

## Data Sources

| File | Description | Source |
|------|-------------|--------|
| `public/data/75_year_tf_splits.csv` | Reform impacts by year | PolicyEngine microsimulation |
| `public/data/ssa_economic_projections.csv` | Taxable payroll & GDP projections | [SSA 2025 Trustees Report Table VI.G6](https://www.ssa.gov/oact/tr/2025/lr6g6.html) |

### Updating Data

1. **PolicyEngine results**: Re-run the batch computation in `../batch/` after upstream fixes
2. **SSA projections**: Download updated data from the Trustees Report link above

## Architecture

```
src/
├── components/
│   ├── ReformSelector.tsx    # Dropdown to pick reform option
│   ├── ImpactChart.tsx       # Plotly bar/line charts
│   ├── ComparisonTable.tsx   # External estimates table
│   └── Header.tsx            # PolicyEngine-styled header
├── utils/
│   └── dataLoader.ts         # CSV parsing + economic calculations
├── types.ts                  # TypeScript interfaces + reform definitions
└── App.tsx                   # Main app layout
```

## Known Issues

- **Trust fund split inverted**: Currently shows ~20% OASDI / ~80% Medicare HI instead of the expected ~59% / ~41%. This is due to a bug in policyengine-us PR #6750 (fix committed). Data will need regeneration after the fix is merged.

## Tech Stack

- Vite + React 19 + TypeScript
- Plotly.js for charts
- Vitest + React Testing Library for tests
- PolicyEngine styling (Inter font, teal `#2C6496` palette)
