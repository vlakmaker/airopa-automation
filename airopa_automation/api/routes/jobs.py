"""
Jobs API endpoints
"""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
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


@router.post("/scrape/sync", response_model=JobResponse)
@limiter.limit(SCRAPE_RATE_LIMIT)
async def trigger_scrape_sync(
    request: Request,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Synchronous scrape — runs the full pipeline and returns when complete.

    Unlike POST /api/scrape, this endpoint does NOT use background tasks.
    The pipeline runs within the request lifecycle, so the response contains
    the final job status (completed or failed).

    Designed for cron/CI callers that need to wait for completion anyway.
    Expects a long timeout on the client side (e.g. curl --max-time 600).

    **Authentication:** Requires X-API-Key header with valid API key.
    **Rate Limit:** 5 requests per minute per IP address.
    """
    job_id = str(uuid4())

    try:
        # Create job record
        job = DBJob(
            id=job_id,
            status=JobStatus.queued.value,
            job_type="scrape",
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()

        # Run pipeline synchronously
        pipeline_service = get_pipeline_service()
        pipeline_service.run_scrape_job(job_id)

        # Re-fetch job to get updated status set by the pipeline
        db.expire(job)
        db.refresh(job)

        return JobResponse(
            job_id=job.id,
            status=JobStatus(job.status),
            job_type=job.job_type,
            timestamp=job.started_at,
            result_count=job.result_count,
            error_message=job.error_message,
        )

    except Exception as e:
        logger.error(
            f"Error in synchronous scrape job {job_id}: {str(e)}", exc_info=True
        )
        # Clear any failed transaction state before re-querying
        db.rollback()
        # Try to fetch the job — pipeline may have already marked it as failed
        try:
            failed_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if failed_job and failed_job.status == "failed":
                return JSONResponse(
                    status_code=500,
                    content={
                        "job_id": failed_job.id,
                        "status": failed_job.status,
                        "job_type": failed_job.job_type,
                        "timestamp": failed_job.started_at.isoformat()
                        if failed_job.started_at
                        else None,
                        "result_count": failed_job.result_count,
                        "error_message": failed_job.error_message,
                    },
                )
        except Exception as db_err:
            logger.warning(f"Could not fetch job status after error: {db_err}")
        raise HTTPException(
            status_code=500,
            detail=f"Scrape job {job_id} failed: {str(e)}",
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
