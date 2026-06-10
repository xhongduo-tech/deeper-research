import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import engine, async_session, Base, run_migrations
from app import models  # noqa: F401
from app.api import auth, reports, agents, files, messages, system, ws, dashboard, prompt_skills, chat
from app.api import admin
from app.api import knowledge_base
from app.api import ingress as ingress_api
from app.api import compute as compute_api
from app.api import admin_bulk
from app.api import ontology, sentiment
from app.api import html_report
from app.api import official_sources
from app.api import admin_datasources
from app.api import kb_coverage
from app.api import projects as projects_api
from app.services.auth_service import ensure_admin_user
from app.skills import register_all_skills

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure data directories and admin user
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.template_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.sandbox_workspace).mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await run_migrations()

    async with async_session() as db:
        await ensure_admin_user(db)
        # Load persisted admin config into runtime LLM override
        from sqlalchemy import select
        from app.models.system_config import SystemConfig
        from app.services.llm_service import apply_runtime_config
        rows = (await db.execute(select(SystemConfig))).scalars().all()
        apply_runtime_config({r.key: r.value for r in rows})

    async with async_session() as db:
        from app.services.datasource_registry import init_official_sources
        await init_official_sources(db)

    async with async_session() as db:
        from app.services.offline_seeder import seed_offline_data
        await seed_offline_data(db)

    register_all_skills()
    logger.info("DataAgent Studio backend started")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("DataAgent Studio backend shut down")


app = FastAPI(
    title="DataAgent Studio API",
    description="深度研究报告生产系统 - 多智能体平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(agents.router)
app.include_router(files.router)
app.include_router(messages.router)
app.include_router(chat.router)
app.include_router(system.router)
app.include_router(ws.router)
app.include_router(knowledge_base.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(prompt_skills.router)
app.include_router(ontology.router)
app.include_router(sentiment.router)
app.include_router(html_report.router)
app.include_router(official_sources.router)
app.include_router(admin_datasources.router)
app.include_router(kb_coverage.router)
app.include_router(ingress_api.router)
app.include_router(compute_api.router)
app.include_router(admin_bulk.router)
app.include_router(projects_api.router)
