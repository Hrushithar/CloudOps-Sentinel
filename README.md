# CloudOps Sentinel

**Self-RAG Incident Response Copilot for Cloud Operations**

CloudOps Sentinel is an AI-powered incident response assistant that helps on-call engineers troubleshoot production issues using private operational runbooks. It implements a **Self-RAG** (Self-Reflective Retrieval-Augmented Generation) workflow: retrieve evidence from a private knowledge base, grade relevance, verify that the answer is supported by the evidence (IsSUP), check usefulness (IsUSE), and fall back to internet search only when internal runbooks are insufficient. Every interaction is remembered via SQLite conversation memory and logged to an audit trail.

Built with **FastAPI**, **LangGraph**, **Pinecone**, **Groq**, **Tavily**, **HuggingFace embeddings**, and **SQLite**.

## Features

| Feature | Description |
|---|---|
| 🔍 **Self-RAG pipeline** | Retrieve → grade → verify support → check usefulness → revise or web-search automatically |
| 📚 **Private knowledge base** | Pinecone vector store with HuggingFace embeddings; ingest PDF, TXT, MD, DOCX runbooks |
| 🌐 **Internet search fallback** | Tavily search activates only when internal evidence is insufficient |
| 🧠 **Conversation memory** | SQLite-backed LangGraph checkpointer remembers context across incident follow-ups |
| 📋 **Audit trail** | Every Q&A interaction is logged (route, support status, sources, trace) and queryable via API |
| ⚡ **FastAPI backend** | REST API + browser-based incident console with Jinja2 templates |
| 🐳 **Docker-ready** | Dockerfile for container deployment |

## Project Structure

```
CloudOps Sentinel/
├── app.py                      # FastAPI application (API routes + frontend)
├── data_ingestion.py           # CLI for bulk ingesting documents into Pinecone
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container definition (python:3.12-slim)
├── template.py                 # Project scaffold generator
├── .env                        # Environment variables (gitignored)
├── .gitignore
├── .dockerignore
├── documents/                  # Sample runbooks ingested into the KB
│   ├── checkout-api-runbook.md
│   ├── deployment-rollback-sop.md
│   └── payments-high-cpu-runbook.md
├── data/                       # SQLite databases (audit + LangGraph memory)
├── uploads/                    # User-uploaded runbooks awaiting ingestion
├── src/
│   ├── __init__.py
│   ├── config.py               # Pydantic settings from .env
│   ├── models.py               # Pydantic request/response models
│   ├── ingestion.py            # Document loading, chunking, Pinecone upsert
│   ├── self_rag.py             # LangGraph Self-RAG agent graph
│   ├── vectorstore.py          # Pinecone index + retriever setup
│   └── db.py                   # SQLite audit logging
├── static/
│   ├── app.js                  # Frontend chat + upload logic
│   └── styles.css              # Dark-mode incident console styles
└── templates/
    └── index.html              # Jinja2 frontend (Incident Response Console)
```

## How It Works

The core Self-RAG agent (`src/self_rag.py`) is a LangGraph state machine:

1. **Contextualize** — Rewrites the user's question as a standalone cloud-ops question using prior conversation memory.
2. **Decide retrieval** — Determines whether to answer from general knowledge, search internal runbooks, or go straight to web search.
3. **Retrieve** — Queries the Pinecone vector store for relevant runbook chunks.
4. **Grade** — Filters retrieved documents for relevance; rewrites the query and retries (internal or web) if needed.
5. **Generate** — Drafts an answer grounded in the evidence.
6. **Support check (IsSUP)** — Verifies the answer is fully/partially supported by evidence; revises if not.
7. **Usefulness check (IsUSE)** — Confirms the answer is useful; triggers another rewrite if not.
8. **Commit memory** — Saves the turn to SQLite conversation memory and the audit database.

Routes are reported to the user as: **Private Runbooks**, **Internet Search**, **General Knowledge**, or **No Reliable Evidence**.

## Prerequisites

- Python 3.12+
- A [Pinecone](https://pinecone.io) account and API key (serverless index)
- A [Groq](https://groq.com) API key (or XAI-compatible endpoint)
- A [Tavily](https://tavily.com) API key (optional — enables internet search fallback)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Hrushithar/CloudOps-Sentinel.git
cd "CloudOps Sentinel"
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# or: .venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment

Create a `.env` file in the project root:

```bash
# --- LLM (Groq) ---
GROQ_API_KEY=your_groq_api_key
LLM_MODEL=qwen/qwen3.8-27b

# --- Embeddings (HuggingFace, run locally) ---
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# --- Pinecone vector store ---
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=cloudops-sentinel-self-rag
PINECONE_NAMESPACE=incident-runbooks
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
PINECONE_AUTO_RECREATE_INDEX=true

# --- Internet search (Tavily) ---
TAVILY_API_KEY=your_tavily_api_key

# --- LangSmith tracing (optional) ---
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=cloudops-sentinel

# --- Self-RAG controls ---
TOP_K=5
MAX_SUPPORT_RETRIES=2
MAX_RETRIEVAL_REWRITES=2
MAX_WEB_REWRITES=2

# --- Database ---
DATABASE_PATH=data/audit.db
```

> **Note:** `.env` is gitignored and never committed. Keep your API keys secret.

## Usage

### Run the application locally

```bash
source .venv/bin/activate
python app.py
```

The server starts at `http://localhost:8080`. Open the **Incident Response Console** in your browser to chat, upload runbooks, and inspect traces.

### Run with Docker

```bash
docker build -t cloudops-sentinel .
docker run -p 8080:8080 --env-file .env cloudops-sentinel
```

### Ingest documents into the knowledge base

Place `.pdf`, `.txt`, `.md`, or `.docx` files in `./documents`, then run:

```bash
python data_ingestion.py
```

You can also upload files directly through the web console (**Runbook Vault → Add to knowledge base**). Uploaded files land in `./uploads` and are indexed into Pinecone automatically.

### Sample starter questions

Try these in the console:

- *"Our checkout API is returning 502 errors after deployment. What should the on-call engineer check first?"*
- *"CPU on the payments service is above 90%. What is our recommended response procedure?"*
- *"What should I verify when a Kubernetes pod keeps restarting with CrashLoopBackOff?"*

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Incident Response Console (HTML) |
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Ask an incident question (`{ question, thread_id }`) |
| `/api/upload` | POST | Upload a runbook file to index (multipart `file`) |
| `/api/audits` | GET | Recent audit trail entries (`?limit=20`) |

Example chat request:

```bash
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Checkout API 502 after deployment","thread_id":"incident-123"}'
```

## Sample Runbooks

The `documents/` folder includes starter runbooks:

- **checkout-api-runbook.md** — 502 errors after deployment, escalation paths
- **payments-high-cpu-runbook.md** — High CPU response procedure and safety notes
- **deployment-rollback-sop.md** — Production rollback pre-checks and execution

Add your own SOPs, postmortems, and architecture notes to this folder (or upload via the UI) to extend the knowledge base.

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` / `XAI_API_KEY` | Yes | — | LLM API key |
| `LLM_MODEL` | No | `qwen/qwen3.8-27b` | Groq model name |
| `PINECONE_API_KEY` | Yes | — | Pinecone API key |
| `PINECONE_INDEX_NAME` | No | `cloudops-sentinel-self-rag` | Pinecone index name |
| `PINECONE_NAMESPACE` | No | `incident-runbooks` | Pinecone namespace |
| `PINECONE_CLOUD` | No | `aws` | Pinecone cloud provider |
| `PINECONE_REGION` | No | `us-east-1` | Pinecone region |
| `TAVILY_API_KEY` | No | — | Tavily search API key (web fallback) |
| `EMBEDDING_MODEL` | No | `sentence-transformers/all-MiniLM-L6-v2` | HF embedding model |
| `EMBEDDING_DIMENSION` | No | `384` | Embedding vector dimension |
| `TOP_K` | No | `5` | Retrieval top-k |
| `MAX_SUPPORT_RETRIES` | No | `2` | Max IsSUP revision loops |
| `MAX_RETRIEVAL_REWRITES` | No | `2` | Max internal query rewrites |
| `MAX_WEB_REWRITES` | No | `2` | Max web query rewrites |
| `DATABASE_PATH` | No | `data/audit.db` | SQLite audit DB path |
| `LANGSMITH_*` | No | — | Optional LangSmith tracing |

## License

This project is provided as-is for cloud operations incident response use. See the repository for license details.

---

*CloudOps Sentinel — Ground every troubleshooting decision in private operational evidence.*