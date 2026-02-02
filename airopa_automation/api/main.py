from fastapi import FastAPI
from airopa_automation.api.routes import health

app = FastAPI(title="AIropa API", version="1.0.0")

# Include routers
app.include_router(health.router)

@app.get("/")
def root():
    return {"message": "AIropa API - MVI", "status": "development"}