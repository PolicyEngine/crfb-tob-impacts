"""Build the 2090 baseline locally (the lone Modal straggler).

Mirrors modal_batch/build_baselines.build_one_year exactly: Stage A-D on the
certified populace base via the managed path, writing {year}.h5 + sidecar to
projected_datasets_newbase/. Run locally to sidestep Modal spot preemption,
which killed this single far-horizon year repeatedly.
"""

from __future__ import annotations

import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import certified_base_build_id, certified_base_uri  # noqa: E402
from src.pipeline import build_year  # noqa: E402

YEAR = 2090
OUT = ROOT / "projected_datasets_newbase"
OUT.mkdir(parents=True, exist_ok=True)


def _json_safe(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return float(value)


def main() -> None:
    t0 = time.monotonic()
    base_uri = certified_base_uri()
    print(f"building {YEAR} on certified base {certified_base_build_id()}", flush=True)
    sentinel = build_year(
        YEAR,
        base_uri,
        OUT,
        base_dataset_label=base_uri,
        policyengine_us_version=metadata.version("policyengine-us"),
    )
    sentinel = {k: _json_safe(v) for k, v in dict(sentinel).items()}
    (OUT / f"{YEAR}.sentinel.json").write_text(json.dumps(sentinel, sort_keys=True))
    mins = (time.monotonic() - t0) / 60
    s = sentinel

    def num(key):
        try:
            return float(s.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def pct(a, t):
        return f"{(a / t - 1) * 100:+.1f}%" if t else "n/a"

    print(
        f"\nDONE {YEAR} in {mins:.1f} min | "
        f"ESS {num('final_effective_sample_size'):,.0f} | "
        f"oasdi_tob ${num('oasdi_tob_achieved') / 1e9:,.1f}B "
        f"({pct(num('oasdi_tob_achieved'), num('oasdi_tob_target'))}) | "
        f"hi_tob ${num('hi_tob_achieved') / 1e9:,.1f}B "
        f"({pct(num('hi_tob_achieved'), num('hi_tob_target'))}) | "
        f"ss ${num('ss_total_achieved') / 1e12:.3f}T "
        f"({pct(num('ss_total_achieved'), num('ss_total_target'))}) | "
        f"gamma {num('gamma_other_income_scale'):.3f} | "
        f"gates {s.get('gates_passed')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
