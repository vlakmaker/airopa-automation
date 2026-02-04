from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from ..models.schemas import HealthResponse
from ..models.database import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
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
        database_status = f"error: {str(e)}"

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
        pipeline=pipeline_status
    )
