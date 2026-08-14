from pathlib import Path

import asyncpg

from bot.config import DATABASE_URL

_SCHEMA_PATH = Path(__file__).parent / "schema_postgres.sql"

_pool: asyncpg.Pool | None = None


async def _get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _translate(sql: str) -> str:
    """Convertit les placeholders `?` (style sqlite) en `$1, $2, ...` (style asyncpg)."""
    parts = sql.split("?")
    out = parts[0]
    for i, part in enumerate(parts[1:], start=1):
        out += f"${i}" + part
    return out


class Cursor:
    """Résultat d'une exécution, compatible avec l'API attendue de aiosqlite.Cursor."""

    def __init__(self, rows: list | None = None, lastrowid=None, rowcount: int = 0):
        self._rows = rows or []
        self._idx = 0
        self.lastrowid = lastrowid
        self.rowcount = rowcount

    async def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    async def fetchall(self):
        rows = self._rows[self._idx :]
        self._idx = len(self._rows)
        return rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Execute:
    """Awaitable ET context manager, comme `aiosqlite.Connection.execute`."""

    def __init__(self, conn: asyncpg.Connection, sql: str, params):
        self._conn = conn
        self._sql = sql
        self._params = tuple(params) if params else ()

    async def _run(self) -> Cursor:
        sql = _translate(self._sql)
        stripped = sql.lstrip().upper()

        if stripped.startswith("SELECT"):
            rows = await self._conn.fetch(sql, *self._params)
            return Cursor(rows=rows)

        if stripped.startswith("INSERT") and "RETURNING" not in stripped:
            row = await self._conn.fetchrow(sql + " RETURNING id", *self._params)
            return Cursor(lastrowid=row["id"] if row else None, rowcount=1)

        status = await self._conn.execute(sql, *self._params)
        last_token = status.split()[-1] if status else "0"
        rowcount = int(last_token) if last_token.isdigit() else 0
        return Cursor(rowcount=rowcount)

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self) -> Cursor:
        self._cursor = await self._run()
        return self._cursor

    async def __aexit__(self, *exc):
        return False


class Connection:
    """Enveloppe une connexion asyncpg avec l'API `aiosqlite.Connection` utilisée
    par le reste du bot (execute/commit/executescript/row_factory)."""

    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn
        self.row_factory = None  # compat no-op — asyncpg.Record supporte déjà row["col"]

    def execute(self, sql: str, params=()) -> _Execute:
        return _Execute(self._conn, sql, params)

    async def executescript(self, sql: str) -> None:
        await self._conn.execute(sql)

    async def commit(self) -> None:
        pass  # asyncpg valide chaque instruction immédiatement (pas de transaction implicite)


class _ConnectionCtx:
    async def __aenter__(self) -> Connection:
        pool = await _get_pool()
        self._raw = await pool.acquire()
        return Connection(self._raw)

    async def __aexit__(self, *exc):
        pool = await _get_pool()
        await pool.release(self._raw)
        return False


async def init_db() -> None:
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    pool = await _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)


def get_connection() -> _ConnectionCtx:
    """Retourne une connexion prête à l'emploi (à utiliser avec `async with`)."""
    return _ConnectionCtx()
