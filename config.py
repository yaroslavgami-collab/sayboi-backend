
import os

PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")

BASE_URL = "https://sayboi-backend.onrender.com"

print("PUBLIC KEY:", bool(PUBLIC_KEY))
print("PRIVATE KEY:", bool(PRIVATE_KEY))
print("BASE URL:", BASE_URL)
