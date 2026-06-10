import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# ── Database engine setup ────────────────────────────────────────────────────

database_type = settings.database_type.lower()
database_url = settings.database_url

if database_type == "sqlite":
    # SQLite: ensure aiosqlite driver
    if database_url.startswith("sqlite:///") and "aiosqlite" not in database_url:
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    logger.info("[database] Using SQLite: %s", database_url)

elif database_type == "postgresql":
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    logger.info("[database] Using PostgreSQL: %s", database_url)

else:
    raise ValueError(f"Unsupported DATABASE_TYPE: {database_type}. Use 'sqlite' or 'postgresql'.")

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Lightweight migrations (SQLite only; PostgreSQL uses Alembic) ───────────

async def run_migrations():
    """
    Lightweight additive migrations for SQLite.
    PostgreSQL should use Alembic for schema management.
    """
    if database_type != "sqlite":
        logger.info("[migration] PostgreSQL mode — skipping lightweight migrations (use Alembic)")
        return

    migrations = [
        ("users", "auth_id", "VARCHAR(50)"),
        ("users", "department", "VARCHAR(100) DEFAULT ''"),
        ("users", "scene", "VARCHAR(200) DEFAULT ''"),
        ("users", "description", "VARCHAR(500) DEFAULT ''"),
    ]
    async with engine.begin() as conn:
        for table, column, col_def in migrations:
            try:
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                cols = {row[1] for row in result.fetchall()}
                if column not in cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                    )
                    logger.info("[migration] Added column %s.%s", table, column)
            except Exception as e:
                logger.warning("[migration] Skipped %s.%s: %s", table, column, e)

        # Backfill auth_id = username for rows where auth_id is NULL
        try:
            await conn.execute(
                text("UPDATE users SET auth_id = username WHERE auth_id IS NULL OR auth_id = ''")
            )
        except Exception as e:
            logger.warning("[migration] auth_id backfill skipped: %s", e)

        ontology_migrations = [
            ("ontology_nodes", "report_id", "INTEGER"),
            ("ontology_edges", "direction", "VARCHAR(20) DEFAULT 'directed'"),
            ("sentiment_records", "report_id", "INTEGER"),
            ("opinion_profiles", "report_id", "INTEGER"),
        ]
        for table, column, col_def in ontology_migrations:
            try:
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                cols = {row[1] for row in result.fetchall()}
                if column not in cols:
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                    )
                    logger.info("[migration] Added column %s.%s", table, column)
            except Exception as e:
                logger.warning("[migration] Skipped %s.%s: %s", table, column, e)

        # ── Project dimension migrations ──────────────────────────────────────
        try:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(200) NOT NULL,
                    description TEXT DEFAULT '',
                    owner_id INTEGER REFERENCES users(id),
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            logger.info("[migration] Ensured projects table exists")
        except Exception as e:
            logger.warning("[migration] projects table creation skipped: %s", e)

        try:
            result = await conn.execute(text("PRAGMA table_info(knowledge_bases)"))
            cols = {row[1] for row in result.fetchall()}
            if "project_id" not in cols:
                await conn.execute(
                    text("ALTER TABLE knowledge_bases ADD COLUMN project_id INTEGER REFERENCES projects(id)")
                )
                logger.info("[migration] Added column knowledge_bases.project_id")
        except Exception as e:
            logger.warning("[migration] Skipped knowledge_bases.project_id: %s", e)
