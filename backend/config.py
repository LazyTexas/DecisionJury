# backend/config.py
import os
from dotenv import load_dotenv


# 项目根目录：backend/config.py → backend/ → 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件
load_dotenv()


class Config:
    ENV = os.getenv("ENV", "development")  # development / production
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'decisionjury.db').replace(os.sep, '/')}"
    )
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    @classmethod
    def is_production(cls):
        return cls.ENV == "production"

    @classmethod
    def is_development(cls):
        return cls.ENV == "development"