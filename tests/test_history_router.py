# tests/test_history_router.py
"""
测试 history 路由（GET /api/history, POST /api/history）
"""

from backend.models import History


def test_post_history_success(client, db_session):
    """创建历史记录成功"""
    response = client.post(
        "/api/history",
        json={
            "user_id": "u001",
            "case_type": "shopping",
            "summary": "购买降噪耳机，建议暂缓3天",
            "result": "neutral",
            "tags": ["electronics", "headphones"],
            "title": "索尼降噪耳机",
            "price": 1299,
            "usage_frequency": "daily",
            "context": "考研期间每天学习需要降噪",
            "pros": ["降噪效果很好"],
            "cons": ["价格偏高"],
            "final_decision": "delay",
            "case_id": "case_xxx",
            "report_id": "report_xxx"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "history_id" in data["data"]
    assert data["data"]["title"] == "索尼降噪耳机"
    assert data["data"]["price"] == 1299


def test_post_history_minimal(client, db_session):
    """最小字段创建历史记录"""
    response = client.post(
        "/api/history",
        json={
            "user_id": "u001",
            "case_type": "shopping",
            "summary": "购买耳机",
            "result": "worth"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["summary"] == "购买耳机"
    assert data["data"]["result"] == "worth"
    assert "history_id" in data["data"]


def test_post_history_missing_user_id(client):
    """缺少 user_id 返回验证错误"""
    response = client.post(
        "/api/history",
        json={
            "case_type": "shopping",
            "summary": "购买耳机",
            "result": "worth"
        }
    )

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "VALIDATION_ERROR"


def test_post_history_invalid_result(client):
    """无效的 result 值返回验证错误"""
    response = client.post(
        "/api/history",
        json={
            "user_id": "u001",
            "case_type": "shopping",
            "summary": "购买耳机",
            "result": "invalid_value"
        }
    )

    # Pydantic 验证应该返回 422
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False


def test_get_history_success(client, db_session):
    """查询历史记录列表成功"""
    # 创建测试数据
    history = History(
        id="hist_001",
        user_id="u001",
        case_type="shopping",
        summary="购买耳机",
        result="worth",
        tags=["electronics"],
        title="索尼耳机",
        price=1299,
        case_id="case_001"
    )
    db_session.add(history)
    db_session.commit()

    response = client.get("/api/history?user_id=u001")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] >= 1
    assert len(data["data"]["items"]) >= 1
    item = data["data"]["items"][0]
    assert item["history_id"] == "hist_001"
    assert item["title"] == "索尼耳机"
    assert item["case_type"] == "shopping"


def test_get_history_pagination(client, db_session):
    """分页参数生效"""
    # 创建 5 条测试数据
    for i in range(5):
        history = History(
            id=f"hist_{i:03d}",
            user_id="u002",
            case_type="shopping",
            summary=f"购买物品{i}",
            result="worth",
            tags=[]
        )
        db_session.add(history)
    db_session.commit()

    response = client.get("/api/history?user_id=u002&page=1&page_size=2")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 2
    assert len(data["data"]["items"]) == 2
    assert data["data"]["total"] == 5


def test_get_history_filter_by_result(client, db_session):
    """按 result 筛选"""
    history1 = History(
        id="hist_regret",
        user_id="u003",
        case_type="shopping",
        summary="后悔购买",
        result="regret",
        tags=[]
    )
    history2 = History(
        id="hist_worth",
        user_id="u003",
        case_type="shopping",
        summary="值得购买",
        result="worth",
        tags=[]
    )
    db_session.add(history1)
    db_session.add(history2)
    db_session.commit()

    response = client.get("/api/history?user_id=u003&result=regret")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["result"] == "regret"


def test_get_history_filter_by_case_type(client, db_session):
    """按 case_type 筛选"""
    history1 = History(
        id="hist_shopping",
        user_id="u004",
        case_type="shopping",
        summary="购物决策",
        result="worth",
        tags=[]
    )
    history2 = History(
        id="hist_time",
        user_id="u004",
        case_type="time",
        summary="时间决策",
        result="neutral",
        tags=[]
    )
    db_session.add(history1)
    db_session.add(history2)
    db_session.commit()

    response = client.get("/api/history?user_id=u004&case_type=shopping")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["case_type"] == "shopping"


def test_get_history_empty(client):
    """无数据用户返回空列表"""
    response = client.get("/api/history?user_id=u_empty")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 0
    assert data["data"]["items"] == []


def test_get_history_missing_user_id(client):
    """缺少 user_id 返回验证错误"""
    response = client.get("/api/history")

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["message"] == "VALIDATION_ERROR"


def test_get_history_sorted_by_created_at(client, db_session):
    """按 created_at 倒序排列"""
    import datetime
    # 创建两条不同时间的数据
    history1 = History(
        id="hist_old",
        user_id="u005",
        case_type="shopping",
        summary="旧记录",
        result="regret",
        tags=[],
        created_at=datetime.datetime.now() - datetime.timedelta(days=10)
    )
    history2 = History(
        id="hist_new",
        user_id="u005",
        case_type="shopping",
        summary="新记录",
        result="worth",
        tags=[]
    )
    db_session.add(history1)
    db_session.add(history2)
    db_session.commit()

    response = client.get("/api/history?user_id=u005")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # 最新记录应该在第一个
    assert data["data"]["items"][0]["history_id"] == "hist_new"