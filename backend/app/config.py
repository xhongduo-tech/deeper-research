import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://dataagent:dataagent@localhost:5432/dataagent"
    database_type: str = "postgresql"       # sqlite | postgresql
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-this-in-production"
    upload_dir: str = str(BASE_DIR / "uploads")
    template_dir: str = str(BASE_DIR / "templates")
    sandbox_workspace: str = str(BASE_DIR / "sandbox_workspace")
    data_dir: str = str(Path("./data"))
    user_skills_dir: str = str(Path("./data/user_skills"))
    kb_data_path: str = str(Path("./data/kb_sources"))

    # ── LLM / Embedding (external compute server) ───────────────────────────
    default_llm_base_url: str = "http://localhost:11434/v1"
    default_llm_model: str = "qwen2.5:72b"
    default_llm_api_key: str = "ollama"

    # Optional per-tier model overrides (fall back to default_llm_* when unset)
    light_llm_base_url: str = ""
    light_llm_model: str = ""
    heavy_llm_base_url: str = ""
    heavy_llm_model: str = ""

    # ── Embedding API (external compute server, OpenAI-compatible) ──────────
    embed_base_url: str = ""                # e.g. http://compute-server:8000/v1
    embed_api_key: str = ""
    embed_model: str = "bge-m3"             # 1024-dim
    embed_batch_size: int = 64              # chunks per API call
    embed_max_retries: int = 3
    embed_retry_delay: float = 2.0
    embed_request_timeout: int = 60

    # ── Vector Store ────────────────────────────────────────────────────────
    vector_store_type: str = "qdrant"       # sqlite | qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "kb_chunks"
    qdrant_api_key: str = ""

    # ── Admin ───────────────────────────────────────────────────────────────
    default_admin_username: str = "admin"
    default_admin_password: str = "730926"
    admin_password_aliases: str = "730926,740419"

    # ── Intranet / Air-gapped Deployment Flags ──────────────────────────────
    enable_external_search: bool = False
    enable_browser: bool = False
    sandbox_timeout: int = 30
    max_workers: int = 10

    # ── RAG / Knowledge Base ────────────────────────────────────────────────
    rag_chunk_size: int = 2000              # chars per chunk (was 400)
    rag_chunk_overlap: int = 200            # overlap between chunks
    rag_top_k: int = 10                     # default retrieval count
    rag_score_threshold: float = 0.15

    # ── JWT ─────────────────────────────────────────────────────────────────
    access_token_expire_minutes: int = 60 * 8

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
