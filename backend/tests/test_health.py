"""Unit test for FastAPI Health Check Endpoint."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns project metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "QueryMind AI 2.0"
    assert data["status"] == "online"


def test_health_check_endpoint():
    """Verify /api/health endpoint returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "QueryMind AI 2.0"
    assert "version" in data

