from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_LAW_PATH = REPO_ROOT / "data" / "tob_current_law_tr2025.csv"
OACT_OASDI_DELTA_PATH = REPO_ROOT / "data" / "oasdi_oact_20250805_nominal_delta.csv"
SSA_ECONOMIC_PROJECTIONS_PATH = REPO_ROOT / "data" / "ssa_economic_projections.csv"
GENERATED_BASELINE_PATH = REPO_ROOT / "data" / "ssa_tob_baseline_75year.csv"
GENERATED_BASELINE_MANIFEST_PATH = GENERATED_BASELINE_PATH.with_suffix(".manifest.json")

TR2026_AUX_PATH = REPO_ROOT / "data" / "social_security_aux_tr2026.csv"
TR2026_SOURCES_MANIFEST_PATH = REPO_ROOT / "data" / "tr2026_sources.manifest.json"

TOB_BASELINE_SCENARIO_ID = "crfb_tr2026_current_law_tob_75y"
TOB_BASELINE_TARGET_ID = "tr2026_current_law_tob_75y"
TOB_BASELINE_LAW_MODE = "trustees-2026-intermediate-v1"

# Backwards-compatible aliases: the bridge-era names now point at the
# TR2026 identifiers (TR2026 carries OBBBA natively, so the post-OBBBA
# bridge no longer exists).
POST_OBBBA_SCENARIO_ID = TOB_BASELINE_SCENARIO_ID
POST_OBBBA_TARGET_ID = TOB_BASELINE_TARGET_ID
TRUSTEES_CORE_THRESHOLD_LAW_MODE = TOB_BASELINE_LAW_MODE

REQUIRED_CURRENT_LAW_COLUMNS = {
    "year",
    "tob_oasdi_billions",
    "tob_hi_billions",
    "tob_total_billions",
}

HI_METHOD_CURRENT_LAW = "current_law"
HI_METHOD_MATCH_OASDI_PCT_CHANGE = "match_oasdi_pct_change"
HI_METHODS = {
    HI_METHOD_CURRENT_LAW,
    HI_METHOD_MATCH_OASDI_PCT_CHANGE,
}

SOURCE_OASDI = (
    "2026 Trustees Report intermediate assumptions: income-rate share of "
    "taxable payroll attributable to taxation of benefits"
)
SOURCE_CURRENT_LAW = "2026 Trustees current-law TOB baseline (OBBBA native)"
SOURCE_HI_CMS_DIRECTION = (
    "CMS 2026 Medicare Trustees expanded tables, annual through 2100"
)
DELTA_METHOD_TR2026 = "tr2026_native_current_law"


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _unique_values(df: pd.DataFrame, column: str) -> list[str]:
    return sorted(str(value) for value in df[column].dropna().unique().tolist())


def load_current_law_series() -> pd.DataFrame:
    current_law = pd.read_csv(CURRENT_LAW_PATH)
    missing_columns = REQUIRED_CURRENT_LAW_COLUMNS - set(current_law.columns)
    if missing_columns:
        raise ValueError(
            f"Missing current-law TOB columns in {CURRENT_LAW_PATH.name}: {sorted(missing_columns)}"
        )

    payroll = pd.read_csv(SSA_ECONOMIC_PROJECTIONS_PATH, usecols=["year", "taxable_payroll"])
    payroll_2025 = pd.DataFrame([{"year": 2025, "taxable_payroll": 10621.0}])
    payroll = pd.concat([payroll_2025, payroll], ignore_index=True)

    merged = current_law.merge(payroll, on="year", how="left", validate="one_to_one")
    missing_payroll_years = merged.loc[merged["taxable_payroll"].isna(), "year"].tolist()
    if missing_payroll_years:
        raise ValueError(f"Missing taxable payroll values for years: {missing_payroll_years}")

    merged = merged.rename(
        columns={
            "tob_oasdi_billions": "current_law_oasdi_billions",
            "tob_hi_billions": "current_law_hi_billions",
            "tob_total_billions": "current_law_total_billions",
        }
    )
    return merged.sort_values("year").reset_index(drop=True)


def load_oact_oasdi_deltas() -> pd.DataFrame:
    deltas = pd.read_csv(OACT_OASDI_DELTA_PATH)
    required_columns = {"year", "oasdi_nominal_delta_billions"}
    missing_columns = required_columns - set(deltas.columns)
    if missing_columns:
        raise ValueError(
            f"Missing OACT delta columns in {OACT_OASDI_DELTA_PATH.name}: {sorted(missing_columns)}"
        )

    deltas = deltas.sort_values("year").reset_index(drop=True)
    last_delta = float(deltas.iloc[-1]["oasdi_nominal_delta_billions"])
    deltas = pd.concat(
        [
            deltas,
            pd.DataFrame(
                [
                    {
                        "year": 2100,
                        "oasdi_nominal_delta_billions": last_delta,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    deltas["oasdi_delta_method"] = "oact_table_1b_nominal"
    deltas.loc[
        deltas["year"] == 2100,
        "oasdi_delta_method",
    ] = "carry_forward_2099_nominal_delta"
    return deltas


def _apply_hi_method(df: pd.DataFrame, hi_method: str) -> tuple[pd.Series, str]:
    if hi_method == HI_METHOD_CURRENT_LAW:
        return (
            df["current_law_hi_billions"],
            "Use the 2025 Trustees/CMS HI current-law series unchanged.",
        )

    if hi_method == HI_METHOD_MATCH_OASDI_PCT_CHANGE:
        oasdi_factor = df["tob_oasdi_billions"] / df["current_law_oasdi_billions"]
        return (
            df["current_law_hi_billions"] * oasdi_factor,
            "Scale HI by the same percentage change as OASDI until a public CMS annual HI post-OBBBA series is identified.",
        )

    raise ValueError(f"Unsupported HI method: {hi_method}")


def build_tob_baseline_tr2026() -> pd.DataFrame:
    """Current-law TOB baseline read directly from the 2026 Trustees targets.

    TR2026 incorporates OBBBA in current law, so the published baseline IS
    the raw Trustees series — no OACT delta bridge, no HI scaling method.
    """
    aux = pd.read_csv(TR2026_AUX_PATH)
    df = pd.DataFrame(
        {
            "year": aux["year"].astype(int),
            "tob_oasdi_billions": aux["oasdi_tob_billions_nominal_usd"],
            "tob_hi_billions": aux["hi_tob_billions_nominal_usd"],
            "taxable_payroll": aux["taxable_payroll_in_billion_nominal_usd"],
        }
    ).dropna(subset=["tob_oasdi_billions", "tob_hi_billions"])
    df["tob_total_billions"] = df["tob_oasdi_billions"] + df["tob_hi_billions"]
    df["oasdi_share"] = df["tob_oasdi_billions"] / df["tob_total_billions"]
    df["hi_share"] = df["tob_hi_billions"] / df["tob_total_billions"]
    df["current_law_oasdi_billions"] = df["tob_oasdi_billions"]
    df["current_law_hi_billions"] = df["tob_hi_billions"]
    df["current_law_total_billions"] = df["tob_total_billions"]
    df["oasdi_nominal_delta_billions"] = 0.0
    df["oasdi_delta_method"] = DELTA_METHOD_TR2026
    df["hi_method"] = HI_METHOD_CURRENT_LAW
    df["oasdi_source"] = SOURCE_OASDI
    df["hi_source"] = SOURCE_HI_CMS_DIRECTION
    df["current_law_source"] = SOURCE_CURRENT_LAW
    df["notes"] = (
        "TR2026 intermediate assumptions carry OBBBA in current law; "
        "values are the raw Trustees/CMS series with no bridge."
    )
    return df[
        [
            "year",
            "tob_oasdi_billions",
            "tob_hi_billions",
            "tob_total_billions",
            "oasdi_share",
            "hi_share",
            "current_law_oasdi_billions",
            "current_law_hi_billions",
            "current_law_total_billions",
            "taxable_payroll",
            "oasdi_nominal_delta_billions",
            "oasdi_delta_method",
            "hi_method",
            "oasdi_source",
            "hi_source",
            "current_law_source",
            "notes",
        ]
    ].sort_values("year").reset_index(drop=True)


def build_tob_baseline(hi_method: str) -> pd.DataFrame:
    if hi_method not in HI_METHODS:
        raise ValueError(f"HI method must be one of {sorted(HI_METHODS)}")

    current_law = load_current_law_series()
    oact_deltas = load_oact_oasdi_deltas()

    df = current_law.merge(oact_deltas, on="year", how="left", validate="one_to_one")
    missing_delta_years = df.loc[df["oasdi_nominal_delta_billions"].isna(), "year"].tolist()
    if missing_delta_years:
        raise ValueError(f"Missing OACT OASDI deltas for years: {missing_delta_years}")

    df["tob_oasdi_billions"] = (
        df["current_law_oasdi_billions"] + df["oasdi_nominal_delta_billions"]
    )
    df["tob_hi_billions"], hi_method_note = _apply_hi_method(df, hi_method)
    df["tob_total_billions"] = df["tob_oasdi_billions"] + df["tob_hi_billions"]
    df["oasdi_share"] = df["tob_oasdi_billions"] / df["tob_total_billions"]
    df["hi_share"] = df["tob_hi_billions"] / df["tob_total_billions"]
    df["hi_method"] = hi_method
    df["oasdi_source"] = SOURCE_OASDI
    df["hi_source"] = SOURCE_HI_CMS_DIRECTION
    df["current_law_source"] = SOURCE_CURRENT_LAW
    df["notes"] = hi_method_note

    return df[
        [
            "year",
            "tob_oasdi_billions",
            "tob_hi_billions",
            "tob_total_billions",
            "oasdi_share",
            "hi_share",
            "current_law_oasdi_billions",
            "current_law_hi_billions",
            "current_law_total_billions",
            "taxable_payroll",
            "oasdi_nominal_delta_billions",
            "oasdi_delta_method",
            "hi_method",
            "oasdi_source",
            "hi_source",
            "current_law_source",
            "notes",
        ]
    ].sort_values("year").reset_index(drop=True)


def validate_generated_baseline(df: pd.DataFrame) -> None:
    expected_years = list(range(2025, 2101))
    years = df["year"].tolist()
    if years != expected_years:
        raise ValueError("Generated baseline must contain one row for each year 2025-2100.")

    totals = df["tob_total_billions"]
    if (totals <= 0).any():
        bad_years = df.loc[totals <= 0, "year"].tolist()
        raise ValueError(f"Generated baseline has non-positive totals for years: {bad_years}")

    if not np.allclose(
        df["tob_oasdi_billions"] + df["tob_hi_billions"],
        df["tob_total_billions"],
        atol=1e-9,
    ):
        raise ValueError("OASDI + HI must equal total TOB revenue in every year.")

    if not np.allclose(df["oasdi_share"] + df["hi_share"], 1.0, atol=1e-9):
        raise ValueError("OASDI share + HI share must equal 1 in every year.")

    # Cross-check against the TR2026 target extract: the published baseline
    # must equal the raw Trustees/CMS series in every overlapping year.
    aux = pd.read_csv(TR2026_AUX_PATH).set_index("year")
    merged = df.set_index("year")
    overlap = merged.index.intersection(aux.index)
    if len(overlap) < 70:
        raise ValueError(
            f"Generated baseline overlaps the TR2026 extract in only "
            f"{len(overlap)} years."
        )
    for column, aux_column in [
        ("tob_oasdi_billions", "oasdi_tob_billions_nominal_usd"),
        ("tob_hi_billions", "hi_tob_billions_nominal_usd"),
    ]:
        if not np.allclose(
            merged.loc[overlap, column],
            aux.loc[overlap, aux_column],
            atol=1e-6,
            equal_nan=False,
        ):
            raise ValueError(
                f"Generated baseline {column} diverges from the TR2026 extract."
            )


def write_tob_baseline(df: pd.DataFrame, output_path: Path = GENERATED_BASELINE_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.10f")


def build_tob_baseline_manifest(
    baseline_path: Path = GENERATED_BASELINE_PATH,
) -> dict[str, object]:
    if not baseline_path.exists():
        raise FileNotFoundError(f"Generated TOB baseline not found: {baseline_path}")

    baseline = pd.read_csv(baseline_path)
    validate_generated_baseline(baseline)

    hi_methods = _unique_values(baseline, "hi_method")
    if len(hi_methods) != 1:
        raise ValueError(f"Expected exactly one HI bridge method, got {hi_methods}")

    output_sha256 = file_sha256(baseline_path)
    source_files = [
        {
            "role": "tr2026_target_extract",
            "path": _relative_to_repo(TR2026_AUX_PATH),
            "sha256": file_sha256(TR2026_AUX_PATH),
        },
        {
            "role": "tr2026_source_manifest",
            "path": _relative_to_repo(TR2026_SOURCES_MANIFEST_PATH),
            "sha256": file_sha256(TR2026_SOURCES_MANIFEST_PATH),
        },
        {
            "role": "legacy_tr2025_current_law_comparator",
            "path": _relative_to_repo(CURRENT_LAW_PATH),
            "sha256": file_sha256(CURRENT_LAW_PATH),
        },
        {
            "role": "oact_post_obbba_oasdi_nominal_delta",
            "path": _relative_to_repo(OACT_OASDI_DELTA_PATH),
            "sha256": file_sha256(OACT_OASDI_DELTA_PATH),
        },
        {
            "role": "ssa_economic_projection",
            "path": _relative_to_repo(SSA_ECONOMIC_PROJECTIONS_PATH),
            "sha256": file_sha256(SSA_ECONOMIC_PROJECTIONS_PATH),
        },
    ]

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario_id": TOB_BASELINE_SCENARIO_ID,
        "calibration_target_id": TOB_BASELINE_TARGET_ID,
        "baseline_kind": "calibration_target",
        "not_law": False,
        "law_mode": TOB_BASELINE_LAW_MODE,
        "baseline_path": _relative_to_repo(baseline_path),
        "baseline_sha256": output_sha256,
        "output": {
            "path": _relative_to_repo(baseline_path),
            "sha256": output_sha256,
            "rows": int(len(baseline)),
            "years": [
                int(baseline["year"].min()),
                int(baseline["year"].max()),
            ],
            "units": "billions_of_nominal_dollars",
        },
        "source_files": source_files,
        "raw_current_law_comparator": source_files[0],
        "target_source": {
            "oasdi": SOURCE_OASDI,
            "hi": SOURCE_HI_CMS_DIRECTION,
            "current_law": SOURCE_CURRENT_LAW,
        },
        "bridge_methods": {
            "oasdi_delta_methods": _unique_values(baseline, "oasdi_delta_method"),
            "hi_method": hi_methods[0],
            "hi_notes": _unique_values(baseline, "notes"),
        },
        "artifact_contract": {
            "must_consume_baseline_sha256": output_sha256,
            "must_expose_scenario_id": POST_OBBBA_SCENARIO_ID,
            "reject_raw_current_law_substitution": True,
        },
        "builder": {
            "module": _relative_to_repo(Path(__file__)),
            "module_sha256": file_sha256(Path(__file__)),
            "script": _relative_to_repo(REPO_ROOT / "scripts" / "build_tob_baseline.py"),
            "script_sha256": file_sha256(REPO_ROOT / "scripts" / "build_tob_baseline.py"),
            "git_head": _git_value("rev-parse", "HEAD"),
            "git_dirty": bool(_git_value("status", "--short")),
        },
    }


def write_tob_baseline_manifest(
    baseline_path: Path = GENERATED_BASELINE_PATH,
    manifest_path: Path = GENERATED_BASELINE_MANIFEST_PATH,
) -> dict[str, object]:
    manifest = build_tob_baseline_manifest(baseline_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_tob_baseline_manifest(
    manifest_path: Path = GENERATED_BASELINE_MANIFEST_PATH,
) -> dict[str, object]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Generated TOB baseline manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def validate_tob_baseline_manifest(
    baseline_path: Path = GENERATED_BASELINE_PATH,
    manifest_path: Path | None = None,
) -> dict[str, object]:
    if manifest_path is None:
        manifest_path = baseline_path.with_suffix(".manifest.json")
    manifest = load_tob_baseline_manifest(manifest_path)
    expected = {
        "scenario_id": TOB_BASELINE_SCENARIO_ID,
        "baseline_kind": "calibration_target",
        "not_law": False,
        "law_mode": TOB_BASELINE_LAW_MODE,
    }
    for key, expected_value in expected.items():
        actual = manifest.get(key)
        if actual != expected_value:
            raise ValueError(
                f"Invalid generated TOB baseline manifest {manifest_path}: "
                f"{key}={actual!r}, expected {expected_value!r}"
            )

    actual_sha256 = file_sha256(baseline_path)
    expected_sha256 = manifest.get("baseline_sha256")
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Generated TOB baseline hash mismatch for {baseline_path}: "
            f"{actual_sha256} != {expected_sha256}"
        )
    contract = manifest.get("artifact_contract", {})
    if not isinstance(contract, dict) or (
        contract.get("must_consume_baseline_sha256") != actual_sha256
    ):
        raise ValueError(
            f"Generated TOB baseline manifest {manifest_path} does not carry "
            "the required artifact hash contract."
        )
    return manifest
