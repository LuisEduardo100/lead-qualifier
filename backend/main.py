import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy import text
from backend.database import init_db, migrate_db, SessionLocal, engine
from backend.models import AdminUser
from backend.auth import hash_password
from backend.config import get_settings
from backend.services.scheduler import start_scheduler, stop_scheduler
from backend.routers import webhooks, channels, leads, config_router, auth_router, campaigns
import os

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await migrate_db()
    async with engine.begin() as conn:
        for col, definition in [
            ("agent_paused", "INTEGER DEFAULT 0"),
            ("media_type", "TEXT"),
            ("media_url", "TEXT"),
        ]:
            try:
                if col == "agent_paused":
                    await conn.execute(text(f"ALTER TABLE leads ADD COLUMN {col} {definition}"))
                else:
                    await conn.execute(text(f"ALTER TABLE messages ADD COLUMN {col} {definition}"))
            except Exception:
                pass
    async with SessionLocal() as db:
        existing = (await db.execute(
            select(AdminUser).where(AdminUser.username == settings.admin_username)
        )).scalar_one_or_none()
        if not existing:
            db.add(AdminUser(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
            ))
            await db.commit()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Lead Qualifier", lifespan=lifespan)

app.include_router(auth_router.router)
app.include_router(webhooks.router)
app.include_router(channels.router)
app.include_router(leads.router)
app.include_router(config_router.router)
app.include_router(campaigns.router)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(frontend_path, "index.html"))

    @app.get("/{page}.html")
    async def serve_page(page: str):
        path = os.path.join(frontend_path, f"{page}.html")
        if os.path.exists(path):
            return FileResponse(path)
        return FileResponse(os.path.join(frontend_path, "index.html"))
