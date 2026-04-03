from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from policyengine_core.data import Dataset

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


DEFAULT_TAX_ASSUMPTION_FACTORY = "create_wage_indexed_core_thresholds_reform"
DEFAULT_BASELINE_CACHE_DIR = REPO_ROOT / ".cache" / "saved_h5_baselines"
DEFAULT_REQUIRED_PROFILE = "ss-payroll-tob"
DEFAULT_REQUIRED_TARGET_SOURCE = "oact_2025_08_05_provisional"
DEFAULT_REQUIRED_TAX_ASSUMPTION = "trustees-core-thresholds-v1"
DEFAULT_MIN_CALIBRATION_QUALITY = "aggregate"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _candidate_tax_assumption_modules() -> list[Path]:
    candidates: list[Path] = []
    env_module = os.environ.get("CRFB_TAX_ASSUMPTION_MODULE")
    if env_module:
        candidates.append(Path(env_module).expanduser())
    candidates.extend(
        [
            Path.home()
            / ".codex-worktrees"
            / "us-data-calibration-contract"
            / "policyengine_us_data"
            / "datasets"
            / "cps"
            / "long_term"
            / "tax_assumptions.py",
            REPO_ROOT.parent
            / "policyengine-us-data"
            / "policyengine_us_data"
            / "datasets"
            / "cps"
            / "long_term"
            / "tax_assumptions.py",
        ]
    )
    return candidates


def resolve_tax_assumption_module(module_path: str | None) -> Path:
    if module_path:
        path = Path(module_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    for candidate in _candidate_tax_assumption_modules():
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Could not resolve a tax assumption module. Pass --tax-assumption-module "
        "or set CRFB_TAX_ASSUMPTION_MODULE."
    )


def _find_git_repo_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def policyengine_us_fingerprint() -> dict[str, object]:
    import policyengine_us

    package_file = Path(policyengine_us.__file__).resolve()
    fingerprint: dict[str, object] = {
        "package_file": str(package_file),
        "package_file_sha256": _sha256_file(package_file),
        "package_mtime_ns": package_file.stat().st_mtime_ns,
        "package_size": package_file.stat().st_size,
        "version": getattr(policyengine_us, "__version__", None),
    }
    repo_root = _find_git_repo_root(package_file)
    if repo_root is None:
        return fingerprint

    fingerprint["repo_root"] = str(repo_root)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if head.returncode == 0:
        fingerprint["git_head"] = head.stdout.strip()

    status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if status.returncode == 0:
        dirty_entries = []
        for line in status.stdout.splitlines():
            if not line:
                continue
            rel_path = line[3:]
            if " -> " in rel_path:
                rel_path = rel_path.split(" -> ", 1)[1]
            candidate = repo_root / rel_path
            entry: dict[str, object] = {"status": line[:2], "path": rel_path}
            if candidate.exists():
                stat = candidate.stat()
                entry["mtime_ns"] = stat.st_mtime_ns
                entry["size"] = stat.st_size
            dirty_entries.append(entry)
        fingerprint["git_dirty_entries"] = dirty_entries

    return fingerprint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score CRFB reforms on saved H5 datasets, optionally composing in a "
            "baseline tax-assumption reform and comparing against an existing results CSV."
        )
    )
    parser.add_argument(
        "--dataset",
        action="append",
        required=True,
        help=(
            "Dataset spec in the form label=/absolute/path/to/<year>.h5. "
            "The year is inferred from the H5 filename stem."
        ),
    )
    parser.add_argument(
        "--reform",
        action="append",
        required=True,
        help="Reform ID to score, e.g. option1. Repeatable.",
    )
    parser.add_argument(
        "--scoring-type",
        default="static",
        choices=["static", "dynamic"],
        help="CRFB scoring type to use when building the reform.",
    )
    parser.add_argument(
        "--tax-assumption-module",
        help=(
            "Path to the Python module defining the baseline tax-assumption reform "
            "factory. If omitted, the script will try common local checkouts."
        ),
    )
    parser.add_argument(
        "--tax-assumption-factory",
        default=DEFAULT_TAX_ASSUMPTION_FACTORY,
        help="Factory function name inside --tax-assumption-module.",
    )
    parser.add_argument(
        "--tax-assumption-start-year",
        type=int,
        default=2035,
        help="Start year passed to the baseline tax-assumption reform factory.",
    )
    parser.add_argument(
        "--tax-assumption-end-year",
        type=int,
        default=2100,
        help="End year passed to the baseline tax-assumption reform factory.",
    )
    parser.add_argument(
        "--compare-csv",
        help="Optional existing CRFB results CSV to compare against.",
    )
    parser.add_argument(
        "--compare-units",
        default="billions",
        choices=["billions", "dollars"],
        help=(
            "Units used by --compare-csv impact columns. "
            "Legacy CRFB result CSVs are in billions."
        ),
    )
    parser.add_argument(
        "--baseline-cache-dir",
        default=str(DEFAULT_BASELINE_CACHE_DIR),
        help="Directory for caching baseline summaries keyed by dataset and tax assumption.",
    )
    parser.add_argument(
        "--output",
        help="Optional output CSV path. Defaults to stdout only.",
    )
    parser.add_argument(
        "--required-profile",
        default=DEFAULT_REQUIRED_PROFILE,
        help="Expected calibration profile name recorded in the saved-H5 metadata.",
    )
    parser.add_argument(
        "--required-target-source",
        default=DEFAULT_REQUIRED_TARGET_SOURCE,
        help="Expected target source name recorded in the saved-H5 metadata.",
    )
    parser.add_argument(
        "--required-tax-assumption",
        default=DEFAULT_REQUIRED_TAX_ASSUMPTION,
        help="Expected tax assumption name recorded in the saved-H5 metadata.",
    )
    parser.add_argument(
        "--minimum-calibration-quality",
        default=DEFAULT_MIN_CALIBRATION_QUALITY,
        choices=["aggregate", "approximate", "exact"],
        help="Minimum calibration quality required in the saved-H5 metadata.",
    )
    return parser.parse_args()


def load_tax_assumption_reform(
    module_path: Path, factory_name: str, start_year: int, end_year: int
):
    spec = importlib.util.spec_from_file_location("tax_assumptions", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load tax assumption module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, factory_name)
    return factory(start_year=start_year, end_year=end_year)


def parse_dataset_spec(spec: str) -> tuple[str, Path, int]:
    if "=" not in spec:
        raise ValueError(f"Invalid dataset spec '{spec}'. Expected label=/path/to/year.h5")
    label, raw_path = spec.split("=", 1)
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        year = int(path.stem)
    except ValueError as exc:
        raise ValueError(
            f"Could not infer year from dataset filename '{path.name}'. "
            "Use files named like 2075.h5."
        ) from exc
    return label, path, year


def resolve_dataset_year(
    dataset_path: Path,
    *,
    inferred_year: int,
    metadata: dict[str, object],
) -> int:
    metadata_year = metadata.get("year")
    if metadata_year is None:
        return inferred_year

    metadata_year = int(metadata_year)
    if metadata_year != inferred_year:
        raise ValueError(
            f"Dataset {dataset_path} filename implies year {inferred_year}, "
            f"but metadata records year {metadata_year}."
        )
    return metadata_year


def baseline_cache_path(
    *,
    dataset_path: Path,
    module_path: Path,
    module_sha256: str,
    policyengine_fingerprint: dict[str, object],
    factory_name: str,
    start_year: int,
    end_year: int,
    cache_dir: str,
) -> Path:
    stat = dataset_path.stat()
    key = json.dumps(
        {
            "dataset_path": str(dataset_path),
            "dataset_size": stat.st_size,
            "dataset_mtime_ns": stat.st_mtime_ns,
            "module_path": str(module_path),
            "module_sha256": module_sha256,
            "factory_name": factory_name,
            "start_year": start_year,
            "end_year": end_year,
            "policyengine_us": policyengine_fingerprint,
        },
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return Path(cache_dir).expanduser().resolve() / f"{digest}.json"


def load_or_compute_baseline(
    *,
    year: int,
    dataset: Dataset,
    dataset_path: Path,
    baseline_reform,
    module_path: Path,
    module_sha256: str,
    policyengine_fingerprint: dict[str, object],
    factory_name: str,
    start_year: int,
    end_year: int,
    cache_dir: str,
    load_baseline_fn,
    baseline_result_type,
):
    cache_path = baseline_cache_path(
        dataset_path=dataset_path,
        module_path=module_path,
        module_sha256=module_sha256,
        policyengine_fingerprint=policyengine_fingerprint,
        factory_name=factory_name,
        start_year=start_year,
        end_year=end_year,
        cache_dir=cache_dir,
    )
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"  Loaded baseline cache {cache_path}", flush=True)
        return baseline_result_type(**payload)

    baseline = load_baseline_fn(
        year=year,
        dataset_name=dataset,
        baseline_reform=baseline_reform,
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "revenue": baseline.revenue,
                "tob_medicare_hi": baseline.tob_medicare_hi,
                "tob_oasdi": baseline.tob_oasdi,
                "tob_total": baseline.tob_total,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"  Wrote baseline cache {cache_path}", flush=True)
    return baseline


def build_rows(args: argparse.Namespace) -> pd.DataFrame:
    from year_runner import (
        BaselineResult,
        BATCH_EMPLOYER_NET_REFORMS,
        compute_reform_result,
        get_reform_lookups,
        load_baseline,
    )
    from runtime_config import validate_dataset_contract

    tax_assumption_module = resolve_tax_assumption_module(args.tax_assumption_module)
    module_sha256 = _sha256_file(tax_assumption_module)
    policyengine_fingerprint = policyengine_us_fingerprint()

    baseline_reform = load_tax_assumption_reform(
        tax_assumption_module,
        args.tax_assumption_factory,
        args.tax_assumption_start_year,
        args.tax_assumption_end_year,
    )
    reform_functions, dynamic_functions = get_reform_lookups()

    rows = []
    for dataset_spec in args.dataset:
        label, dataset_path, inferred_year = parse_dataset_spec(dataset_spec)
        metadata = validate_dataset_contract(
            dataset_path,
            required_profile=args.required_profile,
            minimum_calibration_quality=args.minimum_calibration_quality,
            required_target_source=args.required_target_source,
            required_tax_assumption=args.required_tax_assumption,
            reject_aggregate=False,
            allow_unvalidated=False,
        )
        year = resolve_dataset_year(
            dataset_path,
            inferred_year=inferred_year,
            metadata=metadata,
        )
        print(f"Dataset {label}: {dataset_path} (year {year})", flush=True)
        dataset = Dataset.from_file(str(dataset_path))
        baseline_start = time.time()
        baseline = load_or_compute_baseline(
            year=year,
            dataset=dataset,
            dataset_path=dataset_path,
            baseline_reform=baseline_reform,
            module_path=tax_assumption_module,
            module_sha256=module_sha256,
            policyengine_fingerprint=policyengine_fingerprint,
            factory_name=args.tax_assumption_factory,
            start_year=args.tax_assumption_start_year,
            end_year=args.tax_assumption_end_year,
            cache_dir=args.baseline_cache_dir,
            load_baseline_fn=load_baseline,
            baseline_result_type=BaselineResult,
        )
        print(
            "  Baseline loaded in "
            f"{time.time() - baseline_start:.1f}s "
            f"(revenue ${baseline.revenue / 1e9:.2f}B, "
            f"OASDI TOB ${baseline.tob_oasdi / 1e9:.2f}B, "
            f"HI TOB ${baseline.tob_medicare_hi / 1e9:.2f}B)"
            ,
            flush=True,
        )
        for reform_id in args.reform:
            reform_start = time.time()
            print(f"  Scoring {reform_id}...", flush=True)
            result = compute_reform_result(
                reform_id=reform_id,
                year=year,
                scoring_type=args.scoring_type,
                dataset_name=dataset,
                baseline=baseline,
                reform_functions=reform_functions,
                dynamic_functions=dynamic_functions,
                employer_net_reforms=BATCH_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
                baseline_reform=baseline_reform,
            )
            result["dataset_label"] = label
            result["dataset_path"] = str(dataset_path)
            rows.append(result)
            print(
                "    Done in "
                f"{time.time() - reform_start:.1f}s "
                f"(revenue ${result['revenue_impact'] / 1e9:+.2f}B, "
                f"OASDI ${result['tob_oasdi_impact'] / 1e9:+.2f}B, "
                f"HI ${result['tob_medicare_hi_impact'] / 1e9:+.2f}B)"
                ,
                flush=True,
            )
            if args.output:
                partial_df = pd.DataFrame(rows)
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                partial_df.to_csv(output_path, index=False, float_format="%.10f")
                print(f"    Wrote partial results to {output_path}", flush=True)

    df = pd.DataFrame(rows)
    ordered_columns = [
        "dataset_label",
        "dataset_path",
        "reform_name",
        "year",
        "baseline_revenue",
        "reform_revenue",
        "revenue_impact",
        "baseline_tob_oasdi",
        "reform_tob_oasdi",
        "tob_oasdi_impact",
        "baseline_tob_medicare_hi",
        "reform_tob_medicare_hi",
        "tob_medicare_hi_impact",
        "baseline_tob_total",
        "reform_tob_total",
        "tob_total_impact",
        "scoring_type",
    ]
    extra_columns = [column for column in df.columns if column not in ordered_columns]
    return df[ordered_columns + extra_columns]


def maybe_compare(
    df: pd.DataFrame,
    compare_csv: str | None,
    *,
    compare_units: str,
) -> pd.DataFrame:
    if not compare_csv:
        return df
    compare = pd.read_csv(compare_csv)
    compare_columns = [
        "reform_name",
        "year",
        "revenue_impact",
        "tob_oasdi_impact",
        "tob_medicare_hi_impact",
    ]
    compare = compare[compare_columns].rename(
        columns={column: f"{column}_old" for column in compare_columns if column not in {"reform_name", "year"}}
    )
    unit_scale = 1e9 if compare_units == "billions" else 1.0
    for column in ["revenue_impact_old", "tob_oasdi_impact_old", "tob_medicare_hi_impact_old"]:
        compare[column] = compare[column] * unit_scale
    merged = df.merge(compare, on=["reform_name", "year"], how="left", validate="many_to_one")
    for column in ["revenue_impact", "tob_oasdi_impact", "tob_medicare_hi_impact"]:
        merged[f"{column}_delta"] = merged[column] - merged[f"{column}_old"]
    return merged


def main() -> None:
    args = parse_args()
    df = build_rows(args)
    df = maybe_compare(df, args.compare_csv, compare_units=args.compare_units)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.10f")
        print(f"Wrote {output_path}", flush=True)

    print(df.to_json(orient="records", indent=2))


if __name__ == "__main__":
    main()
