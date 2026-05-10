from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.db import Base, engine
from app.seeds import seed_initial_data


def _ensure_dev_schema() -> None:
    """Lightweight safety net for additive schema changes during development.

    `create_all` only creates missing tables; it does not add new columns to
    existing tables. For prod we use Alembic, but in dev we want to avoid
    losing seeded data when adding a column. List additive columns here.
    """
    inspector = inspect(engine)
    additive_columns: list[tuple[str, str, str]] = [
        # (table, column, ddl-fragment)
        ("invite_tokens", "notified_at", "TIMESTAMP WITH TIME ZONE NULL"),
        ("events", "summerhouse_title", "VARCHAR(300) NULL"),
        ("events", "summerhouse_summary", "TEXT NULL"),
        ("events", "summerhouse_image_url", "VARCHAR(1000) NULL"),
        ("events", "summerhouse_scraped_at", "TIMESTAMP WITH TIME ZONE NULL"),
        ("users", "notify_email", "BOOLEAN NULL"),
        ("users", "notify_prompted_at", "TIMESTAMP WITH TIME ZONE NULL"),
        ("users", "last_read_chat_message_id", "INTEGER NOT NULL DEFAULT 0"),
        ("expense_categories", "is_utility", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in additive_columns:
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}'))


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Auto-create tables on first boot. Migrations are managed via Alembic for prod.
    Base.metadata.create_all(bind=engine)
    _ensure_dev_schema()
    seed_initial_data()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount("/uploads", StaticFiles(directory=str(settings.uploads_dir)), name="uploads")

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
