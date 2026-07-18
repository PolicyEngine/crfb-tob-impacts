from __future__ import annotations

import os
import hashlib
import json
from pathlib import Path

import modal


VERSION = os.environ.get("CRFB_LONGRUN_HF_VERSION", "crfb-longrun-20260517")
DATA_VERSION = os.environ.get("CRFB_LONGRUN_DATA_VERSION")
REQUIRE_DEFAULT_DATASET = (
    os.environ.get("CRFB_LONGRUN_REQUIRE_DEFAULT_DATASET", "1") != "0"
)
STAGING_PREFIX = f"staging/{VERSION}"
REPO_ID = os.environ.get("CRFB_LONGRUN_HF_REPO_ID", "policyengine/policyengine-us-data")
REPO_TYPE = "model"
# Defaults to the long_term storage of a local crfb-pinned us-data checkout.
# Override with CRFB_LONGRUN_LOCAL_DIR to publish from another location.
LOCAL_LONG_TERM_DIR = Path(
    os.environ.get(
        "CRFB_LONGRUN_LOCAL_DIR",
        str(
            Path.home()
            / "PolicyEngine"
            / "policyengine-us-data-crfb-pin"
            / "policyengine_us_data"
            / "storage"
            / "long_term"
        ),
    )
)
LOCAL_RELEASE_DIR = Path(
    os.environ.get("CRFB_LONGRUN_RELEASE_DIR", "/tmp/crfb_hf_publish")
)
REMOTE_LONG_TERM_DIR = Path("/root/long_term")
REMOTE_RELEASE_DIR = Path("/root/release")


if not LOCAL_LONG_TERM_DIR.exists() and not REMOTE_LONG_TERM_DIR.exists():
    raise FileNotFoundError(f"Missing long-term data dir: {LOCAL_LONG_TERM_DIR}")
if (
    not (LOCAL_RELEASE_DIR / "release_manifest.json").exists()
    and not (REMOTE_RELEASE_DIR / "release_manifest.json").exists()
):
    raise FileNotFoundError(
        f"Missing generated release manifest in {LOCAL_RELEASE_DIR}"
    )
if (
    not (LOCAL_RELEASE_DIR / "trace.tro.jsonld").exists()
    and not (REMOTE_RELEASE_DIR / "trace.tro.jsonld").exists()
):
    raise FileNotFoundError(f"Missing generated TRACE TRO in {LOCAL_RELEASE_DIR}")


image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install("huggingface_hub==0.36.0")
    .add_local_dir(LOCAL_LONG_TERM_DIR, str(REMOTE_LONG_TERM_DIR), copy=True)
    .add_local_dir(LOCAL_RELEASE_DIR, str(REMOTE_RELEASE_DIR), copy=True)
)
app = modal.App("crfb-longrun-hf-publisher")


def _batched(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _artifact_by_path(release_manifest: dict) -> dict[str, dict]:
    return {
        artifact["path"]: artifact
        for artifact in release_manifest.get("artifacts", {}).values()
        if artifact.get("path")
    }


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("huggingface-token")],
    timeout=24 * 60 * 60,
    memory=2048,
)
def publish(batch_size: int = 10, tag: bool = True) -> dict:
    from huggingface_hub import (
        CommitOperationAdd,
        CommitOperationCopy,
        CommitOperationDelete,
        HfApi,
    )
    from huggingface_hub.errors import RevisionNotFoundError

    token = os.environ["HUGGING_FACE_TOKEN"]
    api = HfApi()
    if not tag:
        raise ValueError(
            "tag=False is not supported because the release manifest artifact "
            f"revisions point at {VERSION!r}."
        )

    try:
        existing = api.repo_info(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            revision=VERSION,
            token=token,
        )
    except RevisionNotFoundError:
        existing = None
    if existing is not None:
        raise RuntimeError(
            f"Revision {VERSION!r} already exists at {existing.sha}; "
            "refusing to overwrite a published CRFB long-run release."
        )

    files = sorted(REMOTE_LONG_TERM_DIR.glob("*.h5")) + sorted(
        REMOTE_LONG_TERM_DIR.glob("*.h5.metadata.json")
    )
    if len(files) != 150:
        raise RuntimeError(f"Expected 150 long-term files, found {len(files)}")

    release_manifest_path = REMOTE_RELEASE_DIR / "release_manifest.json"
    release_manifest = json.loads(release_manifest_path.read_text())
    manifest_data_version = release_manifest.get("data_package", {}).get("version")
    if DATA_VERSION is not None and manifest_data_version != DATA_VERSION:
        raise RuntimeError(
            f"Expected release manifest data_package.version == {DATA_VERSION!r}; "
            f"got {manifest_data_version!r}."
        )
    artifacts_by_path = _artifact_by_path(release_manifest)
    if len(artifacts_by_path) < 150:
        raise RuntimeError(
            "Expected release manifest to track at least 150 artifacts; got "
            f"{len(artifacts_by_path)}"
        )
    if REQUIRE_DEFAULT_DATASET and "enhanced_cps_2024.h5" not in artifacts_by_path:
        raise RuntimeError(
            "Release manifest must include enhanced_cps_2024.h5 so "
            "policyengine.py can certify the default dataset and the long-run "
            "datasets from the same manifest."
        )
    expected_hashes = {
        path: artifact["sha256"]
        for path, artifact in artifacts_by_path.items()
        if path.startswith("long_term/")
    }
    expected_paths = {f"long_term/{path.name}" for path in files}
    if set(expected_hashes) != expected_paths:
        missing = sorted(expected_paths.difference(expected_hashes))
        extra = sorted(set(expected_hashes).difference(expected_paths))
        raise RuntimeError(
            "Release manifest paths do not match captured files: "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        repo_path = f"long_term/{path.name}"
        if digest != expected_hashes[repo_path]:
            raise RuntimeError(
                f"Captured file hash mismatch for {repo_path}: "
                f"{digest} != {expected_hashes[repo_path]}"
            )

    staged_commits = []
    for batch_index, batch in enumerate(_batched(files, batch_size), start=1):
        operations = [
            CommitOperationAdd(
                path_in_repo=f"{STAGING_PREFIX}/long_term/{path.name}",
                path_or_fileobj=str(path),
            )
            for path in batch
        ]
        result = api.create_commit(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            token=token,
            operations=operations,
            commit_message=(f"Stage CRFB long-run data {VERSION} batch {batch_index}"),
            num_threads=4,
        )
        staged_commits.append(result.oid)
        print(f"Staged batch {batch_index}: {len(batch)} files; commit {result.oid}")

    missing_staged = []
    for path in files:
        staged_path = f"{STAGING_PREFIX}/long_term/{path.name}"
        if not api.file_exists(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            filename=staged_path,
            token=token,
        ):
            missing_staged.append(staged_path)
    if missing_staged:
        raise RuntimeError(f"Missing staged files: {missing_staged[:5]}")

    final_operations = (
        [
            CommitOperationCopy(
                src_path_in_repo=f"{STAGING_PREFIX}/long_term/{path.name}",
                path_in_repo=f"long_term/{path.name}",
            )
            for path in files
            if path.name.endswith(".h5")
        ]
        + [
            CommitOperationAdd(
                path_in_repo=f"long_term/{path.name}",
                path_or_fileobj=str(path),
            )
            for path in files
            if path.name.endswith(".metadata.json")
        ]
        + [
            CommitOperationAdd(
                path_in_repo=f"releases/{VERSION}/release_manifest.json",
                path_or_fileobj=str(REMOTE_RELEASE_DIR / "release_manifest.json"),
            ),
            CommitOperationAdd(
                path_in_repo=f"releases/{VERSION}/trace.tro.jsonld",
                path_or_fileobj=str(REMOTE_RELEASE_DIR / "trace.tro.jsonld"),
            ),
        ]
    )
    final_commit = api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        token=token,
        operations=final_operations,
        commit_message=f"Promote and publish CRFB long-run release {VERSION}",
        num_threads=4,
    )
    print(f"Promoted data and release manifest at commit {final_commit.oid}")

    cleanup_operations = [
        CommitOperationDelete(path_in_repo=f"{STAGING_PREFIX}/long_term/{path.name}")
        for path in files
    ]
    cleanup_commit = api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        token=token,
        operations=cleanup_operations,
        commit_message=f"Clean up staged CRFB long-run data {VERSION}",
        num_threads=4,
    )
    print(f"Cleaned staging files at commit {cleanup_commit.oid}")

    missing_production = []
    for path in files:
        production_path = f"long_term/{path.name}"
        if not api.file_exists(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            filename=production_path,
            revision=cleanup_commit.oid,
            token=token,
        ):
            missing_production.append(production_path)
    for path in [
        f"releases/{VERSION}/release_manifest.json",
        f"releases/{VERSION}/trace.tro.jsonld",
    ] + [path for path in artifacts_by_path if not path.startswith("long_term/")]:
        if not api.file_exists(
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            filename=path,
            revision=cleanup_commit.oid,
            token=token,
        ):
            missing_production.append(path)
    if missing_production:
        raise RuntimeError(f"Missing production files: {missing_production[:5]}")

    api.create_tag(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        token=token,
        tag=VERSION,
        revision=cleanup_commit.oid,
        exist_ok=False,
    )
    print(f"Created tag {VERSION} at {cleanup_commit.oid}")

    return {
        "version": VERSION,
        "repo_id": REPO_ID,
        "file_count": len(files),
        "staging_prefix": STAGING_PREFIX,
        "staged_commits": staged_commits,
        "final_commit": final_commit.oid,
        "cleanup_commit": cleanup_commit.oid,
        "tagged": tag,
    }


@app.local_entrypoint()
def main(batch_size: int = 10, tag: bool = True) -> None:
    print(publish.remote(batch_size=batch_size, tag=tag))
