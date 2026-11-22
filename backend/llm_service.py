import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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
EVIDENCE: State what the supplied data supports.
ACTIONS: Give exactly three short investigation actions.

Important:
The predicted cause is a hypothesis, not a confirmed diagnosis.
Do not invent logs, database failures, or dependencies.
If evidence is insufficient, say so.
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You provide cautious, evidence-based IT incident analysis."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=250,
            temperature=0.2,
            timeout=30
        )

        explanation = response.choices[0].message.content

        return {
            "available": bool(explanation),
            "explanation": explanation.strip() if explanation else None
        }

    except Exception as error:
        return {
            "available": False,
            "explanation": None,
            "error": str(error)
        }
