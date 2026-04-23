import json
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.database import init_db, AsyncSessionLocal

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - startup and shutdown."""
    # === STARTUP ===
    logger.info(f"Starting {settings.APP_NAME}...")

    # Create directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.TEMPLATE_DIR, exist_ok=True)
    os.makedirs(settings.SANDBOX_WORKSPACE, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "outputs"), exist_ok=True)

    # Initialize database tables
    await init_db()
    logger.info("Database tables initialized")

    # Create default admin user
    await _create_default_admin()
    logger.info("Default admin user checked")

    # Initialize default system configs
    await _init_system_configs()
    logger.info("System configs initialized")

    # Seed built-in Word templates
    try:
        from app.generators.builtin_templates import seed_builtin_templates
        async with AsyncSessionLocal() as db:
            await seed_builtin_templates(db, settings.TEMPLATE_DIR)
            await db.commit()
        logger.info("Built-in templates seeded")
    except Exception as e:
        logger.warning(f"Template seeding skipped: {e}")

    logger.info(f"{settings.APP_NAME} started successfully!")

    yield

    # === SHUTDOWN ===
    logger.info(f"Shutting down {settings.APP_NAME}...")


async def _create_default_admin():
    """Create default admin user if no users exist."""
    from app.models.user import User, UserRole
    from app.api.v1.auth import get_password_hash
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count_result = await db.execute(select(func.count(User.id)))
        count = count_result.scalar()

        if count == 0:
            admin_user = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                role=UserRole.admin.value,
            )
            db.add(admin_user)
            await db.commit()
            logger.info(
                f"Default admin user created: {settings.DEFAULT_ADMIN_USERNAME}"
            )


async def _init_system_configs():
    """Initialize default system configurations if not present."""
    from app.models.system_config import SystemConfig
    from sqlalchemy import select

    default_configs = {
        "enable_external_search": str(settings.ENABLE_EXTERNAL_SEARCH),
        "enable_browser": str(settings.ENABLE_BROWSER),
        "sandbox_timeout": str(settings.SANDBOX_TIMEOUT),
        "max_workers": str(settings.MAX_WORKERS),
        "default_llm_profile_id": "default",
        "llm_profiles": json.dumps([
            {
                "id": "default",
                "name": "默认模型",
                "base_url": settings.DEFAULT_LLM_BASE_URL,
                "model": settings.DEFAULT_LLM_MODEL,
                "api_key": settings.DEFAULT_LLM_API_KEY or "",
                "description": "系统初始化默认模型",
            }
        ], ensure_ascii=False),
        "default_llm_base_url": settings.DEFAULT_LLM_BASE_URL,
        "default_llm_model": settings.DEFAULT_LLM_MODEL,
        "embedding_base_url": settings.DEFAULT_LLM_BASE_URL,
        "embedding_model": "text-embedding-3-small",
        "embedding_api_key": settings.DEFAULT_LLM_API_KEY,
        "vector_store_enabled": "False",
        "kb_chunk_size": "1200",
        "kb_top_k": "12",
        "app_version": "1.0.0",
    }

    async with AsyncSessionLocal() as db:
        for key, value in default_configs.items():
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.key == key)
            )
            if not result.scalar_one_or_none():
                config = SystemConfig(key=key, value=value)
                db.add(config)
        await db.commit()


# Create the FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Multi-Agent AI Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware - allow all origins for internal deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
from app.api.v1 import (
    admin,
    auth,
    custom_report_types,
    developer,
    files,
    reports,
    subagents,
    workforce,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(reports.report_types_router, prefix="/api/v1")
app.include_router(custom_report_types.router, prefix="/api/v1")
app.include_router(workforce.router, prefix="/api/v1")
app.include_router(developer.router, prefix="/api/v1")
app.include_router(developer.admin_router, prefix="/api/v1")
app.include_router(subagents.router, prefix="/api/v1")

# Static file serving for uploaded files
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# Download endpoint for generated output files
@app.get("/api/v1/download/{filename}")
async def download_file(filename: str):
    """Download a generated output file."""
    # Security: only allow alphanumeric, dash, underscore, dot
    import re
    if not re.match(r'^[\w\-\.]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    output_dir = os.path.join(settings.UPLOAD_DIR, "outputs")
    file_path = os.path.join(output_dir, filename)

    if not os.path.exists(file_path):
        # Also check uploads dir
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

    # Determine media type
    if filename.endswith(".pptx"):
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    elif filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.endswith(".xlsx"):
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.DEBUG else "Internal server error",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
