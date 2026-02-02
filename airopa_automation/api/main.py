from fastapi import FastAPI
from airopa_automation.api.routes import health, articles

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

# Include routers
app.include_router(health.router)
app.include_router(articles.router)

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
            "article_detail": "/api/articles/{id}"
        }
    }