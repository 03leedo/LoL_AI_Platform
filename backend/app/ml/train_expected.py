"""Build the expected-performance dataset and report (GD/CSD/XPD@10).

Run inside the backend container (or any env with DATABASE_URL set):

    docker compose exec backend python -m app.ml.train_expected
    # options: --queue 420 --test-fraction 0.3 --out /app/tmp/expected_report.json

Report-only: grouped-average expected values and residual definitions; nothing
is wired into serving or profiles by this script.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.ml.advantage_dataset import DEFAULT_QUEUE_ID
from app.ml.expected_performance import TEST_FRACTION, build_expected_dataset, run_expected_report


async def _run(queue_id: int, test_fraction: float, out_path: Path | None) -> dict:
    async with AsyncSessionLocal() as db:
        dataset = await build_expected_dataset(db, queue_id=queue_id)
    report = run_expected_report(dataset, test_fraction=test_fraction)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["matches_excluded"] = dataset["matches_excluded"]

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _print_summary(report: dict) -> None:
    print(f"status: {report['status']}")
    print(f"matches: {report.get('matches')}  rows: {report.get('participant_rows')}")
    if report["status"] == "evaluated":
        split = report["split"]
        print(
            f"split: {split['train_matches']} train / {split['test_matches']} test matches "
            f"({split['train_rows']}/{split['test_rows']} rows, temporal match-grouped)"
        )
        for target, per_baseline in report["baseline_evaluations"].items():
            best = report["best_baselines"][target]
            parts = ", ".join(
                f"{name} mae={metrics['mae']:.1f}" for name, metrics in per_baseline.items()
            )
            print(f"{target}: {parts}  -> best: {best}")
    verdict = report["verdict"]
    print(f"verdict: {verdict['verdict']}")
    for reason in verdict["reasons"]:
        print(f"  - {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=int, default=DEFAULT_QUEUE_ID)
    parser.add_argument("--test-fraction", type=float, default=TEST_FRACTION)
    parser.add_argument("--out", type=str, default="tmp/expected_report.json")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else None
    report = asyncio.run(_run(args.queue, args.test_fraction, out_path))
    _print_summary(report)
    if out_path:
        print(f"report written: {out_path}")


if __name__ == "__main__":
    main()
