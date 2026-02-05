import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.database import get_db
from ..models.schemas import HealthResponse
from ..rate_limit import DEFAULT_RATE_LIMIT, limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
@limiter.limit(DEFAULT_RATE_LIMIT)
async def health_check(request: Request, db: Session = Depends(get_db)):
    """
    Health check endpoint

    Returns the current health status of the API service.
    """
    # Check database connection
    database_status = "not_connected"
    try:
        # Try to execute a simple query
        db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        # Log the actual error, return generic status to client
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        database_status = "error"

    # Pipeline is always available (imported from airopa_automation.agents)
    pipeline_status = "available"

    # Determine overall status
    overall_status = "healthy" if database_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now(),
        api="AIropa Automation Layer",
        database=database_status,
        pipeline=pipeline_status,
    )
