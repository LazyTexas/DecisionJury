import os
from dotenv import load_dotenv

# 项目根目录：backend/config.py → backend/ → 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

class Config:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_PROJECT_ROOT, 'data', 'decisionjury.db').replace(os.sep, '/')}"
    )
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")