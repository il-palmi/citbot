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

### 1. Crea l'applicazione e il bot

1. Vai su https://discord.com/developers/applications e clicca **New Application**,
   dai un nome (es. "Cit Bot") e conferma.
2. Nel menu a sinistra apri la sezione **Bot**.
   - Se non esiste già, clicca **Add Bot** / **Reset Token** e copia il **token**
     che appare (`DISCORD_TOKEN`). È un segreto: non committarlo, non condividerlo,
     va solo nel file `.env`. Se pensi sia stato esposto, rigeneralo dalla stessa
     pagina (**Reset Token**), invalida il precedente.
3. Sempre nella sezione **Bot**, in **Privileged Gateway Intents** abilita
   **MESSAGE CONTENT INTENT** e salva. Serve perché il bot deve leggere il testo
   dei messaggi per riconoscere i comandi (`!add`, `!random`, ...).

### 2. Invita il bot sul tuo server

1. Vai nella sezione **OAuth2 → URL Generator**.
2. In **Scopes** seleziona `bot`.
3. In **Bot Permissions** seleziona come minimo:
   - *Send Messages*
   - *Manage Messages* (serve a cancellare i comandi `add`/`remove`/`import`/`export`
     digitati per errore in un canale del server, invece che in DM)
   - *Embed Links* (le citazioni vengono mostrate come embed)
   - *Attach Files* (serve a `!import`/`!export` per allegare i file JSON)
4. Copia l'URL generato in fondo alla pagina, aprilo nel browser, scegli il server
   e conferma i permessi.
5. Nelle impostazioni del server, verifica che il ruolo del bot possa vedere e
   scrivere nei canali dove deve rispondere.

### 3. Recupera GUILD_ID e ADMIN_ROLE_ID

Questi due ID servono al bot per capire, quando `!add`/`!remove`/`!import`/`!export`
arrivano in DM, se chi scrive ha il ruolo giusto sul server (vedi sopra "Comandi").

1. In Discord, apri **Impostazioni utente → Avanzate** e abilita **Modalità
   sviluppatore**.
2. Clicca col tasto destro sul nome/icona del server → **Copia ID server** → è il
   tuo `GUILD_ID`.
3. Vai in **Impostazioni server → Ruoli**, individua (o crea) il ruolo da
   abilitare ai comandi di amministrazione, clicca col tasto destro → **Copia ID
   ruolo** → è il tuo `ADMIN_ROLE_ID`.
4. Assicurati che il tuo account Discord (e chiunque debba gestire le citazioni)
   abbia effettivamente quel ruolo assegnato sul server.

### 4. Configura le variabili d'ambiente

```bash
cp .env.example .env
```

Apri `.env` e compila:

| Variabile        | Obbligatoria | Descrizione |
|------------------|:---:|-------------|
| `DISCORD_TOKEN`  | sì  | Token del bot, dal passo 1. |
| `BOT_PREFIX`     | no  | Prefisso comandi, default `!`. |
| `GUILD_ID`       | sì* | ID del server, dal passo 3. |
| `ADMIN_ROLE_ID`  | sì* | ID del ruolo amministratore, dal passo 3. |

\* senza `GUILD_ID`/`ADMIN_ROLE_ID` il bot parte comunque, ma `add`/`remove`/`import`/`export`
resteranno bloccati con il messaggio "comando non disponibile", perché non può
verificare i ruoli.

A questo punto puoi avviare il bot con Docker Compose (sotto) o in locale.

## Avvio con Docker Compose

Con il file `.env` già compilato (vedi setup sopra):

```bash
docker compose up -d --build
docker compose logs -f    # per vedere i log; dovresti vedere "Connesso come ..."
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

Il bot legge la configurazione dalle variabili d'ambiente (non carica `.env` da solo),
quindi vanno esportate nella shell prima di avviarlo:

```bash
pip install -r requirements.txt

export DISCORD_TOKEN=il-tuo-token
export GUILD_ID=id-del-server         # opzionale, ma senza add/remove/import/export non funzionano
export ADMIN_ROLE_ID=id-del-ruolo     # opzionale, vedi sopra

python bot.py
```

In alternativa, se hai già compilato `.env`, puoi caricarlo nella shell corrente con
`set -a && source .env && set +a` (bash/zsh) prima di lanciare `python bot.py`.

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
