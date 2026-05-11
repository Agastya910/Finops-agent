"""
Integration tests for FinOps tools.
Run with: uv run pytest tests/ -v
"""
import json

import pytest

from backend.tools.finance_tools import (
    detect_spend_anomaly,
    flag_cost_alert,
    get_budget_vs_actual,
    get_market_benchmark,
    get_rightsizing_recommendations,
    get_service_spend,
)


@pytest.mark.asyncio
async def test_get_service_spend_returns_valid_structure():
    """get_service_spend should return valid JSON with required keys."""
    result = await get_service_spend.ainvoke({"service": "ml-training", "days": 7})
    data = json.loads(result)
    assert "service" in data
    assert "latest_daily_spend" in data
    assert "period_average" in data


@pytest.mark.asyncio
async def test_detect_spend_anomaly_z_score():
    """detect_spend_anomaly should return z_threshold and anomaly verdict."""
    result = await detect_spend_anomaly.ainvoke({"service": "data-pipeline", "sensitivity": "medium"})
    data = json.loads(result)
    assert "z_threshold" in data
    assert data["z_threshold"] == 2.0
    assert "anomaly_count" in data


@pytest.mark.asyncio
async def test_budget_vs_actual_structure():
    """get_budget_vs_actual should return budget and actual spend."""
    result = await get_budget_vs_actual.ainvoke({"team": "ml-platform"})
    data = json.loads(result)
    assert "team" in data
    assert "budget_usd" in data
    assert "actual_spend_usd" in data


def test_flag_cost_alert_creates_alert_id():
    """flag_cost_alert should always return a valid alert record."""
    result = flag_cost_alert.invoke({
        "service": "test-service",
        "severity": "high",
        "message": "Test anomaly detected",
        "estimated_monthly_impact_usd": 5000.0,
    })
    data = json.loads(result)
    assert "alert_id" in data
    assert data["alert_id"].startswith("ALERT-")
    assert data["severity"] == "HIGH"
    assert data["status"] == "OPEN"


@pytest.mark.asyncio
async def test_rightsizing_returns_recommendation():
    """get_rightsizing_recommendations should return a specific action."""
    result = await get_rightsizing_recommendations.ainvoke({"service": "compute"})
    data = json.loads(result)
    assert "recommendation_action" in data
    assert data["recommendation_action"] in ["DOWNSIZE", "OPTIMIZE_SCHEDULING", "RESERVE_CAPACITY"]


@pytest.mark.asyncio
async def test_market_benchmark_returns_industry_data():
    """get_market_benchmark should return industry benchmark comparison."""
    result = await get_market_benchmark.ainvoke({"benchmark": "cloud-infrastructure"})
    data = json.loads(result)
    assert "mid_market_reference_usd" in data
    assert "company_monthly_spend_usd" in data
    assert "industry_cloud_waste_pct" in data
