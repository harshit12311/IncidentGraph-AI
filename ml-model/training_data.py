import numpy as np
import pandas as pd

np.random.seed(42)

DATA_PER_CLASS = 100

def generate_data():
    records = []

    profiles = {
        "high_cpu": {
            "cpu": (90, 100),
            "memory": (20, 75),
            "disk": (20, 75),
            "health": (1, 1),
            "errors": (0, 2),
            "warnings": (0, 5),
        },
        "high_memory": {
            "cpu": (20, 75),
            "memory": (90, 100),
            "disk": (20, 75),
            "health": (1, 1),
            "errors": (0, 2),
            "warnings": (0, 5),
        },
        "high_disk": {
            "cpu": (20, 75),
            "memory": (20, 75),
            "disk": (90, 100),
            "health": (1, 1),
            "errors": (0, 2),
            "warnings": (0, 5),
        },
        "health_failure": {
            "cpu": (10, 80),
            "memory": (10, 80),
            "disk": (10, 80),
            "health": (0, 0),
            "errors": (0, 3),
            "warnings": (0, 5),
        },
        "application_error": {
            "cpu": (10, 80),
            "memory": (10, 80),
            "disk": (10, 80),
            "health": (1, 1),
            "errors": (3, 10),
            "warnings": (0, 5),
        },
        "multiple_causes": {
            "cpu": (90, 100),
            "memory": (90, 100),
            "disk": (20, 90),
            "health": (0, 1),
            "errors": (2, 10),
            "warnings": (0, 5),
        },
    }

    for label, profile in profiles.items():
        for _ in range(DATA_PER_CLASS):
            records.append({
                "cpu_percent": np.random.uniform(*profile["cpu"]),
                "memory_percent": np.random.uniform(*profile["memory"]),
                "disk_percent": np.random.uniform(*profile["disk"]),
                "health_healthy": np.random.randint(
                    profile["health"][0],
                    profile["health"][1] + 1
                ),
                "error_count": np.random.randint(
                    profile["errors"][0],
                    profile["errors"][1] + 1
                ),
                "warning_count": np.random.randint(
                    profile["warnings"][0],
                    profile["warnings"][1] + 1
                ),
                "root_cause": label,
            })

    df = pd.DataFrame(records)
    return df.sample(frac=1, random_state=42).reset_index(drop=True)


if __name__ == "__main__":
    dataset = generate_data()
    output = "ml-model/incident_training_data.csv"
    dataset.to_csv(output, index=False)

    print("Training dataset generated.")
    print("Total records:", len(dataset))
    print("\nClass distribution:")
    print(dataset["root_cause"].value_counts())
    print("\nSaved to:", output)
