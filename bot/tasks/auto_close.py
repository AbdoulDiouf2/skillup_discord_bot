import logging
from datetime import datetime, time

from discord.ext import tasks

from bot.config import TZ
from bot.db.database import get_connection
from bot.db.sessions_admin import close_stale_open_sessions

log = logging.getLogger("skillup")

MINUIT = time(hour=0, minute=0, tzinfo=TZ)


@tasks.loop(time=MINUIT)
async def auto_close_sessions():
    now = datetime.now(TZ)
    async with get_connection() as db:
        nb = await close_stale_open_sessions(db, now)
    if nb:
        log.info("Auto-clôture RG-16 : %d session(s) marquée(s) incomplète(s).", nb)
