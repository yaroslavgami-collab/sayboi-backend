from flask import Flask, request, jsonify
from database import init_db

init_db()
from database import (
    init_db,
    create_purchase
)

from liqpay_service import liqpay

import uuid

app = Flask(__name__)

init_db()


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


if __name__ == "__main__":

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
