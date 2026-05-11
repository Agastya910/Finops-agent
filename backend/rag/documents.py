"""
FinOps knowledge base — 6 structured policy and guide documents.
These form the RAG corpus. In production, load from S3/GCS or a doc store.
"""

FINOPS_DOCUMENTS = [
    {
        "id": "policy-budget-thresholds",
        "title": "FinOps Budget Threshold Policy v2.1",
        "category": "policy",
        "content": """
# FinOps Budget Threshold Policy v2.1

## 1. Purpose
This policy defines budget thresholds, alert triggers, and escalation procedures
for all cloud cost centers.

## 2. Budget Alert Tiers
- Green Zone (0-80%): No action. Monthly report only.
- Yellow Zone (80-100%): Team lead notified. Weekly review.
- Red Zone (100-120%): Director escalation. Spend freeze on non-critical resources.
- Critical Zone (>120%): CTO notification. Immediate budget review meeting.

## 3. Per-Team Monthly Budget Caps
| Team | Monthly Budget | Spike Tolerance |
|------|---------------|-----------------|
| ML Platform | $45,000 | +15% for max 3 days |
| Data Engineering | $28,000 | +10% for max 5 days |
| Backend Services | $32,000 | +20% for max 2 days |
| DevOps | $15,000 | +10% for max 3 days |
| Security | $12,000 | +5% (no tolerance) |
| Analytics | $20,000 | +15% for max 5 days |

## 4. Anomaly Detection Rules
- Any service showing >2 standard deviations from 30-day rolling average triggers review.
- Daily spend increase >30% day-over-day requires same-day investigation.
- Sustained overspend (5+ consecutive days above 110%) requires rightsizing action plan within 48h.

## 5. Approval Process for Budget Exceptions
1. Team lead submits exception request with business justification.
2. FinOps team reviews within 24 business hours.
3. VP Engineering signs off on exceptions >$5,000/month.
4. CFO approval required for exceptions >$20,000/month.

## 6. Rightsizing Mandate
All teams must review and act on rightsizing recommendations within 30 days of receipt.
Non-compliance results in forced automated rightsizing.
        """,
    },
    {
        "id": "policy-cost-allocation",
        "title": "Cloud Cost Allocation & Tagging Standards",
        "category": "policy",
        "content": """
# Cloud Cost Allocation & Tagging Standards

## 1. Mandatory Resource Tags
Every cloud resource must carry:
- team: owning team slug (e.g., ml-platform, data-engineering)
- environment: prod | staging | dev | sandbox
- project: project or initiative identifier
- cost-center: finance cost center code

## 2. Untagged Resource Policy
- Untagged resources auto-tagged to team: unallocated and billed to overhead.
- Resources untagged >7 days receive automated deletion warning.
- Persistent untagged resources (>14 days) terminated in non-production.

## 3. Shared Infrastructure Allocation
- 40% split equally across all teams.
- 60% split proportionally by compute consumption.

## 4. Chargeback Model
- Monthly chargeback reports sent to each team's engineering manager by the 5th.
- Disputes must be raised within 10 business days.
- Chargebacks feed directly into the P&L for each product line.
        """,
    },
    {
        "id": "playbook-anomaly-response",
        "title": "Cost Anomaly Response Playbook",
        "category": "playbook",
        "content": """
# Cost Anomaly Response Playbook

## Trigger Conditions
This playbook activates when:
- Z-score of daily spend exceeds 2.0 (medium sensitivity)
- Day-over-day spend increase exceeds 30%
- Monthly budget utilization exceeds 100%

## Step 1: Classify the Anomaly
1a. Sudden Spike (single day >3x average)
- Likely cause: accidental large batch job, misconfigured auto-scaler
- Action: Check running jobs, verify no infinite loops in ETL
- Resolution: Same day

1b. Gradual Drift (slow increase over 2+ weeks)
- Likely cause: growing data volume, new feature rollout
- Action: Compare resource count week-over-week, review recent deployments
- Resolution: Within 1 week

1c. Recurrent Pattern (spikes on specific days)
- Likely cause: scheduled batch jobs, weekly reports
- Action: Tag jobs as expected, update baseline model
- Resolution: 2-3 days

## Step 2: Assign Ownership
- Check the team tag on anomalous resources.
- If untagged: assign to FinOps team for investigation.
- Notify team lead via Slack #finops-alerts.

## Step 3: Root Cause Analysis
1. Pull 30-day spend history.
2. Identify resource type driving the spike (compute vs storage vs data transfer).
3. Cross-reference with deployment history and incident log.
4. Check cloud provider status page for pricing changes.

## Step 4: Remediation
- Over-provisioned compute: Apply rightsizing recommendation immediately.
- Runaway batch job: Kill job, fix parameters, re-run with resource limits.
- Data transfer spike: Review cross-region traffic.
- Storage growth: Archive or delete stale data.

## Step 5: Prevention
- Add resource quotas to the team's namespace.
- Set up auto-scaling max limits.
- Add cost-aware CI/CD checks.
        """,
    },
    {
        "id": "guide-rightsizing",
        "title": "Cloud Rightsizing Decision Guide",
        "category": "guide",
        "content": """
# Cloud Rightsizing Decision Guide

## CPU-Bound Workloads
- <20% avg CPU: Downsize by 2 tiers immediately.
- 20-60% avg CPU: Downsize by 1 tier, monitor for 1 week.
- 60-80% avg CPU: Current sizing appropriate, consider reserved instances.
- >80% avg CPU: Scale-out (horizontal) rather than scale-up.

## Memory-Bound Workloads
- <25% avg memory: Downsize by 1-2 tiers.
- 25-70% avg memory: Optimal range, no action.
- >70% avg memory: Monitor closely, plan increase before 90%.

## ML Training Workloads (GPU)
- GPU utilization <60%: Spot/preemptible instances (70% cost savings).
- GPU utilization 60-85%: Reserved GPU instances (30% savings).
- GPU utilization >85%: Evaluate distributed training.

## Storage Workloads
- Access frequency <1x/week: Cold/archive storage (80% savings).
- Access frequency 1x/week to 1x/day: Infrequent access tier (40% savings).
- Access frequency >1x/day: Standard storage tier.

## Savings Plan vs Reserved Instance
| Commitment | Discount | Best For |
|------------|----------|---------|
| 1-year Reserved | 30-40% | Stable, predictable workloads |
| 3-year Reserved | 50-60% | Core infra with 3yr roadmap |
| Compute Savings Plan | 20-30% | Mixed workloads |
| Spot Instances | 60-90% | Batch jobs, CI/CD, fault-tolerant |
        """,
    },
    {
        "id": "guide-finops-kpis",
        "title": "FinOps KPIs & Success Metrics",
        "category": "guide",
        "content": """
# FinOps KPIs & Success Metrics

## Unit Economics
- Cloud Cost per Unit Revenue: cloud spend / revenue (target: <8%).
- Cost per Active User: cloud spend / MAU.
- Compute Efficiency Ratio: useful compute / total purchased.

## Waste Reduction
- Idle Resource Ratio: % resources with <5% utilization for >7 days (target: <5%).
- Rightsizing Coverage: % workloads reviewed in last 30 days (target: >80%).
- Reserved Coverage: % steady-state compute with commitments (target: >60%).

## Budget Health
- Budget Adherence Rate: teams finishing within +/-10% of budget (target: >85%).
- Forecast Accuracy: predicted vs actual variance (target: <10% monthly).
- Tagging Compliance: % resources with all mandatory tags (target: >95%).

## Anomaly Response
- Mean Time to Detect (MTTD): time from anomaly to detection (target: <4h).
- Mean Time to Resolve (MTTR): time from detection to resolution (target: <24h).
- False Positive Rate: % flagged anomalies that were benign (target: <15%).
        """,
    },
    {
        "id": "policy-ml-platform",
        "title": "ML Platform Cost Governance Policy",
        "category": "policy",
        "content": """
# ML Platform Cost Governance Policy

## 1. Training Job Resource Limits
All ML training jobs must specify resource limits:
- Max GPU hours per job: 72 hours
- Max CPU per job: 64 vCPUs
- Max memory per job: 256 GB
- Max storage per job: 5 TB

Jobs exceeding these limits require VP of ML approval.

## 2. Experiment Cost Budgets
- Each experiment: $500 maximum cost budget by default.
- Experiments auto-terminate at budget limit.
- Production model training budget: $5,000 per training run.
- Hyperparameter search: maximum $2,000 per sweep.

## 3. GPU Instance Policy
- Development: CPU or T4 instances only.
- Prototyping: A100/H100 allowed for <4h, then requires justification.
- Production training: Reserved H100 instances via ML Platform allocation.
- Inference serving: Quantized models on CPU/T4 where latency SLAs permit.

## 4. Model Storage & Artifact Policy
- Model checkpoints: 30-day retention, then archived to cold storage.
- Final production models: 12-month standard storage retention.
- Experiment artifacts: 7-day retention unless explicitly tagged as important.
- Large datasets (>1TB): Stored in designated data lake with lifecycle policies.
        """,
    },
]
