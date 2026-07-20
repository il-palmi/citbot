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
            await db.commit()

    async def add(self, text: str, author: str, context: str | None, added_by: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO quotes (text, author, context, added_by) VALUES (?, ?, ?, ?)",
                (text, author, context, added_by),
            )
            await db.commit()
            return cur.lastrowid

    async def remove(self, quote_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))
            await db.commit()
            return cur.rowcount > 0

    async def get(self, quote_id: int) -> aiosqlite.Row | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
            return await cur.fetchone()

    async def random(self) -> aiosqlite.Row | None:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM quotes ORDER BY RANDOM() LIMIT 1")
            return await cur.fetchone()

    async def by_author(self, author: str, limit: int = 25) -> list[aiosqlite.Row]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM quotes WHERE author LIKE ? ORDER BY id LIMIT ?",
                (f"%{author}%", limit),
            )
            return await cur.fetchall()

    async def search(self, keyword: str, limit: int = 25) -> list[aiosqlite.Row]:
        like = f"%{keyword}%"
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM quotes
                WHERE text LIKE ? OR author LIKE ? OR context LIKE ?
                ORDER BY id LIMIT ?
                """,
                (like, like, like, limit),
            )
            return await cur.fetchall()

    async def count(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM quotes")
            (n,) = await cur.fetchone()
            return n
