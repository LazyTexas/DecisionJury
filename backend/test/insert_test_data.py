# insert_test_data.py
# 此测试文件用于测试GET /api/watchlist接口
import sys
import os

# 将项目根目录添加到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal
from backend.models import Reminder
from datetime import datetime

db = SessionLocal()

# 检查是否已存在测试数据
existing = db.query(Reminder).filter(Reminder.id == "reminder_test").first()
if existing:
    print("[WARN] 测试数据已存在，跳过插入")
else:
    reminder = Reminder(
        id="reminder_test",
        user_id="local_user",
        case_id="case_test",
        title="降噪耳机",
        reason="预算占比较高，建议冷静3天",
        due_at=datetime(2026, 7, 15, 10, 0, 0),
        status="waiting"
    )
    db.add(reminder)
    db.commit()
    print("[OK] 测试数据插入成功！")

db.close()