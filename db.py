import os
from pathlib import Path

import aiosqlite

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).parent / "data" / "quotes.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    author     TEXT NOT NULL,
    context    TEXT,
    added_by   TEXT,
    secret     INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class QuoteDB:
    """Piccolo wrapper asincrono attorno a SQLite per le citazioni."""

    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(SCHEMA)
            cur = await db.execute("PRAGMA table_info(quotes)")
            columns = {row[1] for row in await cur.fetchall()}
            if "secret" not in columns:
                await db.execute("ALTER TABLE quotes ADD COLUMN secret INTEGER NOT NULL DEFAULT 0")
            await db.commit()

    async def add(
        self,
        text: str,
        author: str,
        context: str | None,
        added_by: str,
        secret: bool = False,
    ) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO quotes (text, author, context, added_by, secret) VALUES (?, ?, ?, ?, ?)",
                (text, author, context, added_by, int(secret)),
            )
            await db.commit()
            return cur.lastrowid

    async def remove(self, quote_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
            await db.commit()
            return cur.rowcount > 0

    async def remove_secret(self, quote_id: int) -> bool:
        """Rimuove una citazione solo se è segreta (evita di cancellare per sbaglio citazioni pubbliche)."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "DELETE FROM quotes WHERE id = ? AND secret = 1", (quote_id,)
            )
            await db.commit()
            return cur.rowcount > 0

    async def get(self, quote_id: int) -> aiosqlite.Row | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
            return await cur.fetchone()

    async def random(self, include_secret: bool = False) -> aiosqlite.Row | None:
        query = "SELECT * FROM quotes"
        if not include_secret:
            query += " WHERE secret = 0"
        query += " ORDER BY RANDOM() LIMIT 1"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query)
            return await cur.fetchone()

    async def random_secret(self) -> aiosqlite.Row | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM quotes WHERE secret = 1 ORDER BY RANDOM() LIMIT 1"
            )
            return await cur.fetchone()

    async def by_author(
        self, author: str, include_secret: bool = False, limit: int = 25
    ) -> list[aiosqlite.Row]:
        query = "SELECT * FROM quotes WHERE author LIKE ?"
        if not include_secret:
            query += " AND secret = 0"
        query += " ORDER BY id LIMIT ?"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (f"%{author}%", limit))
            return await cur.fetchall()

    async def search(
        self, keyword: str, include_secret: bool = False, limit: int = 25
    ) -> list[aiosqlite.Row]:
        like = f"%{keyword}%"
        query = "SELECT * FROM quotes WHERE (text LIKE ? OR author LIKE ? OR context LIKE ?)"
        if not include_secret:
            query += " AND secret = 0"
        query += " ORDER BY id LIMIT ?"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (like, like, like, limit))
            return await cur.fetchall()

    async def all(self) -> list[aiosqlite.Row]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM quotes ORDER BY id")
            return await cur.fetchall()

    async def all_pairs(self) -> set[tuple[str, str]]:
        """Coppie (text, author) già presenti, usate per evitare duplicati in import."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT text, author FROM quotes")
            rows = await cur.fetchall()
            return {(t, a) for t, a in rows}

    async def count(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM quotes")
            (n,) = await cur.fetchone()
            return n
