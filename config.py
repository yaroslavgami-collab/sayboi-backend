
import os
from dotenv import load_dotenv

load_dotenv()

PUBLIC_KEY = os.getenv("PUBLIC_KEY")

PRIVATE_KEY = os.getenv("PRIVATE_KEY")

BASE_URL = os.getenv("BASE_URL")