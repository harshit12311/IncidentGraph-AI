
from fastapi import FastAPI, Query
from database.storage import (
    initialize_database,
    get_recent_incidents,
    get_incident_summary,
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