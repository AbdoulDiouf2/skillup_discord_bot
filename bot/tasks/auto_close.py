import logging
from datetime import datetime

from discord.ext import tasks

from bot.config import TZ
from bot.db.database import get_connection
from bot.db.sessions_admin import close_stale_open_sessions

log = logging.getLogger("skillup")

INTERVALLE_VERIFICATION_MINUTES = 15


@tasks.loop(minutes=INTERVALLE_VERIFICATION_MINUTES)
async def auto_close_sessions():
    now = datetime.now(TZ)
    async with get_connection() as db:
        nb = await close_stale_open_sessions(db, now)
    if nb:
        log.info("Auto-clôture RG-16 : %d session(s) marquée(s) incomplète(s).", nb)
