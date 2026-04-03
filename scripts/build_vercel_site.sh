#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
site_dir="$repo_root/.vercel-site"
dashboard_base_path="${NEXT_PUBLIC_BASE_PATH:-/dashboard}"

if [ -f "$repo_root/.vercel-python/bin/activate" ]; then
  # Use the Vercel-local virtualenv when building via `vercel build`.
  # Fall back to the caller's environment for local development.
  # shellcheck disable=SC1091
  source "$repo_root/.vercel-python/bin/activate"
fi

echo "Building CRFB site for Vercel"
echo "  repo root: $repo_root"
echo "  dashboard base path: $dashboard_base_path"

rm -rf "$site_dir"
mkdir -p "$site_dir/dashboard"

pushd "$repo_root/jupyterbook" >/dev/null
export BASE_URL=""
myst build --html

if [ -d "_build/html" ]; then
  docs_output="_build/html"
elif [ -d "_build/site/public" ]; then
  docs_output="_build/site/public"
else
  echo "Could not find MyST build output." >&2
  exit 1
fi
popd >/dev/null

pushd "$repo_root/dashboard" >/dev/null
NEXT_PUBLIC_BASE_PATH="$dashboard_base_path" npm run build
popd >/dev/null

cp -R "$repo_root/jupyterbook/$docs_output/." "$site_dir/"
cp -R "$repo_root/dashboard/out/." "$site_dir/dashboard/"

echo "Combined site output written to $site_dir"
