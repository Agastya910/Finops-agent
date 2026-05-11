# DESIGN.md — FinOps Advisory Agent

## What Is This?

A conversational AI agent that answers questions about cloud spending. You type a question like *"Is the ML Platform team over budget?"* and the agent does three things automatically: it looks up the relevant cost policy from a knowledge base, runs analysis against the company's real internal spend ledger, and returns a specific, actionable answer with dollar amounts, Z-scores, and next steps grounded in published industry benchmarks.

***

## System Map — What Sits on Top of What

```
Browser (React + Vite)
        │  HTTP /api/*
        ▼
FastAPI  ← pydantic-settings config, structured logging
        │
        ▼
LangGraph StateGraph  ←── the "brain"
   │
   ├─ Node 1: decide_retrieval   (Self-RAG)
   ├─ Node 2: retrieve_context   (HyDE + Qdrant + BM25 → RRF)
   ├─ Node 3: agent_reason       (ChatOllama with tools bound)
   ├─ Node 4: tools              (LangGraph ToolNode)
   └─ Node 5: corag_followup     (CoRAG second hop)
        │
        ├── Ollama  ──────────────────── runs the LLM locally or via cloud
        │     ├── qwen2.5:7b            chat / reasoning
        │     └── all-MiniLM-L6-v2      embeddings (384-dim, fastembed local)
        │
        └── Qdrant ───────────────────── vector store
              └── collection: finops_knowledge
                    ├── Dense vectors (cosine, 384-dim)
                    └── In-memory BM25 index (rank_bm25)

backend/data/company_spend.py  ←── deterministic 90-day internal spend ledger
   ├── SPEND_RECORDS             810 daily records across 9 services (seed=42)
   ├── TEAM_BUDGETS              monthly + quarterly caps per team
   └── INDUSTRY_BENCHMARKS       sourced from Flexera 2025, SpendArk 2026,
                                 FinOps Foundation 2025, Cast AI 2025,
                                 Mirantis 2025, Harness 2025
```

No external HTTP calls are made from any tool. The only outbound network
dependency is Ollama (local by default, optional Ollama Cloud via env var).

***

## Algorithms & Research Papers

| Algorithm | Paper | Venue | How It Is Used Here |
|-----------|-------|-------|---------------------|
| **ReAct** | Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* | ICLR 2023 | The core agent loop: reason → call a tool → observe the result → reason again. Implemented as a LangGraph cycle through `agent_reason → tools → corag_followup → agent_reason`. |
| **Self-RAG** | Asai et al., *Self-RAG: Learning to Retrieve, Generate, and Critique* | ICLR 2024 | `decide_retrieval` node: the agent reflects on the query type before retrieval. Pure data questions skip RAG entirely (saving ~400 ms). Policy questions trigger full retrieval. |
| **HyDE** | Gao et al., *Precise Zero-Shot Dense Retrieval without Relevance Labels* | ACL 2023 | `retrieve_context` node: before embedding the user's query, the LLM generates a *hypothetical* policy answer. That answer is embedded instead. Closes the semantic gap between short queries and long policy documents. |
| **CRAG / RRF** | Yan et al., *Corrective Retrieval Augmented Generation* | ICLR 2024 | `store.py` hybrid search: dense cosine scores from Qdrant and BM25 keyword scores are merged using Reciprocal Rank Fusion (k=60). Policy documents contain exact dollar thresholds that keyword search handles better than vectors alone. |
| **CoRAG** | *Chain-of-RAG: Iterative Retrieval for Multi-Hop Reasoning* | NeurIPS 2025 | `corag_followup` node: after tool results reveal an anomaly or over-budget signal, a second retrieval hop fetches the anomaly response playbook. Max 2 hops to bound latency. |

***

## The Qdrant Collection

### Why Pre-Created (Not Fetched at Runtime)

The six policy documents in `backend/rag/documents.py` are the **ground truth** for this agent. They are intentionally baked into the codebase rather than loaded from an external store because:

1. The agent must give consistent, auditable policy answers — not answers that drift as external docs change.
2. Zero external dependencies at startup — the agent works offline the moment Ollama is available.
3. The knowledge base is small enough (6 documents, ~4,000 words total) that in-memory Qdrant handles it completely.

In production at scale, swap `documents.py` for a loader that pulls from S3 or Confluence, then call `/api/index/rebuild` to re-index.

### Collection Schema

**Collection name:** `finops_knowledge`

```
create_collection(
    collection_name = "finops_knowledge",
    vectors_config  = VectorParams(
        size     = 384,           # all-MiniLM-L6-v2 output dimension
        distance = Distance.COSINE
    )
)
```

**How documents become points:**

Each source document is split into overlapping chunks (800 words, 150-word overlap), then each chunk is embedded and stored as one Qdrant point.

```
Source document  →  chunk_document()  →  _embed()  →  PointStruct
                     800w / 150w overlap   Ollama        Qdrant upsert
```

**Point schema (every vector in the collection carries this payload):**

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `id` | `uint` | `2847391650` | MD5 of `"{doc_id}-{chunk_idx}"`, truncated to 8 hex chars → int |
| `payload.id` | `str` | `"a3f2c1d4e5b6"` | 16-char hex string — used for BM25 cross-reference |
| `payload.doc_id` | `str` | `"policy-budget-thresholds"` | Parent document ID |
| `payload.title` | `str` | `"FinOps Budget Threshold Policy v2.1"` | Human-readable document title |
| `payload.category` | `str` | `"policy"` | One of: `policy`, `playbook`, `guide` |
| `payload.chunk_idx` | `int` | `0` | Zero-based chunk index within the parent document |
| `payload.content` | `str` | `"This policy defines budget thresholds..."` | Raw text of the chunk (≤800 words) |
| `vector` | `float[384]` | `[0.021, -0.143, ...]` | all-MiniLM-L6-v2 embedding of `payload.content` |

### The Six Source Documents

| doc_id | title | category | Sections |
|--------|-------|----------|---------|
| `policy-budget-thresholds` | FinOps Budget Threshold Policy v2.1 | `policy` | Alert tiers (Green/Yellow/Red/Critical), per-team monthly caps, anomaly rules, exception approval process |
| `policy-cost-allocation` | Cloud Cost Allocation & Tagging Standards | `policy` | Mandatory tags (team, env, project, cost-center), untagged resource policy, shared infra split, chargeback model |
| `playbook-anomaly-response` | Cost Anomaly Response Playbook | `playbook` | Trigger conditions, 3 anomaly types, ownership assignment, root cause steps, remediation and prevention |
| `guide-rightsizing` | Cloud Rightsizing Decision Guide | `guide` | CPU, memory, GPU, storage utilization thresholds; savings plan vs reserved instance decision table |
| `guide-finops-kpis` | FinOps KPIs & Success Metrics | `guide` | Unit economics, waste reduction metrics, budget health KPIs, anomaly MTTD/MTTR targets |
| `policy-ml-platform` | ML Platform Cost Governance Policy | `policy` | Training job resource limits, experiment cost budgets, GPU instance policy, artifact retention rules |

### Qdrant Deployment Modes

The same client code supports three modes — selected by env vars, no code changes:

| Mode | Config | Use Case |
|------|--------|---------|
| In-memory | `QDRANT_PATH=""` `QDRANT_URL=""` | Local dev — data lost on restart |
| Persistent | `QDRANT_PATH=./qdrant_data` | Default — survives restarts, Render disk |
| Cloud | `QDRANT_URL=https://...` `QDRANT_API_KEY=...` | Production scale |

***

## The Internal Spend Ledger (`backend/data/company_spend.py`)

### Why This Exists

The agent needs actual company spend data to analyze — not stock prices, not
random values. `company_spend.py` provides a deterministic 90-day spend ledger
(seed=42, 810 records) that the tools read directly. The same data appears on
every run, making tests stable and the agent's answers reproducible.

### Structure

```python
SPEND_RECORDS    # list of 810 dicts — one per service per day, 90 days
TEAM_BUDGETS     # monthly + quarterly caps per team, matching documents.py policy
INDUSTRY_BENCHMARKS  # sourced figures from 6 published 2025 reports (see below)
```

Each spend record:

| Field | Type | Example |
|-------|------|---------|
| `date` | `str` | `"2026-01-15"` |
| `service` | `str` | `"ml-training"` |
| `team` | `str` | `"ml-platform"` |
| `spend_usd` | `float` | `1847.23` |
| `resource_type` | `str` | `"compute"` |
| `environment` | `str` | `"prod"` |
| `region` | `str` | `"us-east-1"` |

### Embedded Anomalies

Three intentional anomalies are baked into the data to exercise Z-score detection:

| Anomaly | Service | Window | Signal |
|---------|---------|--------|--------|
| 3× GPU spike | `ml-training` | day −15 and −14 | Runaway training job; Z≈6.2 |
| 20%/week compounding creep | `data-pipeline` | last 3 weeks | Growing data volume; 4 anomalous days |
| One-day outage | `api-gateway` | day −5 | Service turned off; spend drops to $0 |

### Industry Benchmarks — Sources

All figures in `INDUSTRY_BENCHMARKS` are sourced from primary reports.
None are estimated or interpolated.

| Benchmark | Value | Source |
|-----------|-------|--------|
| Cloud waste rate | 27% of spend | Flexera 2025 State of the Cloud (750+ orgs) |
| Multi-cloud waste premium | 31% | Flexera 2025 |
| Average budget overage | 17% | Flexera 2025 press release (March 2025) |
| Orgs struggling with cloud spend | 84% | Flexera 2025 |
| Mid-market monthly spend (51–200 employees) | $9,000/month | SpendArk Cloud Cost Benchmark 2026 |
| Large company monthly spend (201–1,000 employees) | $47,500/month | SpendArk 2026 |
| Cost per employee — SaaS | $380/month | SpendArk 2026 + Gartner 2025 |
| Infra as % of SaaS revenue | 8–15% | SpendArk 2026 / Flexera 2025 |
| Compute waste share | 35% of compute spend | Flexera 2025 + Harness 2025 |
| Storage waste share | 30% of storage spend | Flexera 2025 + Harness 2025 |
| GPU idle waste | 60–70% of GPU budget | Mirantis 2025 GPU Utilization Guide |
| Avg CPU utilization across clusters | 10% | Cast AI 2025 Kubernetes Cost Benchmark |
| Avg memory utilization across clusters | 23% | Cast AI 2025 Kubernetes Cost Benchmark |
| Reserved instance coverage sweet spot | 75% | FinOps Foundation State of FinOps 2025 |
| RI mature minimum coverage | 60% | FinOps Foundation 2025 / Cloudaware 2026 |
| Orgs with accurate cost attribution | 30% | n2ws 2025 cloud computing statistics |
| Devs using guesswork for commitments | 55% | Harness 2025 (700 engineers surveyed) |
| YoY cloud spend growth | 28% | Flexera 2025 |

**Primary sources:**
1. Flexera 2025 State of the Cloud — https://info.flexera.com/CM-REPORT-State-of-the-Cloud
2. SpendArk Cloud Cost Benchmark 2026 — https://spendark.com/blog/cloud-cost-benchmark-2026/
3. FinOps Foundation State of FinOps 2025 — https://data.finops.org/2025-report/
4. Cast AI 2025 Kubernetes Cost Benchmark Report
5. Mirantis 2025 GPU Utilization Guide — https://www.mirantis.com/blog/improving-gpu-utilization/
6. Harness 2025 Cloud Cost Management Report — 700 developers surveyed Nov–Dec 2024

*Last verified: May 2026. Refresh annually.*

***

## Architectural Trade-Offs

**LangGraph over plain LangChain chains:** LangGraph gives an explicit, inspectable state machine with typed nodes and conditional edges. Each node is a pure async function — easy to unit test in isolation. The `AgentState` TypedDict makes the data flow auditable. Plain chains are opaque; this graph can be visualised and its routing logic is readable code.

**Qdrant in-memory over Chroma/FAISS:** Qdrant's Python client runs entirely in-process without a server binary in `:memory:` mode, persists to a local path with the same API, and scales to Qdrant Cloud without any code change. Chroma requires a separate server for production; FAISS has no native filtering and requires wrapper code for the category filter used in CoRAG.

**Hybrid BM25 + Dense over pure vector search:** FinOps policy documents contain exact numeric thresholds (`$5,000`, `>120%`, `>2 standard deviations`). Pure cosine similarity on embeddings often misses exact numeric matches. BM25Okapi handles keyword-exact retrieval; RRF fusion ensures neither signal dominates.

**Internal spend ledger over live market proxies:** The agent analyzes `SPEND_RECORDS` in `backend/data/company_spend.py` — 810 records of deterministic daily spend per service and team, generated with seed=42. Spend ranges, waste percentages, and benchmark thresholds are all grounded in the six primary 2025 reports listed above. Three embedded anomalies (GPU spike Z≈6.2, pipeline creep, API outage) exercise the Z-score detection path with realistic signal. The `get_market_benchmark` tool compares the company's actual monthly spend against the sourced per-size benchmarks — allowing the agent to say "your spend is 3×the mid-market benchmark of $9,000/month (SpendArk 2026)" rather than quoting a stock ETF.

**`sentence-transformers/all-MiniLM-L6-v2` over larger embeddings:** Fully local via fastembed, zero cost, 384 dimensions, ~80 MB resident — chosen so the agent runs on a 512 MB Render instance. The quality gap vs. larger 768-dim models is negligible at this corpus size (6 documents, ~4k words).