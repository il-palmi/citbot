"""Esporta tutte le citazioni del database in un file JSON.

Genera una lista di oggetti {quote, author, context?}, lo stesso formato
accettato da import_quotes.py / dal comando !import.

Esempio:
    python export_quotes.py quotes_export.json
"""

import argparse
import asyncio
import json

from db import QuoteDB
from import_quotes import rows_to_entries


async def export_to_file(path: str) -> None:
    db = QuoteDB()
    await db.init()
    entries = rows_to_entries(await db.all())

    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"Esportate {len(entries)} citazioni in {path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Esporta le citazioni in un file JSON.")
    parser.add_argument("file", nargs="?", default="quotes_export.json", help="Percorso del file JSON di output")
    args = parser.parse_args()
    asyncio.run(export_to_file(args.file))


if __name__ == "__main__":
    main()
