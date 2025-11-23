#!/bin/bash
set -e  # Exit on any error

echo "======================================"
echo "CRFB TOB Impacts - Full Build Script"
echo "======================================"
echo ""

# Function to print section headers
print_section() {
    echo ""
    echo "======================================"
    echo "$1"
    echo "======================================"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: Must run from repository root"
    exit 1
fi

# 1. Generate fresh data
print_section "Step 1: Generating Fresh Data"
echo "Running data generation scripts..."
uv run python -m scripts.generate_data
if [ $? -ne 0 ]; then
    echo "❌ Data generation failed"
    exit 1
fi
echo "✓ Data generated successfully"

# 2. Execute notebooks to update outputs
print_section "Step 2: Executing Notebooks"
cd jupyterbook

echo "Executing revenue-impacts.ipynb..."
jupyter nbconvert --to notebook --execute --inplace revenue-impacts.ipynb
if [ $? -ne 0 ]; then
    echo "❌ revenue-impacts.ipynb execution failed"
    exit 1
fi
echo "✓ revenue-impacts.ipynb executed"

echo "Executing household-impacts.ipynb..."
jupyter nbconvert --to notebook --execute --inplace household-impacts.ipynb
if [ $? -ne 0 ]; then
    echo "❌ household-impacts.ipynb execution failed"
    exit 1
fi
echo "✓ household-impacts.ipynb executed"

echo "Executing trust-fund-revenue.ipynb..."
jupyter nbconvert --to notebook --execute --inplace trust-fund-revenue.ipynb
if [ $? -ne 0 ]; then
    echo "❌ trust-fund-revenue.ipynb execution failed"
    exit 1
fi
echo "✓ trust-fund-revenue.ipynb executed"

# 3. Build Jupyter Book
print_section "Step 3: Building Jupyter Book"
echo "Building with MyST..."
myst build --html
if [ $? -ne 0 ]; then
    echo "❌ Jupyter Book build failed"
    exit 1
fi
echo "✓ Jupyter Book built successfully"

cd ..

# 4. Summary
print_section "Build Complete!"
echo "✓ Data generated"
echo "✓ Notebooks executed with fresh data"
echo "✓ Jupyter Book built"
echo ""
echo "Preview the book:"
echo "  cd jupyterbook && myst start"
echo ""
echo "The built site is in: jupyterbook/_build/site/public/"

