import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from airopa_automation.api.models.database import init_db
from airopa_automation.api.rate_limit import limiter
from airopa_automation.api.routes import articles, health, jobs

app = FastAPI(
    title="AIropa API",
    version="1.0.0",
    description="API for AIropa Automation Layer - Content automation and processing",
    contact={"name": "AIropa Team", "email": "tech@airopa.eu"},
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
)

# Configure rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on application startup"""
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")


# Configure CORS - Restricted to known origins only
# Add your frontend domain to ALLOWED_ORIGINS environment variable if needed
ALLOWED_ORIGINS = (
    os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
)
DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://web-production-bcd96.up.railway.app",
]
# Combine default origins with any custom origins from environment
cors_origins = [
    origin.strip() for origin in (DEFAULT_ORIGINS + ALLOWED_ORIGINS) if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Only methods we actually use
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
    ],  # Only headers we need
)

# Include routers
app.include_router(health.router)
app.include_router(articles.router)
app.include_router(jobs.router)


@app.get("/")
def root():
    """
    Root endpoint

    Returns basic information about the API service.
    """
    return {
        "message": "AIropa API - MVI",
        "status": "development",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "health": "/api/health",
            "articles": "/api/articles",
            "article_detail": "/api/articles/{id}",
            "scrape": "/api/scrape",
            "job_status": "/api/jobs/{job_id}",
        },
    }
