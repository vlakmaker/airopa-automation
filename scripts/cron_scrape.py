"""
Cron job script for scheduled scraping.

Runs the full pipeline (scrape → classify → score → store) directly,
without going through the API. Designed to be triggered by Railway Cron.

Usage:
    python scripts/cron_scrape.py
"""

import os
import sys
import uuid
from datetime import datetime

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airopa_automation.api.models.database import Job as DBJob  # noqa: E402
from airopa_automation.api.models.database import SessionLocal, init_db  # noqa: E402
from airopa_automation.api.services.pipeline import PipelineService  # noqa: E402


def main():
    print(f"[cron] Starting scheduled scrape at {datetime.utcnow().isoformat()}")

    # Ensure tables exist
    init_db()

    # Create a job record so the scrape is tracked
    job_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        job = DBJob(
            id=job_id,
            status="queued",
            job_type="scrape",
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()

    # Run the pipeline
    pipeline = PipelineService()
    pipeline.run_scrape_job(job_id)

    print(f"[cron] Scrape job {job_id} finished at {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    main()
