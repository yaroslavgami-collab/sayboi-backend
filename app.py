import os
import uuid
import base64
import json
import requests

from flask import Flask, request, jsonify
from flask_cors import CORS

from database import (
    init_database,
    create_purchase,
    get_purchase,
    complete_purchase,
    activate_premium
)

from liqpay_service import liqpay


# ==========================================
# CONFIG
# ==========================================

CHANNEL_ID = -1004410613751

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")


# ==========================================
# APP
# ==========================================

app = Flask(__name__)

CORS(
    app,
    origins=["https://sayboi.netlify.app"]
)

init_database()


# ==========================================
# COURSES
# ==========================================

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


# ==========================================
# TELEGRAM
# ==========================================

def create_channel_invite():

    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN is not set")
        return None

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/createChatInviteLink"
    )

    payload = {
        "chat_id": CHANNEL_ID,
        "member_limit": 1
    }

    response = requests.post(
        url,
        json=payload,
        timeout=15
    )

    result = response.json()

    print("Telegram invite response:", result)

    if not result.get("ok"):
        return None

    return result["result"]["invite_link"]


def send_telegram_message(
    telegram_id,
    invite_link
):

    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN is not set")
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    text = (
       "🎉 Оплату успішно завершено!\n\n"
"Ласкаво просимо до SAY BOI Premium 👑\n\n"
"Твоє персональне посилання "
"для входу до закритого каналу:\n\n"
f"{invite_link}\n\n"
"⚠️ Це посилання призначене лише для тебе."
    )

    payload = {
        "chat_id": telegram_id,
        "text": text
    }

    response = requests.post(
        url,
        json=payload,
        timeout=15
    )

    result = response.json()

    print("Telegram message response:", result)

    return result.get("ok", False)


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    return "SAY BOI Backend работает"


# ==========================================
# CREATE PAYMENT
# ==========================================

@app.route("/create-payment", methods=["POST"])
def create_payment():

    data = request.json

    telegram_id = data.get("telegram_id")

    course = data.get("course")

    if not telegram_id:
        return jsonify({
            "success": False,
            "message": "Telegram ID не указан"
        }), 400

    if course not in COURSES:

        return jsonify({
            "success": False,
            "message": "Курс не найден"
        }), 400

    amount = COURSES[course]["price"]

    order_id = (
        "SB-" +
        uuid.uuid4().hex[:12].upper()
    )

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


# ==========================================
# LIQPAY CALLBACK
# ==========================================

@app.route("/callback", methods=["POST"])
def liqpay_callback():

    data = request.form.get("data")

    if not data:
        return "No data", 400

    try:

        decoded = json.loads(
            base64.b64decode(data).decode("utf-8")
        )

    except Exception as e:

        print("Callback decode error:", e)

        return "Invalid data", 400


    status = decoded.get("status")

    order_id = decoded.get("order_id")


    print("LiqPay status:", status)
    print("LiqPay order:", order_id)


    if status != "success":

        return "Ignored", 200


    purchase = get_purchase(order_id)

    if purchase is None:

        print("Purchase not found:", order_id)

        return "Purchase not found", 404


    telegram_id = purchase["telegram_id"]


    # ======================================
    # ACTIVATE PREMIUM
    # ======================================

    activate_premium(telegram_id)


    # ======================================
    # COMPLETE PURCHASE
    # ======================================

    complete_purchase(order_id)


    # ======================================
    # CREATE CHANNEL INVITE
    # ======================================

    invite_link = create_channel_invite()


    if not invite_link:

        print(
            "ERROR: Could not create Telegram invite"
        )

        return "Premium activated, invite failed", 200


    # ======================================
    # SEND INVITE TO USER
    # ======================================

    sent = send_telegram_message(
        telegram_id,
        invite_link
    )


    if not sent:

        print(
            "ERROR: Could not send Telegram message"
        )


    return "OK", 200


# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
