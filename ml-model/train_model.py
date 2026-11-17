import joblib
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "incident_training_data.csv"
MODEL_FILE = BASE_DIR / "root_cause_model.joblib"

FEATURES = [
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "health_healthy",
    "error_count",
    "warning_count",
]

def train():
    import pandas as pd

    data = pd.read_csv(DATA_FILE)
    X = data[FEATURES]
    y = data["root_cause"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        random_state=42,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    print("Random Forest Model Evaluation")
    print("-" * 40)
    print(f"Training records: {len(X_train)}")
    print(f"Testing records : {len(X_test)}")
    print(f"Accuracy        : {accuracy_score(y_test, predictions):.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, predictions))

    joblib.dump({
        "model": model,
        "features": FEATURES,
    }, MODEL_FILE)

    print(f"\nModel saved: {MODEL_FILE}")

if __name__ == "__main__":
    train()
