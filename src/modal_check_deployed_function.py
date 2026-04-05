from __future__ import annotations

import argparse
import json

import modal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether a deployed Modal function is ready."
    )
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--function-name", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    function = modal.Function.from_name(args.app_name, args.function_name)
    function.hydrate()
    print(
        json.dumps(
            {
                "app_name": args.app_name,
                "function_name": args.function_name,
                "hydrated": function.is_hydrated,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
