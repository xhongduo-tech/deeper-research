# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**DataAgent Studio** — a multi-agent deep research report generation system. Users submit a research topic; the system plans tasks, gathers and verifies information via a RAG knowledge base, and produces formatted reports (PDF/DOCX). Designed for **intranet/air-gapped** deployment — external search and browser automation are disabled by default.

## Running the Stack

```bash
# ── Development (recommended) ───────────────────────────────────────────────
./dev.sh                   # Vite HMR :5173 + uvicorn --reload :8000
./dev.sh --rebuild         # reinstall npm deps then start
./dev.sh --backend         # restart backend only
./dev.sh --frontend        # restart frontend only
./dev.sh --clean           # wipe SQLite DB then start fresh
./dev.sh --test            # API smoke tests against running instance
./dev.sh --stop            # stop all local processes
./dev.sh --status          # show service status
./dev.sh --logs            # tail backend log  (--logs --frontend for Vite log)

# ── Docker (production image testing) ──────────────────────────────────────
./dev.sh --docker          # start with existing arm64 images (localhost:80)
./dev.sh --rebuild --docker # rebuild images then start

# Production (Linux x86_64):
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# ── Offline packaging ───────────────────────────────────────────────────────
./build_offline.sh          # builds linux/amd64 images → offline-images/
```

Copy `.env.example` to `.env` before running. Database migrations run automatically on backend startup via Alembic.

> **Dev workflow note:** The frontend is a React + Vite app (`frontend/src/`). `./dev.sh` is the standard local workflow — no Docker needed. Redis is started automatically (local `redis-server` or Docker fallback). Only use `--docker` when testing the final production image.

## Testing

```bash
# Frontend unit tests (Vitest)
cd frontend && npm test
cd frontend && npm run test:watch

# Backend (Pytest)
cd backend && pytest
cd backend && pytest tests/path/to/test_file.py::test_name  # single test
```

## Architecture

**LLM-OS philosophy:** "能力下沉，场景解耦" — front-end surfaces (home chat, docs/ppt/html, DataLab table-agent) are thin **Apps** sharing one capability middle-platform. The LLM is only the *intent router* + *text synthesizer*; all real computation/reasoning is forced into the sandbox / DuckDB / knowledge engines to eliminate hallucination.

**Three-tier stack:**

- **Frontend** — React + Vite SPA (`frontend/src/`). Built to `dist/` and served by Nginx. `admin.html` is a standalone vanilla-JS admin page. WebSocket client for real-time streaming.
- **Backend** — FastAPI on port 8000. REST API + WebSocket streaming + the unified pipeline.
- **Redis** — Async job queue.

**Four core engines (能力中台):**
1. **Ingress Gateway** (`backend/app/ingress/`) — `vfs.py` builds an in-memory directory tree from `.zip`/`.tar.gz`; `dispatcher.py` routes each file to a parser (`parsers/code_parser.py` Python-AST/regex multi-lang, `config_parser.py` YAML/JSON/TOML flatten, `template_parser.py` `.dotx/.potx` placeholder extraction). Outputs standardized `ParsedAsset`s.
2. **Knowledge Triad** (`backend/app/knowledge/`) — `intent_router.py` classifies the request into a scenario + ontology domain; `triad_coordinator.py` fuses ontology constraints → graph hops → vector RAG into one context block.
3. **Compute底座** (`backend/app/compute/`) — `duckdb_engine.py` registers Excel/CSV/Parquet as in-memory tables with an NL→SQL agent; `polyglot_sandbox.py` runs Python/Node/Shell/Java/Go with timeout + traceback capture. (`services/sandbox.py` is the RestrictedPython Python backend.)
4. **Rendering** (`backend/app/rendering/`) — `widget_renderer.py` emits self-contained ECharts `<iframe>` widgets; `docx_renderer.py`/`pptx_renderer.py`/`xlsx_renderer.py` do template-faithful spec→file rendering.

**Unified pipeline** (`backend/app/pipeline/`) — the single production path (`run.py::run_unified_pipeline`), 7 phases:
`UNDERSTAND → PLAN → RESEARCH → SPEC_GEN → DOC_RENDER → QA → EXPORT` (phases in `pipeline/phases/`). UNDERSTAND runs Ingress + intent routing + DuckDB registration; RESEARCH invokes the knowledge triad; SPEC_GEN injects DuckDB schema / VFS tree / template placeholders. The legacy multi-agent, `simple_pipeline`, and `swarm` paths were retired.

**Services** (`backend/app/services/`):
- `rag_service.py` — embedding + vector search over uploaded documents
- `llm_service.py` — OpenAI-compatible LLM client (default: Ollama with `qwen2.5:72b`)
- `report_service.py` — entrypoint that launches `run_unified_pipeline`
- `orchestrator.py` — retained text/ORM helpers only (`add_message`, `build_source_grounded_draft`, …); no longer an agent engine
- `document_generator.py` — exports to PDF/DOCX
- `sandbox.py` — RestrictedPython execution for data analysis (timeout: `SANDBOX_TIMEOUT`)

**Agents** (`backend/app/agents/`): only `DataAnalystAgent` (Excel grounding), `OntologyAgent`, `SentimentAgent` remain — invoked as capabilities, not a pipeline.

**API routes** (`backend/app/api/`): `auth`, `reports`, `agents`, `knowledge_base`, `messages`, `dashboard`, `ws`, `files`, `system`, `ingress` (VFS upload/parse), `compute` (DuckDB / sandbox / widget), `ontology`, `sentiment`, `kb_coverage`, `official_sources`, `admin`.

**Data layer:** SQLite (`data/app.db`) via SQLAlchemy ORM + Alembic migrations. Skills are registered at startup via `register_all_skills()` in `backend/app/skills/`.

## Key Configuration (`backend/app/config.py` + `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DEFAULT_LLM_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama endpoint |
| `DEFAULT_LLM_MODEL` | `qwen2.5:72b` | LLM model name |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `ENABLE_EXTERNAL_SEARCH` | `false` | Must stay false for intranet |
| `ENABLE_BROWSER` | `false` | Playwright automation toggle |
| `DEFAULT_ADMIN_USERNAME/PASSWORD` | `admin` / `admin123456` | Auto-created on first run |
| `SANDBOX_TIMEOUT` | `30` | Seconds for code execution |

Auth uses JWT. `SECRET_KEY` is auto-generated on first `./dev.sh` run.
