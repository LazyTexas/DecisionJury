# tests/test_health_router.py
"""测试健康检查接口"""


def test_health_check(client):
    """GET /api/health 返回正常状态"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"
    assert "version" in data["data"]
    assert data["message"] == ""


def test_health_check_response_structure(client):
    """健康检查响应结构完整"""
    response = client.get("/api/health")
    data = response.json()
    assert "success" in data
    assert "data" in data
    assert "message" in data
    assert "status" in data["data"]
    assert "version" in data["data"]