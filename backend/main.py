
from fastapi import FastAPI, Query, Depends
from backend.auth_routes import router as auth_router
from backend.website_routes import router as website_router
from backend.permissions import require_active_user, require_admin
from backend.llm_service import generate_incident_explanation
from database.auth_schema import initialize_auth_schema, initialize_ownership_schema

from database.storage import (
    initialize_database,
    get_recent_incidents,
    get_incident_by_id,
    get_incident_summary,
    get_recent_website_checks,
    get_website_check_summary,
    get_latest_application_health,
    get_user_recent_incidents,
    get_user_incident_by_id,
    get_user_incident_summary,
    get_user_recent_website_checks,
    get_user_website_check_summary,
)

app = FastAPI(
    title="IncidentGraph AI API",
    description="API for incident monitoring and root cause analysis",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(website_router)

# Ensure the incidents table exists when the API starts.
initialize_database()
initialize_auth_schema()
initialize_ownership_schema()


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
def list_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_active_user),
):
    incidents = (
        get_recent_incidents(limit=limit)
        if user["role"] == "admin"
        else get_user_recent_incidents(user["id"], limit=limit)
    )
    return {"count": len(incidents), "incidents": incidents}


@app.get("/incidents/correlated")
def correlated_incidents(
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(require_active_user),
):
    incidents = (
        get_recent_incidents(limit=limit)
        if user["role"] == "admin"
        else get_user_recent_incidents(user["id"], limit=limit)
    )
    events = [incident for incident in incidents if incident.get("timestamp")]
    groups = correlate_events(events, time_window_seconds=60)
    return {
        "count": len(groups),
        "correlated_groups": [
            {"event_count": len(group), "incidents": group}
            for group in groups if len(group) > 1
        ],
    }


@app.get("/incidents/summary")
def incident_summary(user: dict = Depends(require_active_user)):
    return (
        get_incident_summary()
        if user["role"] == "admin"
        else get_user_incident_summary(user["id"])
    )


@app.get("/website-checks")
def list_website_checks(
    limit: int = Query(default=50, ge=1, le=500),
    user: dict = Depends(require_active_user),
):
    checks = (
        get_recent_website_checks(limit=limit)
        if user["role"] == "admin"
        else get_user_recent_website_checks(user["id"], limit=limit)
    )
    return {"count": len(checks), "checks": checks}


@app.get("/application-health")
def application_health(user: dict = Depends(require_admin)):
    records = get_latest_application_health()
    return {"count": len(records), "applications": records}

@app.get("/website-checks/summary")
def website_check_summary(user: dict = Depends(require_active_user)):
    return (
        get_website_check_summary()
        if user["role"] == "admin"
        else get_user_website_check_summary(user["id"])
    )


from pydantic import BaseModel, Field
from typing import Optional
import sys
from pathlib import Path
import importlib.util

ML_DIR = Path(__file__).resolve().parent.parent / "ml-model"

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from predictor import predict_root_cause, get_root_cause_recommendations

CORRELATOR_PATH = Path(__file__).resolve().parent.parent / "event-correlation" / "correlator.py"
CORRELATOR_SPEC = importlib.util.spec_from_file_location("incident_correlator", CORRELATOR_PATH)
CORRELATOR_MODULE = importlib.util.module_from_spec(CORRELATOR_SPEC)
CORRELATOR_SPEC.loader.exec_module(CORRELATOR_MODULE)
correlate_events = CORRELATOR_MODULE.correlate_events



class PredictionRequest(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    memory_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    healthy: bool
    error_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


@app.post("/predict/root-cause")
def predict_incident_root_cause(request: PredictionRequest, user: dict = Depends(require_active_user)):
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
def dashboard(user: dict = Depends(require_active_user)):
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/incidents/{incident_id}")
def incident_details(
    incident_id: str,
    user: dict = Depends(require_active_user),
):
    incident = (
        get_incident_by_id(incident_id)
        if user["role"] == "admin"
        else get_user_incident_by_id(user["id"], incident_id)
    )

    if incident is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    incident["recommendations"] = get_root_cause_recommendations(
        incident.get("predicted_root_cause")
    )

    return incident

DEPENDENCY_GRAPH_PATH = Path(__file__).resolve().parent.parent / "dependency-graph" / "graph.py"
DEPENDENCY_GRAPH_SPEC = importlib.util.spec_from_file_location(
    "dependency_graph_module", DEPENDENCY_GRAPH_PATH
)
DEPENDENCY_GRAPH_MODULE = importlib.util.module_from_spec(DEPENDENCY_GRAPH_SPEC)
DEPENDENCY_GRAPH_SPEC.loader.exec_module(DEPENDENCY_GRAPH_MODULE)


@app.get("/dependency-graph")
def dependency_graph_data(user: dict = Depends(require_admin)):
    graph = DEPENDENCY_GRAPH_MODULE.create_dependency_graph()

    return {
        "nodes": [
            {
                "id": name,
                "type": data.get("node_type", "unknown"),
                "url": data.get("url"),
            }
            for name, data in graph.nodes(data=True)
        ],
        "edges": [
            {"source": source, "target": target}
            for source, target in graph.edges()
        ],
    }



@app.post("/incidents/{incident_id}/ai-explanation")
def incident_ai_explanation(
    incident_id: str,
    user: dict = Depends(require_active_user),
):
    incident = (
        get_incident_by_id(incident_id)
        if user["role"] == "admin"
        else get_user_incident_by_id(user["id"], incident_id)
    )

    if not incident:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")

    result = generate_incident_explanation(incident)

    return {
        "incident_id": incident_id,
        "predicted_root_cause": incident.get("predicted_root_cause"),
        "confidence_percent": incident.get("confidence_percent"),
        "ai_analysis": result,
    }
