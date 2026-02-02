from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "api": "AIropa Automation Layer"
    }