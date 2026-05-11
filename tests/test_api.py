"""
FastAPI endpoint tests.
Run with: uv run pytest tests/test_api.py -v
Requires the server to NOT be running (uses TestClient).
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


def test_health_endpoint_structure():
    """Health endpoint should return required fields."""
    with patch("backend.api.routes.getHealth", return_value=None):
        from backend.main import app
        client = TestClient(app)
        # Just verify the endpoint responds — Ollama may not be running in CI
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ollama_reachable" in data
        assert "vector_store_ready" in data


def test_documents_endpoint():
    """Documents endpoint should list all knowledge base documents."""
    from backend.main import app
    client = TestClient(app)
    response = client.get("/api/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert data["total"] >= 6  # We have 6 documents
    titles = [d["title"] for d in data["documents"]]
    assert any("Budget" in t for t in titles)
    assert any("Rightsizing" in t for t in titles)
