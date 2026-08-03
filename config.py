import os


# =========================
# LiqPay
# =========================

PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")


# =========================
# Backend
# =========================

BASE_URL = "https://sayboi-backend.onrender.com"


# =========================
# Проверка настроек
# =========================

if not PUBLIC_KEY:
    raise RuntimeError("LIQPAY_PUBLIC_KEY is not set")

if not PRIVATE_KEY:
    raise RuntimeError("LIQPAY_PRIVATE_KEY is not set")
