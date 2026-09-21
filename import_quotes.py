"""Importa citazioni in blocco da un file JSON o CSV nel database del bot.

Formato atteso, una lista di oggetti con:
    quote      (obbligatorio)
    author     (obbligatorio)
    context    (opzionale)
    created_at (opzionale)

Esempio:
    python import_quotes.py quotes.json
"""

import argparse
import asyncio
import csv
import io
import json
from pathlib import Path

from db import QuoteDB


def rows_to_entries(rows) -> list:
    """Converte righe del DB nel formato usato per JSON e CSV."""
    entries = []
    for row in rows:
        entry = {"quote": row["text"], "author": row["author"]}
        if row["context"]:
            entry["context"] = row["context"]
        if row["created_at"]:
            entry["created_at"] = row["created_at"]
        entries.append(entry)
    return entries


def parse_import_data(raw: bytes, filename: str) -> list[dict]:
    """Decodifica un file JSON o CSV nel formato comune dell'import."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Il file non è codificato in UTF-8.") from exc

    if Path(filename).suffix.lower() == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("Il CSV deve contenere una riga di intestazioni.")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        required = {"quote", "author"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(
                "Il CSV deve contenere le colonne: quote, author."
            )
        return [
            {key.strip(): (value.strip() if value is not None else None)
             for key, value in row.items() if key is not None}
            for row in reader
        ]

    try:
        entries = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Il file non è un JSON valido.") from exc
    if not isinstance(entries, list):
        raise ValueError("Il JSON deve essere una lista di citazioni.")
    return entries


async def import_entries(
    db: QuoteDB, entries: list, added_by: str = "import"
) -> tuple[int, int]:
    """Importa una lista di entry {quote, author, context?, created_at? secret?} già parsate. Ritorna (added, skipped)."""
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

        created_at = entry.get("created_at") or None
        secret = True if entry.get("secret") else False
        await db.add(text, author, context, added_by, secret=secret created_at=created_at)
        existing.add((text, author))
        added += 1

    return added, skipped


async def import_from_file(path: str) -> None:
    with open(path, "rb") as f:
        entries = parse_import_data(f.read(), path)
    added, skipped = await import_entries(QuoteDB(), entries)
    print(f"Importate {added} citazioni, saltate {skipped} (duplicate o non valide).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa citazioni da un file JSON o CSV.")
    parser.add_argument(
        "file", nargs="?", default="quotes.json", help="Percorso del file JSON"
    )
    args = parser.parse_args()
    asyncio.run(import_from_file(args.file))


if __name__ == "__main__":
    main()
