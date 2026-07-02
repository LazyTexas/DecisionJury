import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/decisionjury.db")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")