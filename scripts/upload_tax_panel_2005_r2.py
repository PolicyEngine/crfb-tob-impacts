"""Upload certified tax_panel_2005 cell artifacts to R2 and write lineage.

Mirrors the magi100 lineage layout: for each of the 18 anchor cells, uploads
``scenario.h5`` + ``metadata.json`` to
``r2://axiom-corpus/crfb/reform_full_h5/<run_prefix>/reform_full_h5/year=Y/reform=tax_panel_2005/``
and records ``tmp/tax_panel_2005_lineage.json`` with the r2 URIs and the
worker-recorded output H5 sha256 per year.

Credentials come from the environment (CRFB_R2_ACCOUNT_ID,
CRFB_R2_ACCESS_KEY_ID, CRFB_R2_SECRET_ACCESS_KEY), matching
``scripts/aggregate_reform_full_h5_results.py``.
"""

import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "agg", Path(__file__).resolve().parent / "aggregate_reform_full_h5_results.py"
)
agg = importlib.util.module_from_spec(spec)
sys.modules["agg"] = agg
spec.loader.exec_module(agg)

MAIN = Path(__file__).resolve().parents[1]
RUN_PREFIX = "tax_panel_2005_certrepro_20260717"
ROOT = MAIN / "tmp/full_h5_tax_panel_2005" / RUN_PREFIX / "reform_full_h5"
BUCKET = "axiom-corpus"
KEY_ROOT = f"crfb/reform_full_h5/{RUN_PREFIX}/reform_full_h5"
ANCHOR_YEARS = (2026, 2028, 2029, 2030, *range(2035, 2101, 5))


def main() -> int:
    client = agg._r2_client_from_env()
    lineage = {}
    for year in ANCHOR_YEARS:
        cell = ROOT / f"year={year}" / "reform=tax_panel_2005"
        scenario = cell / "scenario.h5"
        metadata_path = cell / "metadata.json"
        if not scenario.exists() or not metadata_path.exists():
            raise RuntimeError(f"cell artifacts missing for {year}")
        metadata = json.loads(metadata_path.read_text())
        key_base = f"{KEY_ROOT}/year={year}/reform=tax_panel_2005"
        client.upload_file(str(scenario), BUCKET, f"{key_base}/scenario.h5")
        client.upload_file(str(metadata_path), BUCKET, f"{key_base}/metadata.json")
        lineage[str(year)] = {
            "scenario_h5_uri": f"r2://{BUCKET}/{key_base}/scenario.h5",
            "metadata_uri": f"r2://{BUCKET}/{key_base}/metadata.json",
            "output_h5_sha256": metadata["output_h5_sha256"],
        }
        print(f"uploaded {year}")
    dest = MAIN / "tmp/tax_panel_2005_lineage.json"
    dest.write_text(json.dumps(lineage, indent=1))
    print(f"wrote {dest} ({len(lineage)} years)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
