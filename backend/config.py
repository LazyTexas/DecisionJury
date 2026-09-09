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

    # ===== JWT 配置 =====
    # 密钥：生产环境务必使用强随机字符串，建议通过环境变量注入
    SECRET_KEY = os.getenv("SECRET_KEY", "decision-jury-secret-key-change-in-production-2026")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))  # 默认 7 天

    # ===== JWT 强制模式开关 =====
    # False: 双模式兼容（有 Token 用 Token，无 Token 降级用 user_id）
    # True:  强制 JWT 模式（无 Token 或 Token 无效直接返回 401）
    # ENFORCE_JWT = os.getenv("ENFORCE_JWT", "false").lower() == "true"
    ENFORCE_JWT = True

    @classmethod
    def is_production(cls):
        return cls.ENV == "production"

    @classmethod
    def is_development(cls):
        return cls.ENV == "development"