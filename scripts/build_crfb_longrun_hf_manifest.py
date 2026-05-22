from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from policyengine_us_data.utils.release_manifest import (
    build_release_manifest,
    serialize_release_manifest,
)
from policyengine_us_data.utils.trace_tro import (
    build_trace_tro_from_release_manifest,
    serialize_trace_tro,
)


DEFAULT_HF_REPO = "policyengine/policyengine-us-data"
DEFAULT_OUTPUT_DIR = Path("/tmp/crfb_hf_publish")
DEFAULT_DATASET_KEY = "enhanced_cps_2024"
DEFAULT_DATASET_PATH = "enhanced_cps_2024.h5"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_hf_json(*, repo_id: str, revision: str, path: str) -> dict:
    url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{path}"
    headers = {"User-Agent": "crfb-tob-impacts"}
    token = os.environ.get("HUGGING_FACE_TOKEN") or os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers)) as response:
        return json.load(response)


def _base_release_manifest(
    *,
    repo_id: str,
    data_version: str,
    base_release_manifest: Path | None,
    base_release_manifest_path: str | None,
    base_release_manifest_revision: str | None,
) -> dict:
    if base_release_manifest is not None:
        return _load_json(base_release_manifest)
    manifest_path = (
        base_release_manifest_path
        or f"releases/{data_version}/release_manifest.json"
    )
    revision = base_release_manifest_revision or data_version
    return _fetch_hf_json(repo_id=repo_id, revision=revision, path=manifest_path)


def _production_manifest(long_term_dir: Path) -> dict:
    path = long_term_dir / "long_run_production_manifest.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _manifest_value(
    production_manifest: dict,
    *keys: str,
) -> str | None:
    value = production_manifest
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value if isinstance(value, str) and value else None


def _long_term_files(long_term_dir: Path) -> list[Path]:
    h5s = sorted(long_term_dir.glob("*.h5"))
    sidecars = sorted(long_term_dir.glob("*.h5.metadata.json"))
    if len(h5s) != 75:
        raise RuntimeError(f"Expected 75 long-run H5s, found {len(h5s)}.")
    if len(sidecars) != 75:
        raise RuntimeError(
            f"Expected 75 long-run metadata sidecars, found {len(sidecars)}."
        )
    missing_sidecars = [
        h5.name for h5 in h5s if not (long_term_dir / f"{h5.name}.metadata.json").exists()
    ]
    if missing_sidecars:
        raise RuntimeError(f"Missing metadata sidecars for: {missing_sidecars[:5]}")
    return h5s + sidecars


def _enhanced_cps_artifact(base_manifest: dict, *, data_version: str) -> dict:
    artifact = dict(base_manifest.get("artifacts", {}).get(DEFAULT_DATASET_KEY) or {})
    if not artifact:
        for candidate in base_manifest.get("artifacts", {}).values():
            if candidate.get("path") == DEFAULT_DATASET_PATH:
                artifact = dict(candidate)
                break
    if not artifact:
        raise RuntimeError(
            f"Base release manifest does not include {DEFAULT_DATASET_PATH}."
        )
    artifact["revision"] = data_version
    return artifact


def build_manifest(
    *,
    long_term_dir: Path,
    output_dir: Path,
    version: str,
    data_version: str,
    model_version: str | None,
    core_version: str | None,
    repo_id: str,
    base_release_manifest: Path | None,
    base_release_manifest_path: str | None,
    base_release_manifest_revision: str | None,
) -> dict:
    production = _production_manifest(long_term_dir)
    resolved_model_version = model_version or _manifest_value(
        production,
        "package_versions",
        "policyengine-us",
    )
    resolved_core_version = core_version or _manifest_value(
        production,
        "package_versions",
        "policyengine-core",
    )
    if resolved_model_version is None:
        raise RuntimeError("Could not resolve policyengine-us version.")
    if resolved_core_version is None:
        raise RuntimeError("Could not resolve policyengine-core version.")

    base_manifest = _base_release_manifest(
        repo_id=repo_id,
        data_version=data_version,
        base_release_manifest=base_release_manifest,
        base_release_manifest_path=base_release_manifest_path,
        base_release_manifest_revision=base_release_manifest_revision,
    )
    base_version = base_manifest.get("data_package", {}).get("version")
    if base_version != data_version:
        raise RuntimeError(
            f"Base release manifest version {base_version!r} != {data_version!r}."
        )

    long_term_files = _long_term_files(long_term_dir)
    manifest = build_release_manifest(
        files_with_repo_paths=[
            (path, f"long_term/{path.name}") for path in long_term_files
        ],
        version=data_version,
        repo_id=repo_id,
        model_package_version=resolved_model_version,
        core_package_metadata={
            "name": "policyengine-core",
            "version": resolved_core_version,
        },
        build_id=f"policyengine-us-data-{version}",
        pipeline_run_id=_manifest_value(production, "run_id"),
        data_package_git_sha=_manifest_value(production, "source_sha"),
        run_context={
            "crfb_longrun_release": version,
            "long_run_production_run_id": _manifest_value(production, "run_id"),
            "long_run_source_sha": _manifest_value(production, "source_sha"),
            "base_data_release": data_version,
        },
    )
    manifest["artifacts"][DEFAULT_DATASET_KEY] = _enhanced_cps_artifact(
        base_manifest,
        data_version=data_version,
    )
    manifest.setdefault("default_datasets", {})["national"] = DEFAULT_DATASET_KEY

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "release_manifest.json"
    trace_path = output_dir / "trace.tro.jsonld"
    manifest_path.write_bytes(serialize_release_manifest(manifest))
    trace_path.write_bytes(
        serialize_trace_tro(build_trace_tro_from_release_manifest(manifest))
    )
    return {
        "release_manifest": str(manifest_path),
        "trace_tro": str(trace_path),
        "artifact_count": len(manifest["artifacts"]),
        "data_version": data_version,
        "model_version": resolved_model_version,
        "core_version": resolved_core_version,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the CRFB long-run HF release manifest and TRACE TRO from "
            "annual long-run H5s plus the finalized base enhanced CPS artifact."
        )
    )
    parser.add_argument("--long-term-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--version",
        default=os.environ.get("CRFB_LONGRUN_HF_VERSION", "crfb-longrun-20260518"),
    )
    parser.add_argument("--data-version", default=os.environ.get("CRFB_LONGRUN_DATA_VERSION"))
    parser.add_argument("--model-version")
    parser.add_argument("--core-version")
    parser.add_argument("--hf-repo", default=DEFAULT_HF_REPO)
    parser.add_argument("--base-release-manifest", type=Path)
    parser.add_argument("--base-release-manifest-path")
    parser.add_argument("--base-release-manifest-revision")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.data_version:
        raise SystemExit("--data-version or CRFB_LONGRUN_DATA_VERSION is required.")
    result = build_manifest(
        long_term_dir=args.long_term_dir,
        output_dir=args.output_dir,
        version=args.version,
        data_version=args.data_version,
        model_version=args.model_version,
        core_version=args.core_version,
        repo_id=args.hf_repo,
        base_release_manifest=args.base_release_manifest,
        base_release_manifest_path=args.base_release_manifest_path,
        base_release_manifest_revision=args.base_release_manifest_revision,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
