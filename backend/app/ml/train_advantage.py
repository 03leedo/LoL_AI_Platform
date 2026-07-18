"""Train and evaluate the advantage model against stored timelines.

Run inside the backend container (or any env with DATABASE_URL set):

    docker compose exec backend python -m app.ml.train_advantage
    # options: --queue 420 --test-fraction 0.3 --out /app/tmp/advantage_report.json

Writes the full JSON report (metrics, calibration, verdict, artifact) and
prints an honest summary. It never touches the serving path: adopting the
model is a separate, explicit decision gated by the report verdict.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import AsyncSessionLocal
from app.ml.advantage_dataset import DEFAULT_QUEUE_ID, build_dataset
from app.ml.advantage_model import TEST_FRACTION, run_training


async def _run(queue_id: int, test_fraction: float, out_path: Path | None) -> dict:
    async with AsyncSessionLocal() as db:
        dataset = await build_dataset(db, queue_id=queue_id)
    report = run_training(dataset, test_fraction=test_fraction)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    report["matches_excluded"] = dataset["matches_excluded"]

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _print_summary(report: dict) -> None:
    print(f"status: {report['status']}")
    print(f"matches: {report.get('matches')}  rows: {report.get('snapshot_rows')}")
    if report["status"] == "trained":
        split = report["split"]
        print(
            f"split: {split['train_matches']} train / {split['test_matches']} test matches "
            f"({split['train_rows']}/{split['test_rows']} rows, temporal match-grouped)"
        )
        me = report["model_eval"]
        print(
            f"model     — auc: {me['roc_auc']}, log_loss: {me['log_loss']:.4f}, "
            f"brier: {me['brier']:.4f}, ece: {me['ece']:.4f}"
        )
        for name, be in report["baseline_evals"].items():
            print(
                f"{name:<28}— auc: {be['roc_auc']}, log_loss: {be['log_loss']:.4f}, "
                f"brier: {be['brier']:.4f}, ece: {be['ece']:.4f}"
            )
    verdict = report["verdict"]
    print(f"verdict: {verdict['verdict']}")
    for reason in verdict["reasons"]:
        print(f"  - {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=int, default=DEFAULT_QUEUE_ID)
    parser.add_argument("--test-fraction", type=float, default=TEST_FRACTION)
    parser.add_argument("--out", type=str, default="tmp/advantage_report.json")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else None
    report = asyncio.run(_run(args.queue, args.test_fraction, out_path))
    _print_summary(report)
    if out_path:
        print(f"report written: {out_path}")


if __name__ == "__main__":
    main()
