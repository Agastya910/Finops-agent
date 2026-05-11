"""
FinOps tools backed by deterministic, simulated internal cloud-spend data.

All tools read from `backend.data.company_spend` — no external API calls.
Spend records and benchmarks are grounded in FinOps Foundation 2025 and
Flexera 2025 State of the Cloud public reports.
"""
import json
import statistics
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from langchain_core.tools import tool

from ..core.logging import logger
from ..data.company_spend import (
    INDUSTRY_BENCHMARKS,
    REFERENCE_DATE,
    SPEND_RECORDS,
    TEAM_BUDGETS,
)


_SOURCES_NOTE = (
    "FinOps Foundation 2025 State of FinOps Report; "
    "Flexera 2025 State of the Cloud Report"
)


def _norm(name: str) -> str:
    return name.lower().replace("_", "-").replace(" ", "-").strip()


def _filter_by_service(service: str) -> List[Dict]:
    q = _norm(service).replace("-", "")
    matches: List[Dict] = []
    for r in SPEND_RECORDS:
        s = _norm(r["service"]).replace("-", "")
        if q == s or q in s or s in q:
            matches.append(r)
    return matches


def _quarter_bounds(quarter_str: Optional[str]) -> Tuple[date, date, str]:
    if quarter_str:
        try:
            q_part, y_part = quarter_str.upper().replace(" ", "").split("-")
            q_num = int(q_part.lstrip("Q"))
            year = int(y_part)
        except Exception:
            q_num = ((REFERENCE_DATE.month - 1) // 3) + 1
            year = REFERENCE_DATE.year
    else:
        q_num = ((REFERENCE_DATE.month - 1) // 3) + 1
        year = REFERENCE_DATE.year
    start_month = (q_num - 1) * 3 + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    if end_month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, end_month + 1, 1) - timedelta(days=1)
    return start, end, f"Q{q_num}-{year}"


def _total_monthly_spend(reference: date = REFERENCE_DATE) -> float:
    start = reference - timedelta(days=30)
    total = 0.0
    for r in SPEND_RECORDS:
        d = date.fromisoformat(r["date"])
        if start <= d <= reference:
            total += r["spend_usd"]
    return round(total, 2)


@tool
async def get_service_spend(service: str, days: int = 30) -> str:
    """
    Retrieve recent internal spend trend for a cloud service or cost center.
    Reads from the company's own simulated spend ledger.

    Args:
        service: Cloud service name (e.g. ml-training, data-pipeline, storage, compute)
        days: Days of history to retrieve (default 30, max 90)
    """
    days = min(max(days, 7), 90)
    try:
        rows = _filter_by_service(service)
        if not rows:
            return json.dumps({"error": "No records for service", "service": service})
        rows.sort(key=lambda r: r["date"])
        rows = rows[-days:]
        values = [r["spend_usd"] for r in rows]
        avg = statistics.mean(values)
        latest = values[-1]
        pct = round(((latest - avg) / avg) * 100, 1) if avg else 0.0
        series = [{"date": r["date"], "spend_usd": r["spend_usd"]} for r in rows[-7:]]
        return json.dumps({
            "service": service,
            "currency": "USD",
            "period_days": len(values),
            "latest_daily_spend": round(latest, 2),
            "period_average": round(avg, 2),
            "pct_change_vs_average": pct,
            "trend": "above average" if pct > 5 else ("below average" if pct < -5 else "stable"),
            "series": series,
            "data_source": "internal-spend-ledger",
        })
    except Exception as e:
        logger.error(f"get_service_spend error: {e}")
        return json.dumps({"error": str(e), "service": service})


@tool
async def detect_spend_anomaly(service: str, sensitivity: str = "medium") -> str:
    """
    Run Z-score anomaly detection on a service's spend trend.
    Flags days where spend deviates significantly from the rolling baseline.

    Args:
        service: Cloud service name to analyze
        sensitivity: Detection sensitivity - low (z>3), medium (z>2), high (z>1.5)
    """
    z_threshold = {"low": 3.0, "medium": 2.0, "high": 1.5}.get(sensitivity, 2.0)
    try:
        rows = _filter_by_service(service)
        if not rows:
            return json.dumps({"error": "No records for service", "service": service})
        rows.sort(key=lambda r: r["date"])
        rows = rows[-60:]
        values = [r["spend_usd"] for r in rows]
        dates = [r["date"] for r in rows]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0.0
        anomalies = []
        for d, val in zip(dates, values):
            z = abs((val - mean) / stdev) if stdev > 0 else 0.0
            if z > z_threshold:
                anomalies.append({
                    "date": d,
                    "spend_usd": round(val, 2),
                    "z_score": round(z, 2),
                    "deviation_pct": round(((val - mean) / mean) * 100, 1) if mean else 0.0,
                    "direction": "OVERSPEND" if val > mean else "UNDERSPEND",
                })
        return json.dumps({
            "service": service,
            "analysis_period_days": len(values),
            "baseline_mean_usd": round(mean, 2),
            "baseline_stdev_usd": round(stdev, 2),
            "z_threshold": z_threshold,
            "anomaly_count": len(anomalies),
            "anomalies": sorted(anomalies, key=lambda x: abs(x["z_score"]), reverse=True)[:5],
            "verdict": "Anomalies detected" if anomalies else "Spend within normal range",
            "data_source": "internal-spend-ledger",
        })
    except Exception as e:
        logger.error(f"detect_spend_anomaly error: {e}")
        return json.dumps({"error": str(e), "service": service})


@tool
async def get_budget_vs_actual(team: str, quarter: Optional[str] = None) -> str:
    """
    Compare a team's actual cloud spend against allocated budget for the quarter.

    Args:
        team: Team or cost-center name (e.g. ml-platform, data-engineering, backend-services)
        quarter: Quarter string like Q1-2026. Defaults to the current quarter.
    """
    t = _norm(team)
    budget_cfg = TEAM_BUDGETS.get(t)
    if not budget_cfg:
        for key, val in TEAM_BUDGETS.items():
            if _norm(key).replace("-", "") == t.replace("-", ""):
                budget_cfg = val
                t = key
                break
    if not budget_cfg:
        return json.dumps({
            "error": f"Unknown team '{team}'. Known teams: {list(TEAM_BUDGETS)}",
            "team": team,
        })
    try:
        q_start, q_end, q_label = _quarter_bounds(quarter)
        actual = 0.0
        for r in SPEND_RECORDS:
            if r["team"] != t:
                continue
            d = date.fromisoformat(r["date"])
            if q_start <= d <= q_end:
                actual += r["spend_usd"]
        actual = round(actual, 2)
        budget = budget_cfg["quarter_usd"]
        variance = round(actual - budget, 2)
        utilization = round((actual / budget) * 100, 1) if budget else 0.0
        mid_market_monthly = INDUSTRY_BENCHMARKS["monthly_by_company_size"]["mid_200_employees"]
        mid_market_quarter = mid_market_monthly * 3
        return json.dumps({
            "team": t,
            "quarter": q_label,
            "quarter_start": q_start.isoformat(),
            "quarter_end": q_end.isoformat(),
            "budget_usd": budget,
            "actual_spend_usd": actual,
            "variance_usd": variance,
            "utilization_pct": utilization,
            "status": "OVER BUDGET" if variance > 0 else "UNDER BUDGET",
            "industry_benchmark": {
                "mid_market_monthly_usd": mid_market_monthly,
                "mid_market_quarterly_usd": mid_market_quarter,
                "ratio_vs_benchmark": round(actual / mid_market_quarter, 2) if mid_market_quarter else 0.0,
                "source": _SOURCES_NOTE,
            },
            "recommendation": (
                f"Reduce {t} spend by ${abs(variance):,.0f}" if variance > 0
                else f"{t} has ${abs(variance):,.0f} remaining budget headroom"
            ),
            "data_source": "internal-spend-ledger",
        })
    except Exception as e:
        logger.error(f"get_budget_vs_actual error: {e}")
        return json.dumps({"error": str(e), "team": team})


@tool
async def get_rightsizing_recommendations(service: str) -> str:
    """
    Analyze a cloud service's utilization proxy and recommend rightsizing to reduce cost.

    Args:
        service: The cloud service or workload to analyze
    """
    try:
        rows = _filter_by_service(service)
        if not rows:
            return json.dumps({"error": "No records for service", "service": service})
        rows.sort(key=lambda r: r["date"])
        values = [r["spend_usd"] for r in rows[-30:]]
        avg = statistics.mean(values)
        sorted_vals = sorted(values)
        p95_index = max(0, int(len(sorted_vals) * 0.95) - 1)
        theoretical_max = sorted_vals[p95_index] if sorted_vals else 0.0
        utilization = round((avg / theoretical_max) * 100, 0) if theoretical_max > 0 else 50.0
        utilization = float(min(max(utilization, 10.0), 95.0))
        monthly_cost = round(avg * 30, 2)

        resource_type = rows[-1].get("resource_type", "compute")
        category_waste = INDUSTRY_BENCHMARKS["service_waste_by_category"].get(resource_type, 27)

        if utilization < 40:
            action, savings_pct = "DOWNSIZE", 40
            detail = (
                f"Downsize to next smaller tier — utilization at {utilization:.0f}% "
                f"indicates over-provisioning."
            )
        elif utilization > 80:
            action, savings_pct = "OPTIMIZE_SCHEDULING", 15
            detail = (
                f"Adopt auto-scaling and spot/preemptible instances — utilization at "
                f"{utilization:.0f}% leaves limited headroom but spiky load can be shifted."
            )
        else:
            action, savings_pct = "RESERVE_CAPACITY", 30
            detail = (
                f"Switch on-demand to reserved/committed-use — steady {utilization:.0f}% "
                f"utilization justifies a 1-year commitment."
            )

        return json.dumps({
            "service": service,
            "resource_type": resource_type,
            "current_avg_daily_spend_usd": round(avg, 2),
            "current_monthly_cost_usd": monthly_cost,
            "estimated_utilization_pct": utilization,
            "recommendation_action": action,
            "recommendation_detail": detail,
            "estimated_monthly_savings_usd": round(monthly_cost * savings_pct / 100, 2),
            "savings_pct": savings_pct,
            "industry_benchmark": (
                f"{resource_type.capitalize()} waste averages {category_waste}% of spend "
                f"industry-wide (Flexera 2025)."
            ),
            "data_source": "internal-spend-ledger",
        })
    except Exception as e:
        logger.error(f"get_rightsizing_recommendations error: {e}")
        return json.dumps({"error": str(e), "service": service})


@tool
def flag_cost_alert(service: str, severity: str, message: str, estimated_monthly_impact_usd: float) -> str:
    """
    Create a cost alert record for a detected anomaly or policy violation.

    Args:
        service: Service or team name triggering the alert
        severity: Alert severity - critical, high, medium, low
        message: Human-readable description of the issue
        estimated_monthly_impact_usd: Estimated monthly cost impact in USD
    """
    alert_id = f"ALERT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{service[:6].upper()}"
    severity_upper = severity.upper()
    emoji = {"CRITICAL": "🚨", "HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity_upper, "⚪")
    alert = {
        "alert_id": alert_id, "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": service, "severity": severity_upper, "severity_indicator": emoji,
        "message": message, "estimated_monthly_impact_usd": round(estimated_monthly_impact_usd, 2),
        "status": "OPEN",
        "actions_required": [
            "Review spend breakdown in FinOps dashboard",
            "Notify team owner within 24h" if severity_upper in ("HIGH", "CRITICAL") else "Schedule review in next sprint",
            "Apply rightsizing recommendation if confirmed",
        ],
        "integration_note": "In production: this fires a Slack webhook and PagerDuty incident",
    }
    logger.info(f"Cost alert created: {alert_id} [{severity_upper}] for {service}")
    return json.dumps(alert)


@tool
async def get_market_benchmark(benchmark: str = "cloud-infrastructure") -> str:
    """
    Return industry cloud-spend benchmarks and compare against the company's
    current monthly spend. Sourced from FinOps Foundation 2025 and Flexera 2025.

    Args:
        benchmark: Benchmark category - cloud-infrastructure, ai-compute, storage, networking
    """
    try:
        sizes = INDUSTRY_BENCHMARKS["monthly_spend_by_company_size_usd"]
        mid_market = sizes["mid_51_200"]
        company_monthly = _total_monthly_spend()
        ratio = round(company_monthly / mid_market, 2) if mid_market else 0.0
        if ratio > 1.10:
            position = "above"
        elif ratio < 0.90:
            position = "below"
        else:
            position = "at"

        waste_pct = INDUSTRY_BENCHMARKS["cloud_waste_pct"]
        category_waste = INDUSTRY_BENCHMARKS["waste_by_resource_pct"]
        waste_estimate = round(company_monthly * waste_pct / 100, 0)
        gpu_idle = INDUSTRY_BENCHMARKS["gpu_idle_waste_pct_typical"]
        ri_target = INDUSTRY_BENCHMARKS["reserved_coverage_target_pct"]

        interpretation = (
            f"Based on the Flexera 2025 State of the Cloud Report (750+ organizations): "
            f"the average mid-market company (51–200 employees) spends ${mid_market:,}/month "
            f"on cloud infrastructure. Your current monthly spend of ${company_monthly:,.0f} "
            f"is {ratio}x the benchmark ({position} benchmark). "
            f"Industry cloud waste averages {waste_pct}% (Flexera 2025, confirmed by "
            f"Harness 2025 and Datadog 2024). Your estimated recoverable waste is "
            f"${waste_estimate:,.0f}/month. "
            f"GPU idle waste typically runs {gpu_idle}% of GPU budgets for organizations "
            f"without active rightsizing programs (Mirantis 2025). "
            f"FinOps Foundation State of FinOps 2025 recommends {ri_target}% reserved "
            f"instance coverage for steady-state compute as the cost-optimal target."
        )

        return json.dumps({
            "benchmark": benchmark,
            "company_monthly_spend_usd": company_monthly,
            "industry_monthly_by_size_usd": sizes,
            "mid_market_reference_usd": mid_market,
            "ratio_vs_mid_market": ratio,
            "position_vs_benchmark": position,
            "industry_cloud_waste_pct": waste_pct,
            "estimated_recoverable_waste_usd": waste_estimate,
            "waste_by_resource_pct": category_waste,
            "gpu_idle_waste_pct_typical": gpu_idle,
            "gpu_utilization_rightsizing_threshold_pct": INDUSTRY_BENCHMARKS["gpu_utilization_rightsizing_threshold"],
            "reserved_coverage_target_pct": ri_target,
            "avg_budget_overage_pct": INDUSTRY_BENCHMARKS["avg_budget_overage_pct"],
            "saas_revenue_pct_range": INDUSTRY_BENCHMARKS["infra_as_pct_of_revenue"],
            "interpretation": interpretation,
            "sources": INDUSTRY_BENCHMARKS["_sources"],
            "data_source": "industry-benchmark-tables",
        })
    except Exception as e:
        logger.error(f"get_market_benchmark error: {e}")
        return json.dumps({"error": str(e), "benchmark": benchmark})


ALL_TOOLS = [
    get_service_spend, detect_spend_anomaly, get_budget_vs_actual,
    get_rightsizing_recommendations, flag_cost_alert, get_market_benchmark,
]
