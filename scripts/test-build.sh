#!/bin/bash

# Test script for MyST book build
# This ensures the book builds correctly before pushing changes

set -e  # Exit on error

echo "🔍 Testing MyST Book Build..."
echo "================================"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Please run 'uv venv --python 3.13' first."
    exit 1
fi

# Navigate to jupyterbook directory
cd jupyterbook

# Execute notebooks to ensure they have outputs
echo ""
echo "📝 Executing notebooks..."
for nb in *.ipynb; do
    if [ -f "$nb" ]; then
        echo "  - Executing $nb..."
        jupyter nbconvert --to notebook --execute --inplace "$nb" --ExecutePreprocessor.timeout=600 2>&1 | tail -1
    fi
done

# Build the book locally
echo ""
echo "📚 Building MyST book..."
# Kill any existing MyST server first
pkill -f "node.*myst" 2>/dev/null || true

# Build and capture output
BUILD_OUTPUT=$(myst build --html 2>&1)
echo "$BUILD_OUTPUT"

# Check for actual build failures (not just warnings)
if echo "$BUILD_OUTPUT" | grep -q "Build failed\|ERROR\|Failed to build"; then
    echo ""
    echo "❌ Build failed!"
    exit 1
fi

# Check if the build directory was created
if [ ! -d "_build/site/public" ]; then
    echo ""
    echo "❌ Build failed - no output directory created"
    exit 1
fi

# Count HTML files to ensure content was generated
HTML_COUNT=$(find _build/site/public -name "*.html" 2>/dev/null | wc -l)
if [ "$HTML_COUNT" -lt 5 ]; then
    echo ""
    echo "❌ Build incomplete - only $HTML_COUNT HTML files generated (expected at least 5)"
    exit 1
fi

echo ""
echo "✅ Build successful!"
echo "  - Generated $HTML_COUNT HTML pages"
echo "  - Output in: jupyterbook/_build/site/public/"
echo ""
echo "You can preview the site locally by running:"
echo "  cd jupyterbook && myst start"
echo ""

exit 0