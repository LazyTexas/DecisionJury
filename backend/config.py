# backend/config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Config:
    ENV = os.getenv("ENV", "development")  # development / production
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/decisionjury.db")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    @classmethod
    def is_production(cls):
        return cls.ENV == "production"

    @classmethod
    def is_development(cls):
        return cls.ENV == "development"