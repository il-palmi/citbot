# Bot Discord Citazioni

Bot per raccogliere e consultare citazioni, con database SQLite e deploy via Docker.

## Comandi

**Solo in chat privata (DM) con il bot:**
- `!add testo | autore | contesto` — aggiunge una citazione (il contesto è opzionale)
- `!remove <id>` — rimuove una citazione per ID

**Ovunque (canali del server e DM):**
- `!random` — una citazione a caso
- `!author <nome>` — filtra per autore
- `!search <parola>` — cerca per parola chiave (testo, autore o contesto)
- `!help` — riepilogo comandi

Se qualcuno prova `add`/`remove` su un canale del server, il bot cancella il messaggio
e invita a usare la chat privata.

## Setup del bot su Discord

1. Vai su https://discord.com/developers/applications → **New Application**.
2. Sezione **Bot** → crea il bot e copia il **token**.
3. Abilita **MESSAGE CONTENT INTENT** (serve per leggere i comandi).
4. Sezione **OAuth2 → URL Generator**: scope `bot`, permessi
   *Send Messages*, *Manage Messages*, *Embed Links*. Usa l'URL per invitarlo.

## Avvio con Docker Compose

```bash
cp .env.example .env      # inserisci il tuo DISCORD_TOKEN
docker compose up -d --build
docker compose logs -f    # per vedere i log
```

Il database viene salvato nel volume `quote-data` e sopravvive ai riavvii.

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
