# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Social Security taxation reform analysis project with two main components:
1. **Jupyter Book documentation** - Research report and analysis using MyST-NB (Jupyter Book 2.0)
2. **React dashboard** - Interactive policy impact visualization tool

## Development Workflow

**⚠️ IMPORTANT: Always work in pull requests to avoid breaking the main branch!**

### Creating a PR for changes:
```bash
# Create a new branch for your changes
git checkout -b fix/description-of-change

# Make your changes
# ... edit files ...

# For Jupyter notebooks, ALWAYS execute them before committing
cd jupyterbook
jupyter nbconvert --to notebook --execute --inplace *.ipynb

# Commit and push
git add -A
git commit -m "Description of changes"
git push origin fix/description-of-change

# Create PR using GitHub CLI
gh pr create --title "Fix: Description" --body "Details of what was fixed"
```

### PR Checks
The CI will automatically check:
1. **Notebook execution**: All notebooks must have outputs and execute without errors
2. **Python tests**: All tests must pass
3. **Build validation**: The Jupyter Book must build successfully

Never merge a PR with failing checks!

## Build and Development Commands

### Setup with uv (Python 3.13)
```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv --python 3.13
source .venv/bin/activate
uv pip install -e .
uv pip install -e .[dev]  # For development dependencies
```

### Jupyter Book Documentation

**⚠️ IMPORTANT: Always deploy using CI/CD, never manually!**
- DO NOT manually copy files to the `docs/` directory
- DO NOT manually run deployment commands
- Let GitHub Actions handle all deployments to ensure consistency

For local development only:
```bash
# Build the Jupyter Book (uses MyST-NB)
source .venv/bin/activate
cd jupyterbook
myst build --html  # For local preview

# The built documentation will be in jupyterbook/_build/site/public/
```

### React Dashboard
```bash
# Navigate to the dashboard directory
cd policy-impact-dashboard

# Install dependencies
npm install

# Development server (runs on http://localhost:3000)
npm start

# Run tests
npm test

# Production build
npm run build
```

## High-Level Architecture

### Documentation Structure (Jupyter Book)
The Jupyter Book uses MyST-NB and contains:
- **intro.md** - Landing page and overview
- **policy-options.md** - Detailed policy proposals
- **prior-research.md** - Literature review
- **methodology.ipynb** - Technical analysis methods
- **policy-impacts.md** - Aggregate fiscal impacts
- **household-impacts.ipynb** - Distributional analysis with animated visualizations across years 2026-2035
- **bibliography.md** - References

Key configuration:
- `_config.yml` - MyST-NB configuration with forced notebook execution
- `_toc.yml` - Table of contents structure
- `hide_code_cells.py` - Custom script for hiding implementation details

### Dashboard Application
The React dashboard (`policy-impact-dashboard/`) provides interactive policy visualization:

**Core Components:**
- `PolicySelector` - Dropdown interface for policy selection with credit value options
- `ImpactDisplay` - Visualization of 10-year budgetary impacts
- `csvLoader` - Utility for loading and processing policy impact CSV data

**Data Flow:**
1. CSV data (`policy_impacts.csv`) contains pre-computed policy impacts
2. App loads CSV on mount and processes into policy options
3. User selects policy → displays corresponding impact data
4. Supports policies with variable credit values (e.g., $100-$900 refundable credits)

### Data Integration
- Analysis notebooks generate `policy_impacts_results.csv` with fiscal estimates
- Dashboard consumes this CSV for visualization
- Both components share the same underlying PolicyEngine analysis
- Household impacts notebook generates multi-year data (2026-2035) with animated visualizations using Plotly animation frames

## Key Development Patterns

### Jupyter Book
- Uses MyST-NB (not legacy Jupyter Book 1.x)
- Notebooks execute on build with 600-second timeout
- Custom CSS in `_static/custom.css`
- Code cells can be toggled with show/hide prompts

### React Dashboard
- TypeScript with functional components
- No external state management (local state only)
- CSV parsing with PapaParse library
- Dynamic policy data based on CSV content

## Testing

### Dashboard Tests
```bash
cd policy-impact-dashboard
npm test          # Run all tests
npm test -- --coverage  # With coverage report
```

Tests use React Testing Library and focus on component rendering and data handling.

## Common Issues and Solutions

### Jupyter Book Tables Not Displaying
**Problem**: Tables or charts appear blank in the built Jupyter Book even though the code is correct.

**Root Cause**: Jupyter Book uses pre-computed outputs from notebook cells. If a notebook hasn't been executed, there are no outputs to display.

**Solution**: Execute the notebook before building:
```bash
source .venv/bin/activate
cd jupyterbook
jupyter nbconvert --to notebook --execute --inplace your-notebook.ipynb
jupyter-book build .
```

**Prevention**: Always execute notebooks after making changes to ensure outputs are saved:
- Use `jupyter nbconvert --execute` for batch execution
- Or run cells manually in Jupyter Lab/Notebook and save

### Test-Driven Debugging for Tables
When tables aren't displaying correctly:
1. Create a standalone Python script to test the table generation
2. Verify the output HTML is correct
3. Check that notebook cells have saved outputs
4. Rebuild the Jupyter Book after executing notebooks

### PolicyEngine Data Links
For PolicyEngine US data documentation, use: https://policyengine.github.io/policyengine-us-data

### Table Formatting Best Practices
When creating pivot tables for display:
- Use `reset_index()` to convert index to columns
- Rename columns to remove technical names (e.g., `rename(columns={'reform_display': ''})`)
- Set `columns.name = None` to remove multi-level column labels
- Use `to_html(escape=False)` to allow HTML formatting like `<b>` tags

## CRITICAL: Option 4 Tax Credit Amount
**⚠️ IMPORTANT**: Option 4 (Social Security Tax Credit System) uses a **$500** credit amount, NOT $900 or any other value. This is hardcoded throughout the analysis:
- The reforms.py file has `credit_amount=500` as the default
- All notebooks reference "$500 Tax Credit"
- The entire book and documentation analyze a $500 credit
- If you see $900 in any data files, they are INCORRECT and need regeneration
- **NEVER** change this to $900 unless explicitly instructed - the entire analysis is based on $500

## Household Impact Calculation Performance
The household impact calculations are **vectorized**, not iterative:
- Each reform-year combination processes ALL employment income levels simultaneously using numpy arrays
- Total: 7 reforms × 10 years = 70 vectorized calculations (not thousands)
- The calculation time is from complex tax simulations, not from iteration count
- Add status logging when generating household impacts since each calculation can take several minutes

### Chapter Ordering and Naming
- Place comparison chapters (like external estimates) after presenting your own results
- Use descriptive filenames that match the content (e.g., `external-estimates.md` not `prior-research.md` for comparisons)
- Update both the filename and `_toc.yml` when renaming chapters

### Enhanced Hovercards in Plotly
When showing only impact charts, include baseline and reform values in hover data:
```python
customdata=df[['baseline_value', 'reform_value']],
hovertemplate='<b>Impact:</b> %{y}<br>' +
             '<b>Baseline:</b> %{customdata[0]}<br>' +
             '<b>Reform:</b> %{customdata[1]}<br>'
```

### Jupyter Book Build Issues
- **Multiple file warnings**: Delete duplicate files (e.g., both `.md` and `.ipynb` versions)
- **Missing bibtex references**: Check `references.bib` for all cited keys
- **Slow builds**: Use `jupyter-book build .` without `--all` for incremental builds

## Important Development Lessons Learned

### Always Check All Branches Before Assuming Work is Lost
- Work may exist on unmerged branches (e.g., DTrim99/issue16 had critical fixes)
- Use `git branch -r` to list all remote branches
- Check unmerged commits with: `git log origin/branch-name --not origin/main`
- Cherry-pick valuable commits from unmerged branches when needed

### Jupyter Notebooks Must Have Executed Outputs for CI Tests
- The test suite (test_charts.py) requires notebooks to have executed outputs with Plotly charts
- Notebooks without outputs will fail CI even if code is correct
- Execute notebooks before committing: `jupyter nbconvert --execute --to notebook --inplace notebook.ipynb`
- This is especially important when cherry-picking or merging changes that strip outputs

### GitHub Actions Deployment
**⚠️ CRITICAL: All deployments must happen through CI/CD**
- The GitHub Actions workflow automatically builds and deploys the Jupyter Book
- NEVER manually build and commit files to the `docs/` directory
- NEVER run `myst build` and then commit the output
- The CI/CD pipeline ensures proper base URLs and consistent builds

**Debugging deployment issues:**
- Use `gh run list --workflow=workflow-name.yml` to check run status
- Get failed step details: `gh api /repos/owner/repo/actions/runs/RUN_ID/jobs | jq '.jobs[] | select(.conclusion=="failure")'`
- Open failed runs in browser: `gh run view RUN_ID --web`
- Remember: Background monitoring in Claude doesn't persist after response - can't provide updates after sending message

### Commit Frequently to Avoid Losing Work
- Complex notebook edits should be committed after each major change
- Don't rely on uncommitted local changes surviving across sessions
- Use descriptive commit messages to track what was done
- Always push branches even if not ready to merge - better to have unmerged work than lost work