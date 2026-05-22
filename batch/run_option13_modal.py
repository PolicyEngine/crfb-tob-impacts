#!/usr/bin/env python3
"""
Run Option 13 (Balanced Fix) and Option 14 (Option 12 vs Balanced Fix) on Modal.

Option 13: Gap-closing "traditional fix" baseline (50% benefit cuts + 50% rate increases)
           Does NOT include employer payroll tax reform - provides apples-to-apples comparison
Option 14: Option 12 (Extended Roth-Style Swap) vs the balanced fix baseline

Usage:
    modal run batch/run_option13_modal.py --years 2035,2036,2037
    modal run batch/run_option13_modal.py --years 2035 --option14-only  # Skip option13 if already done
"""

import json
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

try:
    import modal
except ModuleNotFoundError:

    class _LocalModalFunction:
        def __init__(self, fn):
            self._fn = fn

        def __call__(self, *args, **kwargs):
            return self._fn(*args, **kwargs)

        def starmap(self, args):
            return [self._fn(*arg) for arg in args]

        def spawn(self, *args, **kwargs):
            raise RuntimeError("Modal is required to spawn remote Option 13 jobs.")

    class _LocalApp:
        def __init__(self, *_args, **_kwargs):
            pass

        def function(self, *_args, **_kwargs):
            return lambda fn: _LocalModalFunction(fn)

        def local_entrypoint(self, *_args, **_kwargs):
            return lambda fn: fn

    class _LocalVolume:
        @staticmethod
        def from_name(*_args, **_kwargs):
            return _LocalVolume()

        def commit(self):
            pass

    class _LocalImage:
        @staticmethod
        def debian_slim(*_args, **_kwargs):
            return _LocalImage()

        def pip_install(self, *_args, **_kwargs):
            return self

        def env(self, *_args, **_kwargs):
            return self

        def add_local_dir(self, *_args, **_kwargs):
            return self

        def run_commands(self, *_args, **_kwargs):
            return self

    class _LocalModal:
        App = _LocalApp
        Volume = _LocalVolume
        Image = _LocalImage
        Secret = _LocalVolume

    modal = _LocalModal()

# Get the project root (parent of batch/)
PROJECT_ROOT = Path(__file__).parent.parent
CONTAINER_ROOT = Path("/app")


def runtime_path(relative_name: str) -> Path:
    """Prefer the container mount, but fall back to the local repo when available."""
    container_path = CONTAINER_ROOT / relative_name
    if container_path.exists():
        return container_path
    return PROJECT_ROOT / relative_name


def resolve_local_env_path(env_name: str) -> Path | None:
    raw = os.environ.get(env_name)
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{env_name} does not exist: {path}")
    return path


DATA_DIR = runtime_path("data")
SRC_DIR = runtime_path("src")
CONTAINER_SNAPSHOT_DIR = CONTAINER_ROOT / "projected_datasets_snapshot"
LOCAL_PROJECTED_DATASETS_SNAPSHOT = resolve_local_env_path(
    "CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH"
)


def results_root(output_prefix: str = "") -> Path:
    prefix = output_prefix.strip("/")
    root = Path("/results")
    if prefix:
        root = root / prefix
    return root


def configure_runtime_snapshot_env() -> None:
    """Point runtime dataset resolution at the mounted exact snapshot when present."""
    mounted_baselines = Path("/baselines/crfb-longrun-20260520-5a35713-annual")
    if mounted_baselines.exists():
        os.environ.setdefault(
            "CRFB_DATASET_TEMPLATE",
            "/baselines/crfb-longrun-20260520-5a35713-annual/{year}.h5",
        )
        return

    if not CONTAINER_SNAPSHOT_DIR.exists():
        return

    snapshot_path = str(CONTAINER_SNAPSHOT_DIR)
    os.environ.setdefault("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", snapshot_path)
    os.environ.setdefault("CRFB_PROJECTED_DATASETS_PATH", snapshot_path)


def default_output_prefix() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"special_case_reruns/option13-14-{timestamp}"


def default_submission_manifest_path(output_prefix: str) -> Path:
    slug = output_prefix.strip("/").replace("/", "__")
    return PROJECT_ROOT / "results" / "special_case_submissions" / f"{slug}.json"


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


app = modal.App("option13-test")

# Create volume for results
results_volume = modal.Volume.from_name("crfb-results", create_if_missing=True)
BASELINE_VOLUME_NAME = os.environ.get(
    "CRFB_REFORM_FULL_H5_BASELINE_VOLUME_NAME",
    "policyengine-us-data-long-term",
)
BASELINE_VOLUME_MOUNT_PATH = os.environ.get(
    "CRFB_REFORM_FULL_H5_BASELINE_VOLUME_MOUNT_PATH",
    "/baselines",
)
baseline_volume = (
    modal.Volume.from_name(BASELINE_VOLUME_NAME, create_if_missing=False)
    if BASELINE_VOLUME_NAME
    else None
)
function_volumes = {"/results": results_volume}
if baseline_volume is not None:
    function_volumes[BASELINE_VOLUME_MOUNT_PATH] = baseline_volume

RUNTIME_ENV = {
    "CRFB_POLICYENGINE_VERSION": os.environ.get("CRFB_POLICYENGINE_VERSION", "4.5.1"),
    "CRFB_POLICYENGINE_US_SPEC": os.environ.get(
        "CRFB_POLICYENGINE_US_SPEC",
        "policyengine-us==1.700.2",
    ),
    "CRFB_POLICYENGINE_CORE_SPEC": os.environ.get(
        "CRFB_POLICYENGINE_CORE_SPEC",
        "policyengine-core==3.26.1",
    ),
    "CRFB_PANDAS_SPEC": os.environ.get("CRFB_PANDAS_SPEC", "pandas==2.3.2"),
    "CRFB_NUMPY_SPEC": os.environ.get("CRFB_NUMPY_SPEC", "numpy==2.1.3"),
    "CRFB_H5PY_SPEC": os.environ.get("CRFB_H5PY_SPEC", "h5py==3.14.0"),
    "CRFB_TABLES_SPEC": os.environ.get("CRFB_TABLES_SPEC", "tables==3.11.1"),
    "CRFB_BOTO3_SPEC": os.environ.get("CRFB_BOTO3_SPEC", "boto3==1.35.99"),
}
for contract_env_name in (
    "CRFB_SUPPORT_GATE_START_YEAR",
    "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT",
    "CRFB_MIN_EFFECTIVE_SAMPLE_SIZE",
    "CRFB_MIN_POSITIVE_HOUSEHOLD_COUNT",
    "CRFB_MAX_TOP_10_WEIGHT_SHARE_PCT",
    "CRFB_MAX_TOP_100_WEIGHT_SHARE_PCT",
):
    if os.environ.get(contract_env_name) is not None:
        RUNTIME_ENV[contract_env_name] = os.environ[contract_env_name]
POLICYENGINE_US_PATH = resolve_local_env_path("CRFB_POLICYENGINE_US_PATH")

# Container image matching the live full-H5 CRFB reform runtime.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .env(RUNTIME_ENV)
    .pip_install(
        RUNTIME_ENV["CRFB_PANDAS_SPEC"],
        RUNTIME_ENV["CRFB_NUMPY_SPEC"],
        RUNTIME_ENV["CRFB_H5PY_SPEC"],
        RUNTIME_ENV["CRFB_TABLES_SPEC"],
        RUNTIME_ENV["CRFB_BOTO3_SPEC"],
        "huggingface_hub",
        RUNTIME_ENV["CRFB_POLICYENGINE_CORE_SPEC"],
        RUNTIME_ENV["CRFB_POLICYENGINE_US_SPEC"],
        f"policyengine=={RUNTIME_ENV['CRFB_POLICYENGINE_VERSION']}",
    )
    # Copy supporting project files into the image so later image steps remain valid.
    .add_local_dir(DATA_DIR, "/app/data", copy=True)
    .add_local_dir(SRC_DIR, "/app/src", copy=True)
)
if POLICYENGINE_US_PATH is not None:
    image = image.add_local_dir(
        POLICYENGINE_US_PATH,
        "/app/policyengine-us",
        copy=True,
    ).run_commands("pip install -e /app/policyengine-us")

DEFAULT_R2_MODAL_SECRET_NAME = "crfb-reform-full-h5-r2-axiom"


def modal_secret_names() -> list[str]:
    names = [
        os.environ.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_MODAL_SECRET"),
        os.environ.get("CRFB_R2_MODAL_SECRET_NAME"),
        DEFAULT_R2_MODAL_SECRET_NAME,
    ]
    return list(dict.fromkeys(name for name in names if name))


modal_secrets = [modal.Secret.from_name(name) for name in modal_secret_names()]

if LOCAL_PROJECTED_DATASETS_SNAPSHOT is not None:
    image = image.add_local_dir(
        LOCAL_PROJECTED_DATASETS_SNAPSHOT,
        str(CONTAINER_SNAPSHOT_DIR),
        copy=True,
    )

# Two-stage approach for "traditional fix" (no employer tax reform):
# Stage 1: Apply benefit cuts only, measure remaining gaps
# Stage 2: Close remaining gaps with payroll rate increases

# HI data from Trustees 2025 (loaded inline to avoid file dependencies)
HI_DATA = None


def get_hi_data():
    """Load HI data from CSV or use cached version."""
    global HI_DATA
    if HI_DATA is not None:
        return HI_DATA

    # In Modal container, data is at /app/data/
    paths = [
        str(DATA_DIR / "hi_expenditures_tr2025.csv"),
        "/app/data/hi_expenditures_tr2025.csv",
        "data/hi_expenditures_tr2025.csv",
    ]
    for path in paths:
        if os.path.exists(path):
            df = pd.read_csv(path)
            if 2100 not in set(df["year"].astype(int)):
                tail = df[df["year"].between(2090, 2099)].copy()
                if len(tail) != 10:
                    raise ValueError("Expected 2090-2099 HI data to extrapolate 2100.")

                extrapolated = {"year": 2100}
                years = tail["year"].to_numpy(dtype=float)
                for column in ["cost_rate", "hi_taxable_payroll", "hi_expenditures"]:
                    values = tail[column].to_numpy(dtype=float)
                    slope, intercept = np.polyfit(years, values, 1)
                    extrapolated[column] = float(slope * 2100 + intercept)

                df = pd.concat([df, pd.DataFrame([extrapolated])], ignore_index=True)

            HI_DATA = {
                int(row["year"]): {
                    "hi_taxable_payroll": row["hi_taxable_payroll"],
                    "hi_expenditures": row["hi_expenditures"],
                    "cost_rate": row["cost_rate"],
                }
                for _, row in df.iterrows()
            }
            print(f"Loaded HI data from {path}")
            return HI_DATA

    raise FileNotFoundError(f"HI expenditures CSV not found in: {paths}")


@app.function(
    image=image,
    cpu=int(os.environ.get("CRFB_OPTION13_MODAL_CPU", "4")),
    timeout=int(os.environ.get("CRFB_OPTION13_MODAL_TIMEOUT_SECONDS", "21600")),
    memory=int(os.environ.get("CRFB_OPTION13_MODAL_MEMORY_MB", "65536")),
    volumes=function_volumes,
    secrets=modal_secrets,
    nonpreemptible=env_bool("CRFB_OPTION13_MODAL_NONPREEMPTIBLE", False),
)
def compute_option13_and_14_year(
    year: int,
    skip_option13: bool = False,
    skip_option14: bool = False,
    output_prefix: str = "",
) -> dict:
    """Compute Option 13 (Balanced Fix) and/or Option 14 (Option 12 vs Balanced Fix) for a single year.

    Args:
        year: Year to compute
        skip_option13: If True, skip Option 13 save (still computes baseline for Option 14)
        skip_option14: If True, skip Option 14 computation
        output_prefix: Results subdirectory under the shared Modal volume.

    Returns:
        Dict with 'option13' and/or 'option14' results (only keys for computed options)
    """
    import sys
    import time
    import numpy as np
    from policyengine_us import Microsimulation
    from policyengine_core.reforms import Reform

    configure_runtime_snapshot_env()

    # Add src to path for imports
    sys.path.insert(0, str(SRC_DIR.parent))
    sys.path.insert(0, str(SRC_DIR))
    from reforms import get_option12_dict
    from runtime_config import dataset_path
    from src.reform_full_h5_artifacts import (
        file_sha256,
        upload_artifact_pair_to_object_store,
    )
    from src.reform_full_h5_worker import (
        _boto3_client,
        object_store_completion_key,
        object_store_config_from_env,
        object_store_keys,
        runtime_provenance_from_environment,
        save_complete_microsimulation_h5,
    )

    def json_safe(value):
        if isinstance(value, dict):
            return {str(key): json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        if isinstance(value, (np.integer, np.floating, np.bool_)):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, Path):
            return str(value)
        return value

    def write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def save_full_h5_artifacts(
        simulation,
        *,
        reform_id: str,
        result_row: dict,
        reform_description: str,
    ) -> dict:
        artifact_dir = (
            output_root
            / "reform_full_h5"
            / f"year={year}"
            / f"reform={reform_id}"
        )
        scenario_path = artifact_dir / "scenario.h5"
        metadata_path = artifact_dir / "metadata.json"
        h5_metadata = save_complete_microsimulation_h5(
            simulation,
            scenario_path,
            year=year,
        )
        object_store_config = object_store_config_from_env()
        object_store = None
        if object_store_config is not None:
            scenario_key, metadata_key = object_store_keys(
                config=object_store_config,
                run_prefix=output_prefix,
                year=year,
                reform_id=reform_id,
            )
            object_store = {
                "bucket": object_store_config.bucket,
                "scenario_key": scenario_key,
                "metadata_key": metadata_key,
                "completion_key": object_store_completion_key(
                    metadata_key=metadata_key
                ),
            }
        elif os.environ.get("CRFB_REQUIRE_R2_FULL_H5", "1").lower() not in {
            "0",
            "false",
            "no",
        }:
            raise RuntimeError("R2 object-store config is required for this rerun.")

        metadata = {
            "schema": "crfb_balanced_fix_full_reform_h5_metadata/v1",
            "created_at": datetime.now().isoformat(),
            "year": int(year),
            "reform_id": reform_id,
            "scoring_type": "static",
            "dataset_path": str(dataset),
            "dataset_h5_sha256": file_sha256(dataset),
            "dataset_h5_size_bytes": int(Path(dataset).stat().st_size),
            "run_prefix": output_prefix,
            "runtime_provenance": runtime_provenance_from_environment(
                dataset_path=dataset
            ),
            "dataset_contract_environment": {
                name: os.environ.get(name)
                for name in (
                    "CRFB_SUPPORT_GATE_START_YEAR",
                    "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT",
                    "CRFB_MIN_EFFECTIVE_SAMPLE_SIZE",
                    "CRFB_MIN_POSITIVE_HOUSEHOLD_COUNT",
                    "CRFB_MAX_TOP_10_WEIGHT_SHARE_PCT",
                    "CRFB_MAX_TOP_100_WEIGHT_SHARE_PCT",
                )
                if os.environ.get(name) is not None
            },
            "reform_description": reform_description,
            "result_row": result_row,
            "full_reform_output_h5_saved": True,
            "baseline_aggregate_metrics_computed_before_h5_save": False,
            "manual_weight_aggregation_used": False,
            "output_h5_sha256": h5_metadata["sha256"],
            "output_h5_size_bytes": h5_metadata["size_bytes"],
            "modal_volume_path": str(scenario_path),
            "scenario_h5": h5_metadata,
            "object_store": object_store,
        }
        write_json(metadata_path, metadata)

        object_store_validation = None
        if object_store_config is not None and object_store is not None:
            object_store_validation = upload_artifact_pair_to_object_store(
                client=_boto3_client(object_store_config),
                bucket=object_store_config.bucket,
                scenario_path=scenario_path,
                metadata_path=metadata_path,
                scenario_key=object_store["scenario_key"],
                metadata_key=object_store["metadata_key"],
                completion_key=object_store["completion_key"],
            )

        artifact_record = {
            "full_reform_output_h5_saved": True,
            "scenario_h5_path": str(scenario_path),
            "metadata_path": str(metadata_path),
            "output_h5_sha256": h5_metadata["sha256"],
            "output_h5_size_bytes": h5_metadata["size_bytes"],
        }
        if object_store is not None:
            artifact_record.update(
                {
                    "scenario_h5_uri": (
                        f"r2://{object_store_config.bucket}/"
                        f"{object_store['scenario_key']}"
                    ),
                    "metadata_uri": (
                        f"r2://{object_store_config.bucket}/"
                        f"{object_store['metadata_key']}"
                    ),
                    "completion_uri": (
                        f"r2://{object_store_config.bucket}/"
                        f"{object_store['completion_key']}"
                    ),
                    "object_store_upload_validated": bool(
                        object_store_validation
                        and object_store_validation.get("validated")
                    ),
                }
            )
        return artifact_record

    print(f"\n{'=' * 60}")
    print(f"OPTION 13 (BALANCED FIX): {year}")
    print(f"{'=' * 60}")

    hi_data = get_hi_data()
    if year not in hi_data:
        return {"year": year, "error": f"No HI data for year {year}"}

    hi_info = hi_data[year]
    medicare_expenditures = hi_info["hi_expenditures"]

    dataset = dataset_path(year)

    def calculate_sum(
        simulation,
        variable_name: str,
        *,
        label: str | None = None,
        map_to: str | None = None,
    ):
        display_name = label or variable_name
        start = time.time()
        print(f"Calculating {display_name}...", flush=True)
        if map_to is None:
            result = simulation.calculate(variable_name, period=year).sum()
        else:
            result = simulation.calculate(
                variable_name, map_to=map_to, period=year
            ).sum()
        print(
            f"  {display_name}: ${result / 1e9:.3f}B ({time.time() - start:.1f}s)",
            flush=True,
        )
        return result

    # Run baseline
    print("Running baseline simulation...")
    baseline = Microsimulation(dataset=dataset)

    # SS components
    employee_ss_tax = calculate_sum(baseline, "employee_social_security_tax")
    employer_ss_tax = calculate_sum(baseline, "employer_social_security_tax")
    se_ss_tax = calculate_sum(baseline, "self_employment_social_security_tax")
    tob_oasdi = calculate_sum(baseline, "tob_revenue_oasdi")

    ss_benefits_series = baseline.calculate("social_security", period=year)
    ss_benefits = ss_benefits_series.sum()
    ss_benefits_values = np.array(ss_benefits_series.values)

    # HI components
    employee_hi_tax = calculate_sum(baseline, "employee_medicare_tax")
    employer_hi_tax = calculate_sum(baseline, "employer_medicare_tax")
    se_medicare_tax = calculate_sum(baseline, "self_employment_medicare_tax")
    additional_medicare_tax = calculate_sum(baseline, "additional_medicare_tax")
    tob_hi = calculate_sum(baseline, "tob_revenue_medicare_hi")

    # Get current rates
    params = baseline.tax_benefit_system.parameters
    current_employee_ss_rate = float(
        params.gov.irs.payroll.social_security.rate.employee(f"{year}-01-01")
    )
    current_employer_ss_rate = float(
        params.gov.irs.payroll.social_security.rate.employer(f"{year}-01-01")
    )
    current_employee_hi_rate = float(
        params.gov.irs.payroll.medicare.rate.employee(f"{year}-01-01")
    )
    current_employer_hi_rate = float(
        params.gov.irs.payroll.medicare.rate.employer(f"{year}-01-01")
    )

    print(f"Baseline SS Benefits: ${ss_benefits / 1e9:.1f}B")

    # Calculate gaps (including SECA self-employment taxes)
    ss_income = employee_ss_tax + employer_ss_tax + se_ss_tax + tob_oasdi
    ss_gap = ss_income - ss_benefits

    hi_income = (
        employee_hi_tax
        + employer_hi_tax
        + se_medicare_tax
        + additional_medicare_tax
        + tob_hi
    )
    hi_gap = hi_income - medicare_expenditures

    print(
        f"SE taxes: SS ${se_ss_tax / 1e9:.1f}B, Medicare ${se_medicare_tax / 1e9:.1f}B"
    )

    ss_shortfall = abs(min(ss_gap, 0))
    hi_shortfall = abs(min(hi_gap, 0))

    print(f"SS Gap: ${ss_gap / 1e9:.1f}B, HI Gap: ${hi_gap / 1e9:.1f}B")

    # ==========================================================================
    # TWO-STAGE APPROACH: Simpler gap closing without TOB estimation
    # ==========================================================================
    # Stage 1: Apply 50% benefit cut, measure actual remaining gaps
    # Stage 2: Close remaining gaps with rate increases
    # ==========================================================================

    # Get taxable payroll directly from PolicyEngine variables
    # SS: capped at wage base, Medicare: no cap (all wages)
    oasdi_taxable_payroll = calculate_sum(
        baseline, "taxable_earnings_for_social_security"
    )
    hi_taxable_payroll = calculate_sum(baseline, "payroll_tax_gross_wages")

    print(
        f"Taxable payroll: SS ${oasdi_taxable_payroll / 1e12:.2f}T, HI ${hi_taxable_payroll / 1e12:.2f}T"
    )

    # ==========================================================================
    # STAGE 1: Apply benefit cuts only (no employer tax reform), measure remaining gaps
    # ==========================================================================
    print("\n=== STAGE 1: Measure gaps after benefit cuts ===")

    # Straight 50% benefit cut (no TOB inflation needed)
    benefit_cut = ss_shortfall * 0.5
    benefit_multiplier = 1 - (benefit_cut / ss_benefits)
    print(
        f"Benefit cut: ${benefit_cut / 1e9:.1f}B ({(1 - benefit_multiplier) * 100:.1f}% cut)"
    )

    # Stage 1: Just benefit cuts, no other reforms
    # Use baseline simulation with modified SS benefits
    stage1_sim = Microsimulation(dataset=dataset, start_instant=f"{year}-01-01")

    # Apply benefit cut
    reduced_ss_values = ss_benefits_values * benefit_multiplier
    stage1_sim.set_input("social_security", year, reduced_ss_values)

    # Calculate Stage 1 results
    stage1_ss_benefits = calculate_sum(
        stage1_sim, "social_security", label="stage1 social_security"
    )
    stage1_employee_ss = calculate_sum(
        stage1_sim,
        "employee_social_security_tax",
        label="stage1 employee_social_security_tax",
    )
    stage1_employer_ss = calculate_sum(
        stage1_sim,
        "employer_social_security_tax",
        label="stage1 employer_social_security_tax",
    )
    stage1_se_ss = calculate_sum(
        stage1_sim,
        "self_employment_social_security_tax",
        label="stage1 self_employment_social_security_tax",
    )
    stage1_tob_oasdi = calculate_sum(
        stage1_sim, "tob_revenue_oasdi", label="stage1 tob_revenue_oasdi"
    )
    stage1_employee_hi = calculate_sum(
        stage1_sim, "employee_medicare_tax", label="stage1 employee_medicare_tax"
    )
    stage1_employer_hi = calculate_sum(
        stage1_sim, "employer_medicare_tax", label="stage1 employer_medicare_tax"
    )
    stage1_se_medicare = calculate_sum(
        stage1_sim,
        "self_employment_medicare_tax",
        label="stage1 self_employment_medicare_tax",
    )
    stage1_additional_medicare = calculate_sum(
        stage1_sim, "additional_medicare_tax", label="stage1 additional_medicare_tax"
    )
    stage1_tob_hi = calculate_sum(
        stage1_sim, "tob_revenue_medicare_hi", label="stage1 tob_revenue_medicare_hi"
    )

    # Calculate remaining gaps AFTER benefit cuts (no employer tax revenue)
    stage1_ss_income = (
        stage1_employee_ss + stage1_employer_ss + stage1_se_ss + stage1_tob_oasdi
    )
    stage1_hi_income = (
        stage1_employee_hi
        + stage1_employer_hi
        + stage1_se_medicare
        + stage1_additional_medicare
        + stage1_tob_hi
    )

    stage1_ss_gap = (
        stage1_ss_income - stage1_ss_benefits
    )  # Trust fund gap (payroll taxes only)
    stage1_hi_gap = stage1_hi_income - medicare_expenditures

    # Remaining gaps = stage 1 gaps (no employer tax revenue to add)
    remaining_ss_gap = stage1_ss_gap
    remaining_hi_gap = stage1_hi_gap

    print(f"After benefit cuts:")
    print(f"  SS: remaining gap ${remaining_ss_gap / 1e9:.1f}B")
    print(f"  HI: remaining gap ${remaining_hi_gap / 1e9:.1f}B")

    del stage1_sim  # Clean up

    # ==========================================================================
    # STAGE 2: Calculate rate increases to close remaining gaps
    # ==========================================================================
    print("\n=== STAGE 2: Calculate rate increases ===")

    # SS: Close remaining gap (negative = deficit needs rate increase)
    if remaining_ss_gap < 0:
        ss_rate_increase = abs(remaining_ss_gap) / oasdi_taxable_payroll
        print(
            f"  SS: deficit ${remaining_ss_gap / 1e9:.1f}B -> rate increase {ss_rate_increase * 100:.3f}pp"
        )
    else:
        ss_rate_increase = 0  # Surplus, no increase needed
        print(f"  SS: surplus ${remaining_ss_gap / 1e9:.1f}B -> no rate increase")

    # HI: Close remaining gap (can be increase or decrease)
    if remaining_hi_gap < 0:
        hi_rate_increase = abs(remaining_hi_gap) / hi_taxable_payroll
        print(
            f"  HI: deficit ${remaining_hi_gap / 1e9:.1f}B -> rate increase {hi_rate_increase * 100:.3f}pp"
        )
    else:
        hi_rate_increase = -remaining_hi_gap / hi_taxable_payroll  # Negative = cut
        print(
            f"  HI: surplus ${remaining_hi_gap / 1e9:.1f}B -> rate cut {abs(hi_rate_increase) * 100:.3f}pp"
        )

    new_employee_ss_rate = current_employee_ss_rate + ss_rate_increase / 2
    new_employer_ss_rate = current_employer_ss_rate + ss_rate_increase / 2
    new_employee_hi_rate = current_employee_hi_rate + hi_rate_increase / 2
    new_employer_hi_rate = current_employer_hi_rate + hi_rate_increase / 2

    print(
        f"New rates: SS {new_employee_ss_rate * 2 * 100:.2f}%, HI {new_employee_hi_rate * 2 * 100:.2f}%"
    )
    print(f"Benefit multiplier: {benefit_multiplier:.4f}")

    results = {}
    output_root = results_root(output_prefix)

    # Build reform: rate increases only (no employer tax reform)
    # Option 13 is the "traditional fix" - benefit cuts + rate increases under current law
    reform_dict = {
        # Payroll rate increases to close remaining gaps
        "gov.irs.payroll.social_security.rate.employee": {
            f"{year}-01-01.{year}-12-31": float(new_employee_ss_rate)
        },
        "gov.irs.payroll.social_security.rate.employer": {
            f"{year}-01-01.{year}-12-31": float(new_employer_ss_rate)
        },
        "gov.irs.payroll.medicare.rate.employee": {
            f"{year}-01-01.{year}-12-31": float(new_employee_hi_rate)
        },
        "gov.irs.payroll.medicare.rate.employer": {
            f"{year}-01-01.{year}-12-31": float(new_employer_hi_rate)
        },
    }

    reform = Reform.from_dict(reform_dict, country_id="us")

    # Create simulation and apply benefit cut BEFORE any calculate()
    # CRITICAL: Must pass start_instant for the year we're reforming
    print("Running final reform simulation...")
    reform_sim = Microsimulation(
        reform=reform, dataset=dataset, start_instant=f"{year}-01-01"
    )

    reduced_ss_values = ss_benefits_values * benefit_multiplier
    reform_sim.set_input("social_security", year, reduced_ss_values)

    option13_artifact_record = {}
    if not skip_option13:
        option13_artifact_record = save_full_h5_artifacts(
            reform_sim,
            reform_id="balanced_fix",
            result_row={
                "year": year,
                "baseline_ss_gap": float(ss_gap),
                "baseline_hi_gap": float(hi_gap),
                "benefit_multiplier": float(benefit_multiplier),
                "new_employee_ss_rate": float(new_employee_ss_rate),
                "new_employer_ss_rate": float(new_employer_ss_rate),
                "new_employee_hi_rate": float(new_employee_hi_rate),
                "new_employer_hi_rate": float(new_employer_hi_rate),
                "post_h5_aggregation_deferred": True,
            },
            reform_description=(
                "Balanced fix baseline: 50 percent Social Security benefit "
                "gap closure through benefit reductions and remaining "
                "OASDI/HI gaps through payroll rate changes."
            ),
        )

    baseline_income_tax = calculate_sum(
        baseline, "income_tax", label="baseline income_tax"
    )
    print(f"Baseline Income Tax: ${baseline_income_tax / 1e9:.1f}B")

    # Calculate
    reform_income_tax = calculate_sum(
        reform_sim, "income_tax", label="reform income_tax"
    )
    reform_tob_oasdi = calculate_sum(
        reform_sim, "tob_revenue_oasdi", label="reform tob_revenue_oasdi"
    )
    reform_tob_hi = calculate_sum(
        reform_sim, "tob_revenue_medicare_hi", label="reform tob_revenue_medicare_hi"
    )
    reform_ss_benefits = calculate_sum(
        reform_sim, "social_security", label="reform social_security"
    )
    reform_employee_ss = calculate_sum(
        reform_sim,
        "employee_social_security_tax",
        label="reform employee_social_security_tax",
    )
    reform_employer_ss = calculate_sum(
        reform_sim,
        "employer_social_security_tax",
        label="reform employer_social_security_tax",
    )
    reform_se_ss = calculate_sum(
        reform_sim,
        "self_employment_social_security_tax",
        label="reform self_employment_social_security_tax",
    )
    reform_employee_hi = calculate_sum(
        reform_sim, "employee_medicare_tax", label="reform employee_medicare_tax"
    )
    reform_employer_hi = calculate_sum(
        reform_sim, "employer_medicare_tax", label="reform employer_medicare_tax"
    )
    reform_se_medicare = calculate_sum(
        reform_sim,
        "self_employment_medicare_tax",
        label="reform self_employment_medicare_tax",
    )
    reform_additional_medicare = calculate_sum(
        reform_sim, "additional_medicare_tax", label="reform additional_medicare_tax"
    )

    # Calculate rate increase revenue (manual calculation)
    rate_increase_ss_revenue = ss_rate_increase * oasdi_taxable_payroll
    rate_increase_hi_revenue = hi_rate_increase * hi_taxable_payroll
    total_rate_increase_revenue = rate_increase_ss_revenue + rate_increase_hi_revenue

    # New gaps (including SECA)
    reform_ss_income = (
        reform_employee_ss + reform_employer_ss + reform_se_ss + reform_tob_oasdi
    )
    reform_hi_income = (
        reform_employee_hi
        + reform_employer_hi
        + reform_se_medicare
        + reform_additional_medicare
        + reform_tob_hi
    )
    new_ss_gap = reform_ss_income - reform_ss_benefits
    new_hi_gap = reform_hi_income - medicare_expenditures

    actual_benefit_cut = ss_benefits - reform_ss_benefits

    print(f"\nResults:")
    print(f"  SS Gap: ${ss_gap / 1e9:.1f}B -> ${new_ss_gap / 1e9:.1f}B")
    print(f"  HI Gap: ${hi_gap / 1e9:.1f}B -> ${new_hi_gap / 1e9:.1f}B")
    print(
        f"  Benefit cut: ${actual_benefit_cut / 1e9:.1f}B ({actual_benefit_cut / ss_benefits * 100:.1f}%)"
    )
    print(
        f"  Income tax impact: ${(reform_income_tax - baseline_income_tax) / 1e9:+.1f}B"
    )
    print(f"  Rate increase revenue: ${total_rate_increase_revenue / 1e9:.1f}B")

    # Option 13 result
    if not skip_option13:
        option13_result = {
            "year": year,
            "baseline_ss_benefits": float(ss_benefits),
            "baseline_income_tax": float(baseline_income_tax),
            "baseline_ss_gap": float(ss_gap),
            "baseline_hi_gap": float(hi_gap),
            "benefit_multiplier": float(benefit_multiplier),
            "new_employee_ss_rate": float(new_employee_ss_rate),
            "new_employer_ss_rate": float(new_employer_ss_rate),
            "new_employee_hi_rate": float(new_employee_hi_rate),
            "new_employer_hi_rate": float(new_employer_hi_rate),
            "reform_ss_benefits": float(reform_ss_benefits),
            "reform_income_tax": float(reform_income_tax),
            "reform_ss_gap": float(new_ss_gap),
            "reform_hi_gap": float(new_hi_gap),
            "benefit_cut": float(actual_benefit_cut),
            "income_tax_impact": float(reform_income_tax - baseline_income_tax),
            "tob_oasdi_impact": float(reform_tob_oasdi - tob_oasdi),
            "tob_hi_impact": float(reform_tob_hi - tob_hi),
            # Rate increase revenue (manual calculation)
            "rate_increase_ss_revenue": float(rate_increase_ss_revenue),
            "rate_increase_hi_revenue": float(rate_increase_hi_revenue),
            "total_rate_increase_revenue": float(total_rate_increase_revenue),
            # Rate changes in percentage points
            "ss_rate_increase_pp": float(ss_rate_increase * 100),
            "hi_rate_increase_pp": float(hi_rate_increase * 100),
            # TOB losses for tracking
            "tob_oasdi_loss": float(tob_oasdi - reform_tob_oasdi),
            "tob_hi_loss": float(tob_hi - reform_tob_hi),
            # Final gaps (reform gaps = payroll income - outgo, should be ~$0)
            "ss_gap_after": float(new_ss_gap),
            "hi_gap_after": float(new_hi_gap),
            "total_gap_after": float(new_ss_gap + new_hi_gap),
        }
        option13_result.update(option13_artifact_record)

        # Save Option 13 result
        option13_dir = output_root / "option13"
        option13_dir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame([option13_result])
        df.to_csv(option13_dir / f"{year}_static_results.csv", index=False)
        results_volume.commit()
        results["option13"] = option13_result

    # =========================================================================
    # OPTION 14: Option 12 (Extended Roth) vs Balanced Fix Baseline
    # Shows what happens if we do Extended Roth INSTEAD OF balanced fix
    # =========================================================================
    if not skip_option14:
        print(f"\n{'=' * 60}")
        print(f"OPTION 14 (OPTION 12 vs BALANCED FIX): {year}")
        print(f"{'=' * 60}")

        option12_dict = get_option12_dict()

        # Option 12 only - no balanced fix rate increases, no benefit cuts
        option12_reform = Reform.from_dict(option12_dict, country_id="us")

        print("Running Option 12 standalone simulation...")
        option12_sim = Microsimulation(
            reform=option12_reform, dataset=dataset, start_instant=f"{year}-01-01"
        )

        # NO benefit cuts - use original baseline SS values
        # (don't call set_input for social_security)

        option14_artifact_record = save_full_h5_artifacts(
            option12_sim,
            reform_id="option12_balanced_fix",
            result_row={
                "year": year,
                "comparison_baseline": "balanced_fix",
                "post_h5_aggregation_deferred": True,
            },
            reform_description=(
                "Option 12 extended Roth-style swap measured against the "
                "balanced-fix baseline for the same year."
            ),
        )

        # Calculate Option 12 standalone results
        option12_income_tax = calculate_sum(
            option12_sim, "income_tax", label="option12 income_tax"
        )
        option12_tob_oasdi = calculate_sum(
            option12_sim, "tob_revenue_oasdi", label="option12 tob_revenue_oasdi"
        )
        option12_tob_hi = calculate_sum(
            option12_sim,
            "tob_revenue_medicare_hi",
            label="option12 tob_revenue_medicare_hi",
        )
        option12_ss_benefits = calculate_sum(
            option12_sim, "social_security", label="option12 social_security"
        )

        # Option 12 specific: employer payroll tax revenue
        option12_employer_ss_revenue = calculate_sum(
            option12_sim,
            "employer_ss_tax_income_tax_revenue",
            label="option12 employer_ss_tax_income_tax_revenue",
            map_to="household",
        )
        option12_employer_hi_revenue = calculate_sum(
            option12_sim,
            "employer_medicare_tax_income_tax_revenue",
            label="option12 employer_medicare_tax_income_tax_revenue",
            map_to="household",
        )

        # Compare to Option 13 baseline (balanced fix)
        option12_income_tax_impact = option12_income_tax - reform_income_tax
        option12_tob_oasdi_impact = option12_tob_oasdi - reform_tob_oasdi
        option12_tob_hi_impact = option12_tob_hi - reform_tob_hi

        # Trust fund impacts
        option12_oasdi_gain = float(option12_employer_ss_revenue)
        option12_hi_gain = float(option12_employer_hi_revenue)
        option12_oasdi_loss = float(reform_tob_oasdi - option12_tob_oasdi)
        option12_hi_loss = float(reform_tob_hi - option12_tob_hi)
        option12_oasdi_net = option12_oasdi_gain - option12_oasdi_loss
        option12_hi_net = option12_hi_gain - option12_hi_loss

        print(f"\nOption 14 Results (vs Balanced Fix):")
        print(f"  Income tax impact: ${option12_income_tax_impact / 1e9:+.1f}B")
        print(
            f"  OASDI net impact: ${option12_oasdi_net / 1e9:+.1f}B (gain: ${option12_oasdi_gain / 1e9:.1f}B, loss: ${option12_oasdi_loss / 1e9:.1f}B)"
        )
        print(
            f"  HI net impact: ${option12_hi_net / 1e9:+.1f}B (gain: ${option12_hi_gain / 1e9:.1f}B, loss: ${option12_hi_loss / 1e9:.1f}B)"
        )

        option14_result = {
            "year": year,
            # Baseline is the balanced fix (Option 13)
            "baseline_income_tax": float(reform_income_tax),
            "baseline_tob_oasdi": float(reform_tob_oasdi),
            "baseline_tob_hi": float(reform_tob_hi),
            "baseline_ss_benefits": float(reform_ss_benefits),
            # Reform is Option 12 only (no balanced fix)
            "reform_income_tax": float(option12_income_tax),
            "reform_tob_oasdi": float(option12_tob_oasdi),
            "reform_tob_hi": float(option12_tob_hi),
            "reform_ss_benefits": float(option12_ss_benefits),
            # Impacts
            "income_tax_impact": float(option12_income_tax_impact),
            "tob_oasdi_impact": float(option12_tob_oasdi_impact),
            "tob_hi_impact": float(option12_tob_hi_impact),
            # Trust fund breakdown
            "employer_ss_tax_revenue": float(option12_employer_ss_revenue),
            "employer_hi_tax_revenue": float(option12_employer_hi_revenue),
            "oasdi_gain": option12_oasdi_gain,
            "hi_gain": option12_hi_gain,
            "oasdi_loss": option12_oasdi_loss,
            "hi_loss": option12_hi_loss,
            "oasdi_net_impact": option12_oasdi_net,
            "hi_net_impact": option12_hi_net,
        }
        option14_result.update(option14_artifact_record)

        # Save Option 14 result
        option14_dir = output_root / "option14"
        option14_dir.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame([option14_result])
        df.to_csv(option14_dir / f"{year}_static_results.csv", index=False)
        results_volume.commit()
        results["option14"] = option14_result

    return results


# Backwards compatibility alias for running jobs
compute_option13_year = compute_option13_and_14_year


@app.local_entrypoint()
def main(
    years: str = "2035,2036,2037",
    option13_only: bool = False,
    option14_only: bool = False,
    output_prefix: str = "",
    submit_only: bool = False,
    submission_manifest: str = "",
):
    """Run Option 13 and/or Option 14 for specified years.

    Args:
        years: Comma-separated years to compute
        option13_only: Only compute Option 13 (balanced fix baseline)
        option14_only: Only compute Option 14 (requires Option 13 already computed)
        output_prefix: Optional results subdirectory within the Modal volume.
        submit_only: Submit remote year jobs and exit without waiting for completion.
        submission_manifest: Local JSON file to store submitted call metadata.
    """
    year_list = [int(y.strip()) for y in years.split(",")]

    # Determine what to run
    run_option13 = not option14_only
    run_option14 = not option13_only

    if option13_only and option14_only:
        print("Error: Cannot specify both --option13-only and --option14-only")
        return

    options_str = []
    if run_option13:
        options_str.append("Option 13")
    if run_option14:
        options_str.append("Option 14")
    print(f"Running {' & '.join(options_str)} for years: {year_list}")

    option13_results = []
    option14_results = []

    # Pass flags to the compute function
    if not output_prefix:
        output_prefix = os.environ.get("CRFB_SPECIAL_CASE_OUTPUT_PREFIX", "")
    if not output_prefix:
        output_prefix = default_output_prefix()

    args = [
        (year, not run_option13, not run_option14, output_prefix) for year in year_list
    ]

    if submit_only:
        print(
            "Submit-only mode records spawned year jobs and exits without waiting. "
            "Use the recovered volume outputs, not just call-id state, as the publication artifact."
        )
        manifest_path = (
            Path(submission_manifest)
            if submission_manifest
            else default_submission_manifest_path(output_prefix)
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)

        submitted_calls = []
        for year, skip_option13, skip_option14, prefix in args:
            call = compute_option13_and_14_year.spawn(
                year, skip_option13, skip_option14, prefix
            )
            submitted_calls.append(
                {
                    "year": year,
                    "skip_option13": skip_option13,
                    "skip_option14": skip_option14,
                    "output_prefix": prefix,
                    "call_id": call.object_id,
                    "dashboard_url": call.get_dashboard_url(),
                }
            )
            print(
                f"Submitted year {year}: {call.object_id} -> {call.get_dashboard_url()}"
            )

        payload = {
            "submitted_at": datetime.now().isoformat(),
            "years": year_list,
            "run_option13": run_option13,
            "run_option14": run_option14,
            "output_prefix": output_prefix,
            "calls": submitted_calls,
        }
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"\nSubmitted {len(submitted_calls)} year jobs.")
        print(f"Volume output root: /results/{output_prefix}/")
        print(f"Submission manifest: {manifest_path}")
        return

    for result in compute_option13_and_14_year.starmap(args):
        if result.get("option13"):
            opt13 = result["option13"]
            option13_results.append(opt13)
            print(f"\n=== Year {opt13['year']} - Option 13 ===")
            print(
                f"  SS Gap: ${opt13['baseline_ss_gap'] / 1e9:.1f}B -> ${opt13['reform_ss_gap'] / 1e9:.1f}B"
            )
            print(
                f"  HI Gap: ${opt13['baseline_hi_gap'] / 1e9:.1f}B -> ${opt13['reform_hi_gap'] / 1e9:.1f}B"
            )
            print(f"  Benefit cut: {(1 - opt13['benefit_multiplier']) * 100:.1f}%")

        if result.get("option14"):
            opt14 = result["option14"]
            option14_results.append(opt14)
            print(f"\n=== Year {opt14['year']} - Option 14 ===")
            print(f"  Income tax impact: ${opt14['income_tax_impact'] / 1e9:+.1f}B")
            print(f"  OASDI net: ${opt14['oasdi_net_impact'] / 1e9:+.1f}B")
            print(f"  HI net: ${opt14['hi_net_impact'] / 1e9:+.1f}B")

    # Save combined results
    if option13_results:
        df13 = pd.DataFrame(option13_results)
        df13.to_csv("results/option13_results.csv", index=False)
        print(f"\nOption 13 results saved to results/option13_results.csv")

    if option14_results:
        df14 = pd.DataFrame(option14_results)
        df14.to_csv("results/option14_results.csv", index=False)
        print(f"Option 14 results saved to results/option14_results.csv")
