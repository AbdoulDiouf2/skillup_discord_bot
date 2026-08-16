from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import discord_client
from api.routers import admin as admin_router
from api.routers import journal as journal_router
from api.routers import vagues as vagues_router
from bot.db.database import close_pool, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    discord_client.init_http_client()
    yield
    await discord_client.close_http_client()
    await close_pool()


app = FastAPI(title="SkillUp API", lifespan=lifespan)
app.include_router(journal_router.router)
app.include_router(vagues_router.router)
app.include_router(admin_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
