from __future__ import annotations

import argparse
import json

import modal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Spawn a single call against a deployed Modal function."
    )
    parser.add_argument("--app-name", required=True, help="Deployed Modal app name.")
    parser.add_argument(
        "--function-name",
        required=True,
        help="Deployed Modal function name.",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--scenario-name", required=True)
    parser.add_argument("--reform-id", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    function = modal.Function.from_name(args.app_name, args.function_name)
    call = function.spawn(
        args.run_id,
        args.year,
        args.scenario_name,
        args.reform_id,
    )
    payload = {
        "call_id": call.object_id,
        "dashboard_url": call.get_dashboard_url(),
        "function_name": args.function_name,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
