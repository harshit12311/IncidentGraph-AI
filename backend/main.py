
from fastapi import FastAPI, Query
from database.storage import (
    initialize_database,
    get_recent_incidents,
    get_incident_by_id,
    get_incident_summary,
    get_recent_website_checks,
    get_website_check_summary,
)

app = FastAPI(
    title="IncidentGraph AI API",
    description="API for incident monitoring and root cause analysis",
    version="1.0.0",
)

# Ensure the incidents table exists when the API starts.
initialize_database()


@app.get("/")
def home():
    return {
        "message": "Welcome to IncidentGraph AI API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "IncidentGraph AI API",
    }


@app.get("/incidents")
def list_incidents(limit: int = Query(default=20, ge=1, le=100)):
    incidents = get_recent_incidents(limit=limit)

    return {
        "count": len(incidents),
        "incidents": incidents,
    }

@app.get("/incidents/summary")
def incident_summary():
    return get_incident_summary()


@app.get("/website-checks")
def list_website_checks(limit: int = Query(default=50, ge=1, le=500)):
    checks = get_recent_website_checks(limit=limit)
    return {"count": len(checks), "checks": checks}


@app.get("/website-checks/summary")
def website_check_summary():
    return get_website_check_summary()


from pydantic import BaseModel, Field
from typing import Optional
import sys
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent / "ml-model"

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from predictor import predict_root_cause, get_root_cause_recommendations


class PredictionRequest(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    healthy: bool
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


@app.post("/predict/root-cause")
def predict_incident_root_cause(request: PredictionRequest):
    metrics = {
        "cpu_percent": request.cpu_percent,
        "memory_percent": request.memory_percent,
        "disk_percent": request.disk_percent,
    }

    health = {"healthy": request.healthy}

    log_analysis = {
        "error_count": request.error_count,
        "warning_count": request.warning_count,
    }

    return predict_root_cause(metrics, health, log_analysis)


# Serve the IncidentGraph AI dashboard and its static assets.
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app.mount(
    "/frontend",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="frontend",
)


@app.get("/dashboard")
def dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/incidents/{incident_id}")
def incident_details(incident_id: str):
    incident = get_incident_by_id(incident_id)

    if incident is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    incident["recommendations"] = get_root_cause_recommendations(
        incident.get("predicted_root_cause")
    )

    return incident
