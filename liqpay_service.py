import json
import base64
import hashlib

from config import PUBLIC_KEY, PRIVATE_KEY, BASE_URL


class LiqPayService:
    def create_payment(self, course, amount, order_id):
        params = {
            "public_key": PUBLIC_KEY,
            "version": "3",
            "action": "pay",
            "amount": amount,
            "currency": "UAH",
            "description": f"SAY BOI | {course}",
            "order_id": order_id,
            "result_url": f"{BASE_URL}/success",
            "server_url": f"{BASE_URL}/callback"
        }

        json_string = json.dumps(params)

        data = base64.b64encode(
            json_string.encode("utf-8")
        ).decode("utf-8")

        sign_string = PRIVATE_KEY + data + PRIVATE_KEY

        signature = base64.b64encode(
            hashlib.sha1(
                sign_string.encode("utf-8")
            ).digest()
        ).decode("utf-8")

        return {
            "data": data,
            "signature": signature,
            "checkout_url": "https://www.liqpay.ua/api/3/checkout"
        }


liqpay = LiqPayService()