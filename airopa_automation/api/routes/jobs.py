"""
Jobs API endpoints
"""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import verify_api_key
from ..models.database import Job as DBJob
from ..models.database import get_db
from ..models.schemas import JobResponse, JobStatus
from ..rate_limit import DEFAULT_RATE_LIMIT, SCRAPE_RATE_LIMIT, limiter
from ..services import get_pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/scrape", response_model=JobResponse)
@limiter.limit(SCRAPE_RATE_LIMIT)
async def trigger_scrape(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Trigger a scraping job (requires API key authentication)

    Starts a background job that runs the automation pipeline to scrape,
    classify, and process articles from configured RSS feeds.

    Returns a job ID that can be used to check the status of the job.

    **Authentication:** Requires X-API-Key header with valid API key.
    **Rate Limit:** 5 requests per minute per IP address.
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
        # Log the actual error for debugging, return generic message to client
        logger.error(f"Error creating scrape job: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while creating the scrape job"
        )


@router.get("/jobs/{job_id}", response_model=JobResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def get_job_status(request: Request, job_id: str, db: Session = Depends(get_db)):
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
        # Log the actual error for debugging, return generic message to client
        logger.error(
            f"Error retrieving job status for {job_id}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while retrieving the job status"
        )
