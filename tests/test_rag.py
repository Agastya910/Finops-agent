"""
RAG store tests — tests the hybrid retrieval logic.
"""
import pytest
from backend.rag.documents import FINOPS_DOCUMENTS


def test_documents_have_required_fields():
    """All documents must have id, title, category, content."""
    for doc in FINOPS_DOCUMENTS:
        assert "id" in doc, f"Document missing id: {doc}"
        assert "title" in doc
        assert "category" in doc
        assert "content" in doc
        assert len(doc["content"]) > 100, f"Document content too short: {doc['id']}"


def test_document_categories():
    """Documents should be in expected categories."""
    valid_categories = {"policy", "playbook", "guide"}
    for doc in FINOPS_DOCUMENTS:
        assert doc["category"] in valid_categories, f"Invalid category in {doc['id']}: {doc['category']}"


def test_policy_documents_exist():
    """At least 3 policy documents should exist."""
    policies = [d for d in FINOPS_DOCUMENTS if d["category"] == "policy"]
    assert len(policies) >= 3
