# FinOps Advisory Agent

> **Cloud Cost Anomaly Detection & Advisory Agent** — powered by LangGraph, Qdrant, and Ollama.

An AI agent that autonomously decides when to query internal FinOps policy knowledge (RAG) vs. when to call live market data tools (Tool-Use), implementing algorithms from NeurIPS 2025 and ICLR 2024 research.

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              LangGraph Agent Graph                   │
│                                                      │
│  ┌──────────────────┐                                │
│  │ decide_retrieval  │  ← Self-RAG: is RAG needed?   │
│  └─────────┬────────┘                                │
│            │                                         │
│     ┌──────▼──────┐    ┌──────────────┐             │
│     │  retrieve_  │    │ agent_reason │             │
│     │  context    │    │ (ReAct loop) │             │
│     │  (HyDE +    │───▶│ + tools      │             │
│     │  Hybrid RRF)│    └──────┬───────┘             │
│     └─────────────┘          │                      │
│                        ┌─────▼──────┐               │
│                        │ToolNode    │               │
│                        │(6 real     │               │
│                        │ API tools) │               │
│                        └─────┬──────┘               │
│                        ┌─────▼──────┐               │
│                        │ corag_     │               │
│                        │ followup   │  ← CoRAG hop  │
│                        └────────────┘               │
└─────────────────────────────────────────────────────┘
    │
    ▼
FastAPI → React UI
```

### Implemented Algorithms

| Algorithm | Venue | What It Does |
|-----------|-------|--------------|
| **Self-RAG** (Asai et al.) | ICLR 2024 | Adaptive retrieval — agent decides if RAG is needed per query |
| **HyDE** (Gao et al.) | ACL 2023 | Hypothetical document embeddings for better semantic alignment |
| **CoRAG** | NeurIPS 2025 | Iterative multi-hop retrieval after tool results |
| **CRAG** (Yan et al.) | ICLR 2024 | RRF fusion of dense + BM25 sparse retrieval |
| **ReAct** (Yao et al.) | ICLR 2023 | Reasoning + Acting loop via LangGraph ToolNode |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |
| [Ollama](https://ollama.com) | latest | Local/Cloud chat LLM runner (embeddings run locally via fastembed — no Ollama embedding model required) |
| [Node.js](https://nodejs.org) | ≥18 | Frontend build |
| Alpha Vantage API Key | free | Real market data (25 req/day) |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/finops-agent.git
cd finops-agent

# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# Local Ollama (default)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# OR Ollama Cloud
OLLAMA_BASE_URL=https://api.ollama.ai
OLLAMA_API_KEY=your_ollama_cloud_key
OLLAMA_MODEL=deepseek-v3.1:671b-cloud

# Real market data (free — sign up at alphavantage.co)
ALPHA_VANTAGE_KEY=your_free_key_here
```

### 3. Pull the chat LLM

Only the chat LLM needs to be pulled via Ollama. Embeddings run **locally via [fastembed](https://github.com/qdrant/fastembed)** (Qdrant's ONNX-based embedder) — no Ollama embedding model required, and it works even when chat is served by Ollama Cloud (whose free tier does not authorize embedding endpoints).

```bash
# Local Ollama — pick one
ollama pull qwen2.5:7b        # Recommended — best tool calling at 7B
ollama pull llama3.1:8b       # Alternative

# Ollama Cloud — no pull needed, just set OLLAMA_API_KEY and OLLAMA_MODEL (e.g. gemma4:31b-cloud)
```

### 4. Prefetch the embedding model (optional but recommended)

`fastembed` is installed automatically by `uv sync`. The default model is **`BAAI/bge-base-en-v1.5`** (768-dim, quantized ONNX, ~110 MB), defined as `EMBED_MODEL_NAME` in [backend/rag/store.py](backend/rag/store.py). On first server start it downloads to the HuggingFace cache (`~/.cache/huggingface/` on Linux/macOS, `%LOCALAPPDATA%\Temp\fastembed_cache\` on Windows).

To prefetch it now so the first request isn't slow:

```bash
uv run python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-base-en-v1.5')"
```

### 5. Run in development

```bash
# Terminal 1 — Backend
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Production Build

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Run production server (serves frontend + API on port 8000)
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check — Ollama + vector store status |
| `POST` | `/api/chat` | Main agent endpoint |
| `GET` | `/api/index/status` | Vector store index status |
| `POST` | `/api/index/rebuild` | Rebuild the RAG index |
| `GET` | `/api/documents` | List knowledge base documents |

### Chat request example

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Is the ML Platform team over budget this quarter?"}'
```

---

## Deployment on Render (Free Tier)

1. Push your repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` — no manual config needed
5. Add environment variables in the Render dashboard:
   - `OLLAMA_BASE_URL` → your Ollama Cloud URL
   - `OLLAMA_API_KEY` → your Ollama Cloud key
   - `ALPHA_VANTAGE_KEY` → your Alpha Vantage key
6. Click **Deploy**

> **Note:** For free tier Render, use Ollama Cloud (not local Ollama). Qdrant runs in persistent path mode (`./qdrant_data`) — data persists across deploys on Render's disk.

---

## Agent Tools

| Tool | Data Source | What It Does |
|------|-------------|--------------|
| `get_service_spend` | Alpha Vantage (real) | Daily spend trend for any cloud service |
| `detect_spend_anomaly` | Alpha Vantage (real) | Z-score anomaly detection on spend series |
| `get_budget_vs_actual` | Alpha Vantage (real) | Budget vs actual for any team/quarter |
| `get_rightsizing_recommendations` | Alpha Vantage (real) | Instance rightsizing with savings estimates |
| `flag_cost_alert` | Internal | Creates structured cost alert record |
| `get_market_benchmark` | Alpha Vantage ETF data | Cloud cost industry benchmarks |

---

## Knowledge Base Documents

The RAG corpus contains 6 structured documents:

- **FinOps Budget Threshold Policy v2.1** — alert tiers, per-team caps, anomaly rules
- **Cloud Cost Allocation & Tagging Standards** — mandatory tags, chargeback model
- **Cost Anomaly Response Playbook** — step-by-step remediation procedures
- **Cloud Rightsizing Decision Guide** — CPU/memory/GPU rightsizing decision trees
- **FinOps KPIs & Success Metrics** — unit economics, waste reduction, forecast accuracy
- **ML Platform Cost Governance Policy** — GPU limits, experiment budgets, storage lifecycle

---

## Project Structure

```
finops-agent/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── agent/
│   │   ├── graph.py          # LangGraph agent (ReAct + Self-RAG + CoRAG)
│   │   └── prompts.py        # System prompt, HyDE prompt, Self-RAG prompt
│   ├── api/
│   │   ├── routes.py         # FastAPI endpoints
│   │   └── schemas.py        # Pydantic request/response models
│   ├── rag/
│   │   ├── store.py          # Qdrant vector store + fastembed (BAAI/bge-base-en-v1.5) + hybrid RRF
│   │   └── documents.py      # FinOps knowledge base documents
│   ├── tools/
│   │   └── finance_tools.py  # 6 real-data tools (Alpha Vantage)
│   └── core/
│       ├── config.py         # Pydantic settings
│       └── logging.py        # Structured logging
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React component
│   │   ├── main.jsx          # React entry point
│   │   └── lib/api.js        # API client
│   ├── package.json
│   └── vite.config.js
├── pyproject.toml            # UV dependencies
├── render.yaml               # Render deployment config
├── Makefile                  # Development shortcuts
└── .env.example              # Environment template
```

---

## Architectural Choices 

**LangGraph** was chosen over plain LangChain chains because it provides explicit state management, conditional edge routing, and checkpointing — making the agent's decision process auditable and testable. The stateful graph also enables the CoRAG multi-hop pattern natively.

**Qdrant** was chosen because it supports in-memory mode (no server required for dev), local persistent mode (no external dependencies), and Qdrant Cloud free tier (1GB) for production — all via the same Python client API with zero code changes.

**Hybrid BM25 + Dense retrieval with RRF** was implemented rather than pure vector search because FinOps documents contain exact policy terms (dollar thresholds, percentages) that keyword search handles better than semantic similarity.

**fastembed (`BAAI/bge-base-en-v1.5`)** is used for dense embeddings instead of calling a remote embedding API. It runs on CPU via ONNX Runtime (no PyTorch dependency), keeps the cold-start surface small, and remains free of network calls — so the deployment doesn't depend on a hosted embedding provider. 768-dim output is matched by the Qdrant collection schema.

**Alpha Vantage** provides real financial time-series data on a free tier (25 req/day), giving genuine spend trends instead of hardcoded mock values.

---

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Test the agent directly
uv run python -c "
import asyncio
from backend.agent.graph import get_agent_graph
from langchain_core.messages import HumanMessage

async def test():
    graph = get_agent_graph()
    result = await graph.ainvoke({
        'messages': [HumanMessage(content='What is the budget policy for the ML Platform team?')],
        'rag_context': None, 'retrieval_needed': None, 'hop_count': 0,
        'query': 'What is the budget policy for the ML Platform team?'
    })
    print(result['messages'][-1].content)

asyncio.run(test())
"
```
