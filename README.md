# Bot Discord Citazioni

Bot per raccogliere e consultare citazioni, con database SQLite e deploy via Docker.

## Comandi

**Solo in chat privata (DM) con il bot:**
- `!add testo | autore | contesto` — aggiunge una citazione (il contesto è opzionale)
- `!remove <id>` — rimuove una citazione per ID
- `!import` (con un file JSON allegato al messaggio) — importa citazioni in blocco
- `!export` — esporta tutte le citazioni in un file JSON (stesso formato di `!import`)

**Ovunque (canali del server e DM):**
- `!random` — una citazione a caso
- `!author <nome>` — filtra per autore
- `!search <parola>` — cerca per parola chiave (testo, autore o contesto)
- `!help` — riepilogo comandi

Se qualcuno prova `add`/`remove` su un canale del server, il bot cancella il messaggio
e invita a usare la chat privata.

`add`/`remove` sono riservati a chi ha il ruolo `ADMIN_ROLE_ID` sul server `GUILD_ID`
(vedi `.env.example`): il bot recupera il membro dal server anche se il comando
arriva in DM, per poterne controllare i ruoli.

## Setup del bot su Discord

1. Vai su https://discord.com/developers/applications → **New Application**.
2. Sezione **Bot** → crea il bot e copia il **token**.
3. Abilita **MESSAGE CONTENT INTENT** (serve per leggere i comandi).
4. Sezione **OAuth2 → URL Generator**: scope `bot`, permessi
   *Send Messages*, *Manage Messages*, *Embed Links*. Usa l'URL per invitarlo.

## Avvio con Docker Compose

```bash
cp .env.example .env      # inserisci DISCORD_TOKEN, GUILD_ID, ADMIN_ROLE_ID
docker compose up -d --build
docker compose logs -f    # per vedere i log
```

### Dati persistenti

Il `docker-compose.yml` monta la cartella `./data` (accanto al file compose, sull'host)
su `/data` nel container, dove il bot scrive `quotes.db` (percorso impostato da
`DB_PATH=/data/quotes.db`). Essendo un bind mount su una cartella reale dell'host —
non un volume Docker anonimo — il database:

- sopravvive a `docker compose down` / `up`, restart e ricreazioni del container;
- è visibile e modificabile direttamente dall'host in `./data/quotes.db`;
- va incluso nei backup (basta copiare la cartella `data/`).

La cartella `data/` viene creata automaticamente al primo avvio; se vuoi usare un
altro percorso, cambia il mount in `docker-compose.yml` (es. `/mnt/backup/citbot:/data`).

Per fermare il bot mantenendo i dati:

```bash
docker compose down       # i dati restano in ./data
```

Per importare le citazioni iniziali (es. `quotes.json`) dentro al container già in
esecuzione:

```bash
docker compose cp quotes.json quote-bot:/app/quotes.json
docker compose exec quote-bot python import_quotes.py /app/quotes.json
```

## Avvio locale (senza Docker)

```bash
pip install -r requirements.txt
export DISCORD_TOKEN=il-tuo-token
python bot.py
```

## Formato del comando `add`

I campi sono separati da `|`:

```
!add La vita è ciò che ti accade mentre sei impegnato a fare altri piani | John Lennon | intervista, 1980
```

- **testo** e **autore** sono obbligatori
- **contesto** è opzionale (puoi ometterlo insieme al secondo `|`)

## Import in blocco da JSON

Per importare tante citazioni insieme (es. da `quotes.json`), ogni oggetto deve avere
`quote` e `author` obbligatori e `context` opzionale:

```json
[
  { "quote": "...", "author": "...", "context": "..." },
  { "quote": "...", "author": "..." }
]
```

Due modi:

- **Da Discord**: manda in DM al bot `!import` con il file JSON allegato (richiede
  il ruolo di amministrazione, vedi sopra).
- **Da terminale**: `python import_quotes.py quotes.json`

Le citazioni già presenti (stesso testo e autore) vengono saltate, quindi si può
rilanciare l'import in sicurezza.

## Export in blocco su JSON

Genera lo stesso formato usato per l'import, quindi il file esportato può essere
riutilizzato direttamente per un import (es. su un'altra istanza del bot):

- **Da Discord**: manda in DM al bot `!export` (richiede il ruolo di
  amministrazione), che risponde con il file `quotes_export.json` allegato.
- **Da terminale**: `python export_quotes.py quotes_export.json`
