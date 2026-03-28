from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.tob_baseline import GENERATED_BASELINE_PATH, validate_generated_baseline


def main(path: Path = GENERATED_BASELINE_PATH) -> None:
    baseline = pd.read_csv(path)
    validate_generated_baseline(baseline)
    print(f"{path} passed baseline validation.")


if __name__ == "__main__":
    main()
