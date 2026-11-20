import os
import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate"
)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


def generate_incident_explanation(incident):
    prompt = f"""
You are an IT incident investigation assistant.

Incident evidence:
Application: {incident.get('application_name', 'Unknown')}
Predicted cause: {incident.get('predicted_root_cause', 'Unknown')}
ML confidence: {incident.get('confidence_percent', 0)}%
Severity: {incident.get('severity', 'Unknown')}
CPU: {incident.get('cpu_percent', 0)}%
Memory: {incident.get('memory_percent', 0)}%
Disk: {incident.get('disk_percent', 0)}%
Health: {incident.get('health_status', 'Unknown')}
Reasons: {incident.get('reasons', 'Not provided')}

Write exactly three short sections:

SUMMARY: Explain the incident in two sentences.

EVIDENCE: State what the supplied data supports. Do not invent causes.

ACTIONS: Give exactly three short investigation actions.

Important:
The predicted cause is a hypothesis, not a confirmed diagnosis.
Do not invent logs, database failures, or dependencies.
If evidence is insufficient, say so.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 120,
                    "num_ctx": 1024,
                    "temperature": 0.1
                }
            },
            timeout=(5, 120)
        )
        response.raise_for_status()

        result = response.json()
        explanation = result.get("response", "").strip()

        return {
            "available": bool(explanation),
            "explanation": explanation or None
        }

    except requests.RequestException as error:
        return {
            "available": False,
            "explanation": None,
            "error": str(error)
        }
