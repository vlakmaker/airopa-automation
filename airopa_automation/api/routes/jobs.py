"""
Jobs API endpoints
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.database import Job as DBJob
from ..models.database import get_db
from ..models.schemas import JobResponse, JobStatus
from ..services import get_pipeline_service

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/scrape", response_model=JobResponse)
async def trigger_scrape(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Trigger a scraping job

    Starts a background job that runs the automation pipeline to scrape,
    classify, and process articles from configured RSS feeds.

    Returns a job ID that can be used to check the status of the job.
    """
    try:
        # Generate unique job ID
        job_id = str(uuid4())

        # Create job record in database
        job = DBJob(
            id=job_id,
            status=JobStatus.queued.value,
            job_type="scrape",
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Add background task to run the scraping pipeline
        pipeline_service = get_pipeline_service()
        background_tasks.add_task(pipeline_service.run_scrape_job, job_id)

        return JobResponse(
            job_id=job.id,
            status=JobStatus(job.status),
            job_type=job.job_type,
            timestamp=job.started_at,
            result_count=job.result_count,
            error_message=job.error_message,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating scrape job: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Get job status

    Returns the current status of a job, including completion status,
    result count, and any error messages.
    """
    try:
        # Query job by ID
        job = db.query(DBJob).filter(DBJob.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobResponse(
            job_id=job.id,
            status=JobStatus(job.status),
            job_type=job.job_type,
            timestamp=job.started_at,
            result_count=job.result_count,
            error_message=job.error_message,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving job status: {str(e)}"
        )
