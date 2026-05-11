# GitHub Commit Plan — FinOps Advisory Agent

This plan describes how to commit the codebase layer by layer to show clear architectural progression.
Each commit represents a meaningful, independently testable unit of work.

---

## Commit 1 — `chore: initial project scaffold`

**Files:**
```
pyproject.toml
.env.example
.gitignore
Makefile
README.md
```

**Message:**
```
chore: initial project scaffold

- Add pyproject.toml with uv-managed dependencies (FastAPI, LangGraph, Qdrant, Ollama)
- Add .env.example with all required environment variables documented
- Add Makefile for dev/build/test shortcuts
- Add .gitignore for Python, Node, Qdrant data, and secrets
- Add README skeleton
```

---

## Commit 2 — `feat: core configuration and logging`

**Files:**
```
backend/__init__.py
backend/core/__init__.py
backend/core/config.py
backend/core/logging.py
```

**Message:**
```
feat: core configuration and logging

- Add pydantic-settings based config with .env loading
- Support local Ollama, Ollama Cloud, and Qdrant in-memory/persistent/cloud modes
- Add structured stdout logging with configurable level
- Suppress noisy third-party loggers (httpx, sentence-transformers)
```

---

## Commit 3 — `feat: FinOps knowledge base documents`

**Files:**
```
backend/rag/__init__.py
backend/rag/documents.py
```

**Message:**
```
feat: FinOps knowledge base documents

Add 6 structured policy and guide documents forming the RAG corpus:
- FinOps Budget Threshold Policy v2.1 (alert tiers, per-team caps)
- Cloud Cost Allocation & Tagging Standards (mandatory tags, chargeback)
- Cost Anomaly Response Playbook (step-by-step remediation)
- Cloud Rightsizing Decision Guide (CPU/GPU/storage decision trees)
- FinOps KPIs & Success Metrics (unit economics, waste reduction)
- ML Platform Cost Governance Policy (GPU limits, experiment budgets)
```

---

## Commit 4 — `feat: Qdrant vector store with hybrid BM25+dense retrieval`

**Files:**
```
backend/rag/store.py
```

**Message:**
```
feat: Qdrant vector store with hybrid BM25+dense retrieval

Implements the retrieval layer powering the agent's RAG knowledge base:

- Qdrant in-memory by default; persistent path or Qdrant Cloud via env
- Document chunking with configurable size (800 tokens) and overlap (150)
- nomic-embed-text via Ollama for local embeddings (768-dim)
- BM25Okapi sparse index for keyword-exact policy term retrieval
- Reciprocal Rank Fusion (RRF, k=60) merging dense + sparse results
- Relevance threshold filtering (Self-RAG ISREL implementation)
- Singleton store pattern with lazy initialization on first request

Algorithm: CRAG-style hybrid retrieval (ICLR 2024)
```

---

## Commit 5 — `feat: six real-data FinOps tools via Alpha Vantage`

**Files:**
```
backend/tools/__init__.py
backend/tools/finance_tools.py
```

**Message:**
```
feat: six real-data FinOps tools via Alpha Vantage

All tools call real APIs (Alpha Vantage free tier) — no mock data:

- get_service_spend: daily spend trend (30d) with period average and direction
- detect_spend_anomaly: Z-score anomaly detection (configurable sensitivity)
- get_budget_vs_actual: quarterly budget vs actual with overage percentage
- get_rightsizing_recommendations: utilization-driven rightsizing with savings estimate
- flag_cost_alert: structured alert record with severity, impact, required actions
- get_market_benchmark: cloud infrastructure ETF benchmark data (WCLD, BOTZ, IGV)

Service names are mapped to real market tickers as realistic cost proxies.
Tools are all Pydantic-typed with rich docstrings for LLM tool selection.
```

---

## Commit 6 — `feat: LangGraph ReAct agent with Self-RAG, HyDE, and CoRAG`

**Files:**
```
backend/agent/__init__.py
backend/agent/prompts.py
backend/agent/graph.py
```

**Message:**
```
feat: LangGraph ReAct agent with Self-RAG, HyDE, and CoRAG

Core agent implementing 4 research algorithms in a LangGraph StateGraph:

Self-RAG (ICLR 2024): decide_retrieval node uses keyword heuristics + policy
signals to skip retrieval for pure data queries, saving latency.

HyDE (ACL 2023): retrieve_context generates a hypothetical answer before
embedding, bridging the semantic gap between terse queries and verbose docs.

Hybrid RRF retrieval: dense Qdrant search + BM25 merged via RRF in store.py.

CoRAG (NeurIPS 2025): corag_followup node triggers additional playbook
retrieval after tool results show anomalies or over-budget signals.

ReAct loop: agent_reason to ToolNode to corag_followup to agent_reason
with conditional routing at each step via LangGraph edges.

Agent state: typed TypedDict with add_messages reducer, rag_context,
retrieval decision flag, hop counter, and original query.
```

---

## Commit 7 — `feat: FastAPI backend with chat, health, and index endpoints`

**Files:**
```
backend/api/__init__.py
backend/api/schemas.py
backend/api/routes.py
backend/main.py
```

**Message:**
```
feat: FastAPI backend with chat, health, and index endpoints

- POST /api/chat: full agent pipeline with session tracking
- GET /api/health: Ollama connectivity + vector store status
- GET /api/index/status: Qdrant collection count and store type
- POST /api/index/rebuild: background task to re-index documents
- GET /api/documents: list knowledge base with id/title/category

CORS configured via env (supports both dev and production origins).
Lifespan handler warms up vector store on startup.
Frontend static file serving in production mode.
Full error handling: tool failures, Ollama timeouts, index errors.
```

---

## Commit 8 — `feat: React/Vite frontend with chat UI`

**Files:**
```
frontend/package.json
frontend/vite.config.js
frontend/index.html
frontend/src/main.jsx
frontend/src/App.jsx
frontend/src/lib/api.js
```

**Message:**
```
feat: React/Vite frontend with chat UI

- Dark-theme chat interface with message bubbles and markdown rendering
- ReactMarkdown + remark-gfm: renders tables, code blocks, lists from agent output
- Real-time status badges showing Ollama and vector store health
- Tool call and RAG context badges per message (shows which tools fired)
- Suggested query chips for demo (6 pre-built FinOps queries)
- Collapsible sidebar with status + query suggestions
- Vite proxy to localhost:8000 in dev, same-origin in production
- Enter to send, Shift+Enter for newline
```

---

## Commit 9 — `test: unit and integration tests for tools, API, and RAG`

**Files:**
```
tests/__init__.py
tests/test_tools.py
tests/test_api.py
tests/test_rag.py
```

**Message:**
```
test: unit and integration tests for tools, API, and RAG

tests/test_tools.py: async tool invocation, Z-score threshold validation,
alert_id format, rightsizing action enum validation

tests/test_api.py: health endpoint fields, documents endpoint count

tests/test_rag.py: document schema validation, category enum, policy count
```

---

## Commit 10 — `chore: deployment config and final README`

**Files:**
```
render.yaml
README.md (complete)
docs/COMMIT_PLAN.md
```

**Message:**
```
chore: deployment config and final README

- render.yaml: one-click Render deployment (builds frontend + starts FastAPI)
- Complete README: quick start, API reference, architecture diagram,
  algorithm table, project structure, Render deployment guide
- docs/COMMIT_PLAN.md: commit-by-commit breakdown for evaluator review

Deployment: Render free tier, Qdrant persistent path, Ollama Cloud
```

---

## Git Commands

```bash
# After cloning your new empty GitHub repo:
git init
git remote add origin https://github.com/YOUR_USERNAME/finops-agent.git

# Commit 1 — scaffold
git add pyproject.toml .env.example .gitignore Makefile README.md
git commit -m "chore: initial project scaffold"

# Commit 2 — config
git add backend/__init__.py backend/core/
git commit -m "feat: core configuration and logging"

# Commit 3 — documents
git add backend/rag/__init__.py backend/rag/documents.py
git commit -m "feat: FinOps knowledge base documents"

# Commit 4 — vector store
git add backend/rag/store.py
git commit -m "feat: Qdrant vector store with hybrid BM25+dense retrieval"

# Commit 5 — tools
git add backend/tools/
git commit -m "feat: six real-data FinOps tools via Alpha Vantage"

# Commit 6 — agent
git add backend/agent/
git commit -m "feat: LangGraph ReAct agent with Self-RAG, HyDE, and CoRAG"

# Commit 7 — API
git add backend/api/ backend/main.py
git commit -m "feat: FastAPI backend with chat, health, and index endpoints"

# Commit 8 — frontend
git add frontend/
git commit -m "feat: React/Vite frontend with chat UI"

# Commit 9 — tests
git add tests/
git commit -m "test: unit and integration tests for tools, API, and RAG"

# Commit 10 — deployment
git add render.yaml docs/
git commit -m "chore: deployment config and final README"

git push -u origin main
```
