from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from airopa_automation.api.routes import health, articles, jobs

app = FastAPI(
    title="AIropa API",
    version="1.0.0",
    description="API for AIropa Automation Layer - Content automation and processing",
    contact={
        "name": "AIropa Team",
        "email": "tech@airopa.eu"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            "job_status": "/api/jobs/{job_id}"
        }
    }