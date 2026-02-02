from fastapi import APIRouter
from datetime import datetime
from ..models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns the current health status of the API service.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(),
        api="AIropa Automation Layer",
        database="not_connected",  # Will update when we add database
        pipeline="not_connected"   # Will update when we connect to pipeline
    )