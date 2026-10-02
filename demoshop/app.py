from flask import Flask, jsonify, render_template
from datetime import datetime
import logging
import os

app = Flask(__name__)

# Create logs directory if it does not exist
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

# Configure application logging
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "demoshop.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


@app.route("/")
def home():
    logging.info("DemoShop home page accessed")
    return render_template("index.html")


@app.route("/health")
def health():
    logging.info("DemoShop health check successful")

    return jsonify({
        "status": "healthy",
        "service": "DemoShop",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/products")
def products():
    logging.info("Product list requested")

    products = [
        {"id": 1, "name": "Laptop", "price": 55000},
        {"id": 2, "name": "Smartphone", "price": 25000},
        {"id": 3, "name": "Headphones", "price": 3000}
    ]

    return jsonify(products)

@app.route("/simulate-error")
def simulate_error():
    logging.error("CONTROLLED FAILURE: Simulated database connection error")
    return jsonify({
        "status": "error",
        "message": "Simulated database connection failure"
    }), 500
if __name__ == "__main__":
    print("DemoShop starting...")
    print("Open http://127.0.0.1:5000 in your browser")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )