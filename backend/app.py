from flask import Flask, request, jsonify
from database import init_database
from flask_cors import CORS


init_database()
from database import (
    init_database,
    create_purchase,
    get_purchase,
    complete_purchase,
    activate_premium
)

from liqpay_service import liqpay

import uuid

app = Flask(__name__)
CORS(app, origins=["https://sayboi.netlify.app"])

init_database()


COURSES = {
    "starter": {
        "name": "Starter",
        "price": 500
    },

    "plus": {
        "name": "Plus",
        "price": 1000
    },

    "premium": {
        "name": "Premium",
        "price": 1500
    }
}


@app.route("/")
def home():

    return "SAY BOI Backend работает"


@app.route("/create-payment", methods=["POST"])
def create_payment():

    data = request.json

    telegram_id = data.get("telegram_id")

    course = data.get("course")

    if course not in COURSES:

        return jsonify({

            "success": False,

            "message": "Курс не найден"

        }), 400

    amount = COURSES[course]["price"]

    order_id = "SB-" + uuid.uuid4().hex[:12].upper()

    create_purchase(

        telegram_id,

        course,

        amount,

        order_id

    )

    payment = liqpay.create_payment(

        course,

        amount,

        order_id

    )

    return jsonify({

        "success": True,

        "order_id": order_id,

        "data": payment["data"],

        "signature": payment["signature"],

        "checkout_url": payment["checkout_url"]

    })

import os
import base64
import json


@app.route("/callback", methods=["POST"])
def liqpay_callback():

    data = request.form.get("data")

    if not data:
        return "No data", 400

    decoded = json.loads(
        base64.b64decode(data).decode("utf-8")
    )

    status = decoded.get("status")
    order_id = decoded.get("order_id")

    if status != "success":
        return "Ignored", 200

    purchase = get_purchase(order_id)

    if purchase is None:
        return "Purchase not found", 404

    telegram_id = purchase["telegram_id"]

    activate_premium(telegram_id)

    complete_purchase(order_id)

    return "OK", 200
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)