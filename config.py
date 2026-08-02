
import os
from dotenv import load_dotenv

load_dotenv()

import os

PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")

BASE_URL = "https://sayboi-backend.onrender.com"
