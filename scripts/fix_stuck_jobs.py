"""
Fix stuck jobs — marks any 'running' jobs older than 30 minutes as 'failed'.

Usage:
    python scripts/fix_stuck_jobs.py              # dry-run (shows what would change)
    python scripts/fix_stuck_jobs.py --apply       # actually update the database
"""

import argparse
from datetime import datetime, timedelta

from airopa_automation.api.models.database import Job, SessionLocal

TIMEOUT_MINUTES = 30


def fix_stuck_jobs(apply: bool = False) -> None:
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES)
        stuck_jobs = (
            db.query(Job).filter(Job.status == "running", Job.started_at < cutoff).all()
        )

        if not stuck_jobs:
            print("No stuck jobs found.")
            return

        print(f"Found {len(stuck_jobs)} stuck job(s):")
        for job in stuck_jobs:
            age = datetime.utcnow() - job.started_at
            print(f"  - {job.id}  started {age} ago  (type={job.job_type})")

            if apply:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.error_message = "timeout_cleanup"

        if apply:
            db.commit()
            print(f"Updated {len(stuck_jobs)} job(s) to 'failed'.")
        else:
            print("\nDry run — pass --apply to update the database.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix stuck running jobs")
    parser.add_argument("--apply", action="store_true", help="Actually update the DB")
    args = parser.parse_args()
    fix_stuck_jobs(apply=args.apply)
