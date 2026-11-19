import joblib
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_FILE = BASE_DIR / "root_cause_model.joblib"

_model_data = joblib.load(MODEL_FILE)
model = _model_data["model"]
FEATURES = _model_data["features"]


def predict_root_cause(metrics, health, log_analysis):
    """Predict the most likely incident root-cause category."""

    input_data = {
        "cpu_percent": metrics.get("cpu_percent", 0),
        "memory_percent": metrics.get("memory_percent", 0),
        "disk_percent": metrics.get("disk_percent", 0),
        "health_healthy": int(health.get("healthy", False)),
        "error_count": log_analysis.get("error_count", 0),
        "warning_count": log_analysis.get("warning_count", 0),
    }

    features = pd.DataFrame([input_data], columns=FEATURES)

    prediction = model.predict(features)[0]
    probabilities = model.predict_proba(features)[0]

    confidence = max(probabilities) * 100

    return {
        "predicted_root_cause": prediction,
        "confidence_percent": round(float(confidence), 2),
        "probabilities": {
            label: round(float(probability) * 100, 2)
            for label, probability in zip(
                model.classes_,
                probabilities
            )
        },
        "interpretation": (
            "Model prediction based on monitoring patterns; "
            "not a confirmed causal diagnosis."
        ),
    }


def get_root_cause_recommendations(root_cause):
    recommendations = {
        "high_cpu": [
            "Inspect CPU-intensive processes.",
            "Check for traffic spikes or excessive workloads.",
            "Review application performance and optimize expensive operations."
        ],
        "high_memory": [
            "Inspect memory-consuming processes.",
            "Check for memory leaks.",
            "Review application memory usage and restart affected services if necessary."
        ],
        "high_disk": [
            "Check available disk space.",
            "Inspect large log files and temporary files.",
            "Review disk usage growth and configure log rotation."
        ],
        "health_failure": [
            "Inspect the application health endpoint.",
            "Check application and service logs.",
            "Verify dependencies and restart the service if appropriate."
        ],
        "application_error": [
            "Inspect recent application error logs.",
            "Identify the failing request or application component.",
            "Review recent code changes and dependency failures."
        ],
        "multiple_causes": [
            "Investigate CPU, memory and disk utilization together.",
            "Review application health and error logs.",
            "Prioritize the most severe resource or application symptoms."
        ]
    }

    return recommendations.get(
        root_cause,
        ["Review application logs and system metrics for further investigation."]
    )
