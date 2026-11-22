from flask import Flask, jsonify, render_template
from datetime import datetime
import logging
import os
import requests

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "demoshop.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

PRODUCT_API_URL = "https://dummyjson.com/products?limit=30"


@app.route("/")
def home():
    logging.info("DemoShop home page accessed")
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "DemoShop",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/products")
def products():
    logging.info("Fetching products from DummyJSON")

    try:
        response = requests.get(PRODUCT_API_URL, timeout=8)
        response.raise_for_status()
        data = response.json()

        products = [
            {
                "id": item["id"],
                "name": item["title"],
                "price": item["price"],
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "image": item.get("thumbnail", ""),
                "rating": item.get("rating", 0),
                "stock": item.get("stock", 0),
                "brand": item.get("brand", "Generic")
            }
            for item in data.get("products", []) if item.get("title", "").strip().lower() != "beef steak"
        ]

        logging.info("Successfully loaded %s products", len(products))
        return jsonify(products)

    except requests.RequestException as error:
        logging.error("DummyJSON product API failure: %s", error)
        return jsonify({
            "status": "error",
            "message": "Our product service is temporarily unavailable."
        }), 502

    except (ValueError, KeyError) as error:
        logging.error("Invalid product API response: %s", error)
        return jsonify({
            "status": "error",
            "message": "Unable to process product data."
        }), 502


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

    app.run(host="0.0.0.0", port=5000, debug=False)
