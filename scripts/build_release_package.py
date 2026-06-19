# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.tob_baseline import GENERATED_BASELINE_PATH, validate_tob_baseline_manifest

RESULTS = REPO / "results"
PACKAGE_ROOT = RESULTS / "release_packages"
POST_OBBBA_TOB_BASELINE = GENERATED_BASELINE_PATH
POST_OBBBA_TOB_BASELINE_MANIFEST = POST_OBBBA_TOB_BASELINE.with_suffix(".manifest.json")


@dataclass(frozen=True)
class ReleasePackage:
    package_dir: Path
    manifest_path: Path
    archive_path: Path | None


REQUIRED_FILES: tuple[tuple[str, Path], ...] = (
    ("results", REPO / "results.csv"),
    ("results", REPO / "results.csv.metadata.json"),
    ("results", RESULTS / "modal_runs_production" / "static_cells.csv"),
    ("results", RESULTS / "modal_runs_production" / "behavioral_endpoint_cells.csv"),
    ("results", RESULTS / "modal_runs_production" / "balanced_fix_results.csv"),
    (
        "results",
        RESULTS / "modal_runs_production" / "balanced_fix_results_metadata.json",
    ),
    ("dashboard_data", REPO / "dashboard" / "public" / "data" / "results.csv"),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "balanced_fix_results.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "balanced_fix_results_metadata.json",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "ssa_economic_projections.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "hi_taxable_payroll.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_aggregates.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_indexed_parameters.csv",
    ),
    (
        "dashboard_data",
        REPO
        / "dashboard"
        / "public"
        / "data"
        / "baseline_indexed_parameter_summary.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_indexing_growth.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_calibration_targets.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_calibration_diagnostics.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_policy_parameters.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_reform_parameters.csv",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "baseline_assumptions_metadata.json",
    ),
    (
        "dashboard_data",
        REPO
        / "dashboard"
        / "public"
        / "data"
        / "post_obbba_tob_baseline_manifest.json",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "distributional.json",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "results_contract.json",
    ),
    (
        "dashboard_data",
        REPO / "dashboard" / "public" / "data" / "tob_explainer.json",
    ),
    ("root_compat", REPO / "results.csv"),
    ("docs", REPO / "docs" / "current" / "README.md"),
    ("docs", REPO / "docs" / "current" / "deliverables.md"),
    ("docs", REPO / "docs" / "current" / "methodology.md"),
    ("docs", REPO / "docs" / "current" / "pipeline.md"),
    ("docs", REPO / "docs" / "current" / "REFORM_MODELING_BIBLE.md"),
    ("docs", REPO / "docs" / "current" / "v2-baseline-method.md"),
    ("docs", REPO / "docs" / "current" / "v2-launch-runbook.md"),
    ("paper", REPO / "paper" / "sections" / "03-methods.qmd"),
    ("paper", REPO / "paper" / "sections" / "04-results-and-validation.qmd"),
    ("paper", REPO / "paper" / "sections" / "05-results-framework.qmd"),
    ("paper", REPO / "paper" / "sections" / "06-publication-boundary.qmd"),
    ("scripts", REPO / "scripts" / "build_dashboard_baseline_assumptions.py"),
    ("scripts", REPO / "scripts" / "build_dashboard_payroll_denominators.py"),
    ("scripts", REPO / "scripts" / "build_hi_expenditures_tr2026.py"),
    ("scripts", REPO / "scripts" / "build_distributional_data.py"),
    ("scripts", REPO / "scripts" / "build_results_contract.py"),
    ("scripts", REPO / "scripts" / "build_tob_explainer_data.py"),
    ("scripts", REPO / "scripts" / "publish_balanced_fix_results.py"),
    ("scripts", REPO / "scripts" / "publish_dashboard_results.py"),
    ("scripts", REPO / "scripts" / "publish_behavioral_endpoint_dashboard_results.py"),
    ("scripts", REPO / "scripts" / "publish_full_h5_static_dashboard_results.py"),
    ("modal", REPO / "modal_batch" / "balanced_fix.py"),
    ("package", REPO / "pyproject.toml"),
    ("package", REPO / "src" / "balanced_fix.py"),
    ("package", REPO / "src" / "cli.py"),
    ("package", REPO / "src" / "dashboard_baseline_assumptions.py"),
    ("package", REPO / "src" / "runtime_config.py"),
    ("package", REPO / "src" / "hi_expenditures.py"),
    ("package", REPO / "src" / "tax_assumption_loader.py"),
    ("package", REPO / "src" / "tob_baseline.py"),
    ("tests", REPO / "tests" / "test_release_artifacts.py"),
    ("tests", REPO / "tests" / "test_dashboard_baseline_assumptions.py"),
    ("source_data", POST_OBBBA_TOB_BASELINE_MANIFEST),
)

OPTIONAL_FILES: tuple[tuple[str, Path], ...] = ()

DATA_SOURCE_GLOBS: tuple[str, ...] = (
    "data/*.csv",
    "data/tr2026_sources.manifest.json",
    "reproducibility.lock.toml",
)

DIRECTORY_SOURCES: tuple[tuple[str, Path], ...] = (
    ("built_dashboard", REPO / "dashboard" / "out"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a client/review release package for the CRFB TOB artifacts."
    )
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--package-name", default=None)
    parser.add_argument("--no-archive", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def copy_file(
    source: Path, package_dir: Path, records: list[dict[str, object]], category: str
) -> None:
    relative = source.relative_to(REPO)
    if any(record["path"] == str(relative) for record in records):
        return
    target = package_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records.append(
        {
            "category": category,
            "path": str(relative),
            "size_bytes": target.stat().st_size,
            "sha256": file_sha256(target),
        }
    )


def copy_tree(
    source_root: Path,
    package_dir: Path,
    records: list[dict[str, object]],
    category: str,
) -> None:
    for source in sorted(source_root.rglob("*")):
        if source.is_file():
            copy_file(source, package_dir, records, category)


def baseline_metadata_paths() -> list[Path]:
    paths: set[Path] = set()
    for csv_path in [
        REPO / "dashboard" / "public" / "data" / "baseline_calibration_targets.csv",
        REPO / "dashboard" / "public" / "data" / "baseline_calibration_diagnostics.csv",
    ]:
        if not csv_path.exists():
            continue
        with csv_path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                raw_path = (row.get("dataset_path") or "").strip()
                if not raw_path:
                    continue
                path = (REPO / raw_path).resolve()
                if path.exists() and path.name.endswith(".h5.metadata.json"):
                    paths.add(path)

    for metadata_path in list(paths):
        for manifest_name in [
            "calibration_manifest.json",
            "long_run_production_manifest.json",
        ]:
            manifest_path = metadata_path.parent / manifest_name
            if manifest_path.exists():
                paths.add(manifest_path.resolve())

    return sorted(paths)


def archive_package(package_dir: Path) -> Path:
    archive_path = package_dir.with_suffix(".zip")
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir.parent))
    return archive_path


def build_release_package(
    *,
    package_root: Path = PACKAGE_ROOT,
    package_name: str | None = None,
    archive: bool = True,
) -> ReleasePackage:
    generated_at = datetime.now(UTC)
    if package_name is None:
        package_name = f"crfb_tob_release_{generated_at.strftime('%Y%m%d_%H%M%S')}"
    package_dir = package_root / package_name
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    tob_manifest = validate_tob_baseline_manifest(
        POST_OBBBA_TOB_BASELINE,
        POST_OBBBA_TOB_BASELINE_MANIFEST,
    )
    missing_required: list[str] = []
    for category, source in REQUIRED_FILES:
        if source.exists():
            copy_file(source, package_dir, records, category)
        else:
            missing_required.append(str(source.relative_to(REPO)))
    if missing_required:
        raise FileNotFoundError(
            "Missing required release package files: " + ", ".join(missing_required)
        )

    copied_optional: list[str] = []
    for category, source in OPTIONAL_FILES:
        if source.exists():
            copy_file(source, package_dir, records, category)
            copied_optional.append(str(source.relative_to(REPO)))

    for pattern in DATA_SOURCE_GLOBS:
        for source in sorted(REPO.glob(pattern)):
            if source.is_file():
                copy_file(source, package_dir, records, "source_data")

    for category, source_root in DIRECTORY_SOURCES:
        if source_root.exists():
            copy_tree(source_root, package_dir, records, category)

    for source in baseline_metadata_paths():
        copy_file(source, package_dir, records, "baseline_metadata")

    status = git_value("status", "--short")
    manifest = {
        "package_name": package_name,
        "generated_at": generated_at.isoformat(),
        "repo": {
            "path": str(REPO),
            "head": git_value("rev-parse", "HEAD"),
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(status),
            "status_short": status.splitlines() if status else [],
        },
        "post_obbba_tob_baseline": {
            "path": str(POST_OBBBA_TOB_BASELINE.relative_to(REPO)),
            "manifest": str(POST_OBBBA_TOB_BASELINE_MANIFEST.relative_to(REPO)),
            "scenario_id": tob_manifest["scenario_id"],
            "baseline_kind": tob_manifest["baseline_kind"],
            "not_law": tob_manifest["not_law"],
            "law_mode": tob_manifest["law_mode"],
            "hi_bridge_method": tob_manifest["bridge_methods"]["hi_method"],
            "baseline_sha256": tob_manifest["baseline_sha256"],
        },
        "required_files_count": len(REQUIRED_FILES),
        "optional_files_copied": copied_optional,
        "baseline_metadata_files_copied": [
            record["path"]
            for record in records
            if record["category"] == "baseline_metadata"
        ],
        "files_count": len(records),
        "files": records,
        "manifest_note": (
            "release_manifest.json is not listed in files to avoid a "
            "self-referential checksum."
        ),
    }

    manifest_path = package_dir / "release_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    archive_path = archive_package(package_dir) if archive else None
    return ReleasePackage(
        package_dir=package_dir,
        manifest_path=manifest_path,
        archive_path=archive_path,
    )


def main() -> int:
    args = parse_args()
    package = build_release_package(
        package_root=args.package_root,
        package_name=args.package_name,
        archive=not args.no_archive,
    )
    print(f"Release package: {package.package_dir}")
    print(f"Release manifest: {package.manifest_path}")
    if package.archive_path is not None:
        print(f"Release archive: {package.archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
