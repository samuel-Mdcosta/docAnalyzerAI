# DocAnalyzer AI

**Autonomous agent for analysis of legal and financial documents**

DocAnalyzer AI is a ReAct agent built with LangGraph that reads, reasons over, and navigates legal contracts and financial reports of any size — including documents with hundreds of pages, tables, and embedded charts.

Unlike a simple RAG chatbot, the agent decides on its own which tools to call, in what order, and when to stop. It does not just retrieve — it reasons.

---

## Demo

> Upload a PDF → Ask a question → The agent navigates the document step by step and returns a structured answer with cited excerpts and a risk score.

```
User: "What are the early termination penalties in this contract?"

Thought: I need to find rescission clauses in the document.
Action:  search_document(query="early termination penalty")
Obs:     [chunk 12] "§ 8 In case of early termination, the breaching party shall pay..."

Thought: Found the clause. Checking for cross-references.
Action:  search_document(query="cancellation fine contract")
Obs:     [chunk 15] reference to same clause + value table

Thought: Sufficient context. Generating structured response.
Action:  finish → response with cited excerpts + risk_score: 74
```

---

## Why DocAnalyzer is different from ChatGPT or Gemini

| Scenario                              | ChatGPT / Gemini         | DocAnalyzer AI          |
| ------------------------------------- | ------------------------ | ----------------------- |
| Small PDF, direct question            | Resolves                 | Resolves                |
| 400+ page document                    | Truncates / hallucinates | RAG navigates correctly |
| Multi-step reasoning with calculation | Often fails              | Step-by-step            |
| Memory between sessions               | Forgets everything       | MongoDB persists        |
| Compare 2 documents                   | Manual and fragile       | Automated semantic diff |
| Structured output for systems         | Text only                | JSON / API              |
| Integration into enterprise products  | Not an API               | Central API             |

---

## Architecture

```
User → PDF + question in natural language
         │
         ▼
[INGESTION]   Docling extracts text, tables, and charts
         │
         ▼
[EMBEDDING]   Nomic embed-text-v1.5 → 768-dimension vectors
         │
         ▼
[VECTOR STORE] MongoDB Atlas Vector Search (persistent index)
         │
         ▼
┌─────────────────────────────────────┐
│       LangGraph State Machine       │
│  agent_node → tool_node → loop → END│
└─────────────────────────────────────┘
         │
         ▼
[FINAL RESPONSE] structured text + cited excerpts + risk score
```

### Memory layers

| Layer       | Technology            | Scope                              |
| ----------- | --------------------- | ---------------------------------- |
| Short-term  | LangGraph MemorySaver | Current session                    |
| Medium-term | Redis                 | Recent query cache                 |
| Long-term   | MongoDB Atlas         | Full history per document and user |

---

## Agent tools

| Tool                    | Type     | Description                                              |
| ----------------------- | -------- | -------------------------------------------------------- |
| `search_document`       | CORE     | Semantic search in MongoDB Vector Search                 |
| `extract_clauses`       | CORE     | Extracts clauses by type (penalty, rescission, deadline) |
| `calculate_risk_score`  | ANALYSIS | Returns score 0–100 + risk flags                         |
| `compare_documents`     | ANALYSIS | Semantic diff between two document versions              |
| `summarize_section`     | OUTPUT   | Structured summary with cited excerpts                   |
| `web_search`            | EXTERNAL | Searches legislation via Tavily API                      |
| `get_document_metadata` | UTILITY  | Parties, dates, contract type                            |

### Agent safeguards

- `max_iterations: 10` — prevents infinite loop
- `token_budget` — cost control per tool call
- `confidence_threshold: 0.75` — only cites excerpts above similarity threshold
- `fallback_response` — informs if answer was not found after N iterations

---

## Tech stack

| Layer               | Technology                                    |
| ------------------- | --------------------------------------------- |
| Orchestration       | LangGraph 0.2+ (ReAct)                        |
| LLM                 | Google Gemini 1.5 Pro                         |
| Embeddings          | Nomic embed-text-v1.5 (768 dimensions)        |
| Vector Store        | MongoDB Atlas Vector Search                   |
| Document extraction | Docling (IBM) — text, tables, charts          |
| Chart extraction    | Gemini Vision (rasterized graphs)             |
| Cache / memory      | Redis                                         |
| API                 | FastAPI + Uvicorn (SSE streaming)             |
| Authentication      | JWT + httpOnly refresh token                  |
| External search     | Tavily API                                    |
| Frontend            | React + Tailwind CSS                          |
| Deploy              | Docker · Render (backend) · Vercel (frontend) |

---

## Security

| Layer              | Technology                    | Protects against              |
| ------------------ | ----------------------------- | ----------------------------- |
| Authentication     | JWT + httpOnly cookie         | Session theft, XSS            |
| Authorization      | `owner_id` on every query     | Lateral data leakage          |
| Encryption at rest | AES-256                       | Storage data leakage          |
| Transport          | HTTPS + restricted CORS       | MITM, unauthorized origin     |
| Prompt injection   | Sanitization + XML delimiters | Document content manipulation |
| Rate limiting      | Redis + FastAPI middleware    | API abuse, brute force        |
| Audit log          | Immutable MongoDB logs        | Traceability, LGPD compliance |

---

## MLOps practices

| Practice               | Implementation                                            |
| ---------------------- | --------------------------------------------------------- |
| Reproducibility        | Docker + pinned requirements                              |
| Environment versioning | `APP_VERSION` in `.env`                                   |
| Feature flags          | `ENABLE_*` variables — no rebuild needed                  |
| Structured logging     | JSON logger per event                                     |
| Analysis traceability  | Immutable audit log in MongoDB                            |
| Performance monitoring | `/metrics` endpoint (avg iterations, latency, confidence) |
| Cost control           | API cost log per call                                     |

---

## Project structure

```
docanalyzer-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point
│   │   ├── logger.py                # structured JSON logger
│   │   ├── agent/
│   │   │   ├── graph.py             # LangGraph StateGraph
│   │   │   ├── state.py             # AgentState TypedDict
│   │   │   ├── nodes.py             # agent_node, tool_node
│   │   │   └── conditions.py        # should_continue logic
│   │   ├── tools/
│   │   │   ├── search.py            # search_document
│   │   │   ├── extract.py           # extract_clauses
│   │   │   ├── risk.py              # calculate_risk_score
│   │   │   ├── summarize.py         # summarize_section
│   │   │   └── web.py               # web_search (Tavily)
│   │   ├── ingestion/
│   │   │   ├── pdf_parser.py        # Docling pipeline
│   │   │   ├── chunker.py           # semantic chunking
│   │   │   └── embedder.py          # Nomic embeddings
│   │   ├── database/
│   │   │   ├── mongo.py             # MongoDB Atlas client
│   │   │   ├── redis.py             # Redis client
│   │   │   └── audit.py             # immutable audit log
│   │   └── api/
│   │       ├── routes.py            # FastAPI endpoints
│   │       └── auth.py              # JWT authentication
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Upload.jsx
│       │   ├── Analyze.jsx
│       │   └── History.jsx
│       └── components/
│           ├── RiskPanel.jsx        # visual risk traffic light
│           └── CitationViewer.jsx   # cited excerpt highlight
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Getting started

### Prerequisites

- Docker and Docker Compose
- MongoDB Atlas account (free tier works)
- Google AI Studio API key (Gemini)
- Tavily API key (free tier)

### 1. Clone the repository

```bash
git clone https://github.com/samuel-Mdcosta/docanalyzer-ai
cd docanalyzer-ai
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
GEMINI_API_KEY=your_key_here
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/docanalyzer
TAVILY_API_KEY=tvly-...
REDIS_URL=redis://redis:6379
APP_VERSION=0.1.0
ENVIRONMENT=development
MAX_ITERATIONS=10
CONFIDENCE_THRESHOLD=0.75
ENABLE_CHART_EXTRACTION=true
ENABLE_WEB_SEARCH=true
ENABLE_AUDIT_LOG=true
```

Generate the JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# paste the output into JWT_SECRET in .env
```

### 3. Build and run

```bash
# first build — downloads Docling models (~2GB inside Docker)
# takes 10–20 minutes on first run
docker-compose build

# start containers
docker-compose up -d
```

### 4. Validate the environment

```bash
# API health check
curl http://localhost:8000/health

# Redis
docker-compose exec redis redis-cli ping

# Docling
docker-compose exec backend python -c \
  "from docling.document_converter import DocumentConverter; print('Docling ok')"

# LangGraph
docker-compose exec backend python -c \
  "from langgraph.graph import StateGraph; print('LangGraph ok')"

# Swagger UI
# open in browser: http://localhost:8000/docs
```

---

## API endpoints

| Method   | Endpoint              | Description                             |
| -------- | --------------------- | --------------------------------------- |
| `POST`   | `/auth/register`      | Create account                          |
| `POST`   | `/auth/login`         | Authenticate, returns JWT               |
| `POST`   | `/upload`             | Upload PDF for processing               |
| `GET`    | `/documents`          | List user's documents                   |
| `POST`   | `/analyze`            | Send question to agent (SSE streaming)  |
| `GET`    | `/history/{doc_id}`   | Analysis history for a document         |
| `DELETE` | `/documents/{doc_id}` | Delete document and all chunks (LGPD)   |
| `GET`    | `/health`             | Service health + version                |
| `GET`    | `/metrics`            | Agent performance metrics (last 7 days) |

---

## Development

```bash
# view logs
docker-compose logs -f backend

# open terminal inside container
docker-compose exec backend bash

# rebuild after adding a new library to requirements.txt
docker-compose build backend
docker-compose up -d

# stop everything
docker-compose down
```

---

## Roadmap

- [x] Project structure and Docker environment
- [ ] MLOps practices (logging, audit, metrics, feature flags)
- [ ] Phase 1 — PDF ingestion pipeline (Docling)
- [ ] Phase 2 — Agent tools (@tool)
- [ ] Phase 3 — LangGraph ReAct agent
- [ ] Phase 4 — Memory layers + FastAPI
- [ ] Phase 5 — React frontend + production deploy

---

## Target use cases

**Legal** — Contract analysis, rescission clause identification, risk flagging, semantic diff between versions.

**Finance** — Quarterly report reading, EBITDA variation calculation, table and chart extraction, KPI comparison.

**Compliance** — Automated document audit, immutable traceability log, LGPD-compliant data deletion.

---

## Author

**Samuel M. Costa**
Backend & AI Engineering · Python · LangGraph · FastAPI

[![LinkedIn](https://img.shields.io/badge/LinkedIn-samuel--mdcosta-blue)](https://linkedin.com/in/samuelmdcosta)
[![GitHub](https://img.shields.io/badge/GitHub-samuel--Mdcosta-black)](https://github.com/samuel-Mdcosta)

---

_DocAnalyzer AI · Technical Documentation v1.0 · 2026_
