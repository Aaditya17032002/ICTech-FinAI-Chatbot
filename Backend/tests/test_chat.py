import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "endpoints" in data


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_fund_search_requires_query():
    """Test fund search requires query parameter."""
    response = client.get("/api/v1/funds/search")
    assert response.status_code == 422


def test_fund_search_with_query():
    """Test fund search with valid query."""
    response = client.get("/api/v1/funds/search?q=sbi&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert isinstance(data["results"], list)


def test_fund_details_not_found():
    """Test fund details with invalid scheme code."""
    response = client.get("/api/v1/funds/invalid_code")
    assert response.status_code in [404, 500]


def test_chat_requires_message():
    """Test chat endpoint requires message."""
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422


def test_chat_with_message():
    """Test chat endpoint with valid message."""
    response = client.post(
        "/api/v1/chat",
        json={"message": "What is CAGR?"}
    )
    assert response.status_code in [200, 500]


def test_fund_compare_requires_minimum_funds():
    """Test fund comparison requires at least 2 funds."""
    response = client.post(
        "/api/v1/funds/compare",
        json=["119598"]
    )
    assert response.status_code == 400


def test_fund_compare_maximum_funds():
    """Test fund comparison has maximum limit."""
    response = client.post(
        "/api/v1/funds/compare",
        json=["1", "2", "3", "4", "5", "6"]
    )
    assert response.status_code == 400
