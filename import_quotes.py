"""Importa citazioni in blocco da un file JSON nel database del bot.

Formato atteso, una lista di oggetti con:
    quote      (obbligatorio)
    author     (obbligatorio)
    context    (opzionale)

Esempio:
    python import_quotes.py quotes.json
"""

import argparse
import asyncio
import json

from db import QuoteDB


def rows_to_entries(rows) -> list:
    """Converte righe del DB nello stesso formato {quote, author, context?} usato per l'import."""
    entries = []
    for row in rows:
        entry = {"quote": row["text"], "author": row["author"]}
        if row["context"]:
            entry["context"] = row["context"]
        entries.append(entry)
    return entries


async def import_entries(
    db: QuoteDB, entries: list, added_by: str = "import"
) -> tuple[int, int]:
    """Importa una lista di entry {quote, author, context?} già parsate. Ritorna (added, skipped)."""
    await db.init()
    existing = await db.all_pairs()

    added = skipped = 0
    for entry in entries:
        text = (entry.get("quote") or "").strip()
        author = (entry.get("author") or "").strip()
        context = entry.get("context") or None
        if isinstance(context, str):
            context = context.strip() or None

        if not text or not author or (text, author) in existing:
            skipped += 1
            continue

        await db.add(text, author, context, added_by)
        existing.add((text, author))
        added += 1

    return added, skipped


async def import_from_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)

    added, skipped = await import_entries(QuoteDB(), entries)
    print(f"Importate {added} citazioni, saltate {skipped} (duplicate o non valide).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa citazioni da un file JSON.")
    parser.add_argument(
        "file", nargs="?", default="quotes.json", help="Percorso del file JSON"
    )
    args = parser.parse_args()
    asyncio.run(import_from_file(args.file))


if __name__ == "__main__":
    main()
