"""Compatibility wrapper for the canonical CRFB results publisher.

Do not add dashboard-results construction logic here. The single implementation
is ``scripts.publish_dashboard_results`` so the repo has one public results
contract: root ``results.csv`` plus the dashboard deployment copy.
"""

from __future__ import annotations

from scripts.publish_dashboard_results import main


if __name__ == "__main__":
    raise SystemExit(main())
