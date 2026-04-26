#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
site_dir="$repo_root/.vercel-site"
dashboard_base_path="${NEXT_PUBLIC_BASE_PATH:-}"
dashboard_target="$site_dir${dashboard_base_path:-/}"
paper_target="$dashboard_target/paper"
paper_output="$repo_root/paper/_build"

if [ -f "$repo_root/.vercel-python/bin/activate" ]; then
  # Use the Vercel-local virtualenv when building via `vercel build`.
  # Fall back to the caller's environment for local development.
  # shellcheck disable=SC1091
  source "$repo_root/.vercel-python/bin/activate"
fi

echo "Building CRFB site for Vercel"
echo "  repo root: $repo_root"
echo "  dashboard base path: ${dashboard_base_path:-/}"
echo "  paper path: ${dashboard_base_path:-}/paper/"

rm -rf "$site_dir"
mkdir -p "$dashboard_target" "$paper_target"

if ! command -v quarto >/dev/null 2>&1; then
  echo "Quarto is required to build the citable paper at /paper/." >&2
  exit 1
fi

rm -rf "$paper_output"
quarto render "$repo_root/paper/index.qmd" --to html

if [ ! -d "$paper_output" ]; then
  echo "Could not find Quarto paper output." >&2
  exit 1
fi

if quarto render "$repo_root/paper/index.qmd" --to pdf; then
  echo "Rendered paper PDF."
else
  echo "Paper PDF render skipped; HTML paper is still available." >&2
fi

cp -R "$paper_output/." "$paper_target/"

pushd "$repo_root/dashboard" >/dev/null
NEXT_PUBLIC_BASE_PATH="$dashboard_base_path" bun run build
popd >/dev/null

cp -R "$repo_root/dashboard/out/." "$dashboard_target/"

echo "Combined site output written to $site_dir"
