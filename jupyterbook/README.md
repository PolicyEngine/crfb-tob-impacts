
## Building the Project

To avoid stale numbers in the documentation, use the build script which regenerates all data and notebooks from scratch:

```bash
./build.sh
```

This script will:
1. ✓ Generate fresh revenue and household impact data
2. ✓ Execute all Jupyter notebooks with the new data
3. ✓ Build the Jupyter Book with MyST

The script ensures all numbers in the documentation match the latest analysis.

### Manual Steps

If you need to run steps individually:

```bash
# Generate data
uv run python -m scripts.generate_data

# Execute notebooks
cd jupyterbook
jupyter nbconvert --to notebook --execute --inplace revenue-impacts.ipynb
jupyter nbconvert --to notebook --execute --inplace household-impacts.ipynb
jupyter nbconvert --to notebook --execute --inplace trust-fund-revenue.ipynb

# Build book
myst build --html

# Preview
myst start
```

### CI/CD Integration

The build script can be integrated into CI/CD to ensure the published documentation always reflects the latest data.\\$\\$