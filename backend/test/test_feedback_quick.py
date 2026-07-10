# backend/test/test_feedback_quick.py
import sys
import os

# 将项目根目录添加到 Python 路径
# 当前文件在 backend/test/ 下，需要向上两级到达项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal
from backend.models import Case
from datetime import datetime

db = SessionLocal()

# 检查是否已存在
existing = db.query(Case).filter(Case.id == "case_feedback_test").first()
if not existing:
    case = Case(
        id="case_feedback_test",
        user_id="local_user",
        case_type="shopping",
        title="反馈测试-降噪耳机",
        description="测试反馈接口用",
        status="completed",
        final_decision="delay",
        report_id="report_feedback_test",
        debate_result={"report": {"final_decision": "delay", "confidence": 0.8}},
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(case)
    db.commit()
    print("[OK] 测试案件创建成功: case_feedback_test")
else:
    print("[INFO] 测试案件已存在")

db.close()

print("\n现在可以运行测试命令：")
print('curl -X POST http://127.0.0.1:8000/api/cases/case_feedback_test/feedback \\')
print('  -H "Content-Type: application/json" \\')
print('  -d \'{"user_id":"local_user","actual_action":"bought","satisfaction":4,"review":"测试反馈"}\'')