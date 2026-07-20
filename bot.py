import io
import json
import os

import discord
from discord.ext import commands

from db import QuoteDB
from import_quotes import import_entries, rows_to_entries

PREFIX = os.getenv("BOT_PREFIX", "!")
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID") or 0) or None
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID") or 0) or None

intents = discord.Intents.default()
intents.message_content = True  # richiesto per leggere il testo dei comandi

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
db = QuoteDB()


# --------------------------------------------------------------------------- #
# Check: alcuni comandi possono essere usati SOLO in chat privata (DM)
# --------------------------------------------------------------------------- #
def dm_only():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is not None:
            raise commands.CheckFailure("dm_only")
        return True

    return commands.check(predicate)


# --------------------------------------------------------------------------- #
# Check: comandi di amministrazione, riservati a chi ha il ruolo ADMIN_ROLE_ID
# sul server GUILD_ID. Serve a recuperare il Member (e quindi i suoi ruoli)
# anche quando il comando arriva in DM, dove Discord non fornisce i ruoli.
# --------------------------------------------------------------------------- #
def admin_only():
    async def predicate(ctx: commands.Context) -> bool:
        if GUILD_ID is None or ADMIN_ROLE_ID is None:
            raise commands.CheckFailure("admin_not_configured")

        guild = ctx.bot.get_guild(GUILD_ID)
        if guild is None:
            raise commands.CheckFailure("admin_not_configured")

        member = guild.get_member(ctx.author.id)
        if member is None:
            try:
                member = await guild.fetch_member(ctx.author.id)
            except discord.NotFound:
                raise commands.CheckFailure("admin_missing_role")

        if not any(role.id == ADMIN_ROLE_ID for role in member.roles):
            raise commands.CheckFailure("admin_missing_role")
        return True

    return commands.check(predicate)


def quote_embed(row) -> discord.Embed:
    embed = discord.Embed(
        description=f"“{row['text']}”",
        color=discord.Color.blurple(),
    )
    embed.set_author(name=row["author"])
    if row["context"]:
        embed.add_field(name="Contesto", value=row["context"], inline=False)
    embed.set_footer(text=f"Citazione #{row['id']}")
    return embed


# --------------------------------------------------------------------------- #
# Comandi SOLO in DM: aggiungere / rimuovere
# --------------------------------------------------------------------------- #
@bot.command(name="add", aliases=["aggiungi"])
@admin_only()
@dm_only()
async def add_quote(ctx: commands.Context, *, payload: str = ""):
    """Aggiunge una citazione. Formato: testo | autore | contesto(opzionale)"""
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await ctx.send(
            "Formato non valido.\n"
            f"Usa: `{PREFIX}add testo della citazione | autore | contesto (opzionale)`"
        )
        return

    text, author = parts[0], parts[1]
    context = parts[2] if len(parts) >= 3 and parts[2] else None
    qid = await db.add(text, author, context, str(ctx.author))
    await ctx.send(f"✅ Citazione **#{qid}** aggiunta.")


@bot.command(name="import", aliases=["importa"])
@admin_only()
@dm_only()
async def import_quotes(ctx: commands.Context):
    """Importa citazioni in blocco da un file JSON allegato al messaggio."""
    if not ctx.message.attachments:
        await ctx.send(
            "Allega un file JSON con una lista di `{quote, author, context(opzionale)}`."
        )
        return

    attachment = ctx.message.attachments[0]
    try:
        raw = await attachment.read()
        entries = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        await ctx.send("Il file allegato non è un JSON valido.")
        return

    if not isinstance(entries, list):
        await ctx.send("Il JSON deve essere una lista di citazioni.")
        return

    added, skipped = await import_entries(db, entries, str(ctx.author))
    await ctx.send(f"✅ Importate **{added}** citazioni, saltate **{skipped}**.")


@bot.command(name="export", aliases=["esporta"])
@admin_only()
@dm_only()
async def export_quotes(ctx: commands.Context):
    """Esporta tutte le citazioni in un file JSON, nello stesso formato usato da !import."""
    entries = rows_to_entries(await db.all())
    data = json.dumps(entries, ensure_ascii=False, indent=2).encode("utf-8")
    await ctx.send(
        f"📤 Esportate **{len(entries)}** citazioni.",
        file=discord.File(io.BytesIO(data), filename="quotes_export.json"),
    )


@bot.command(name="remove", aliases=["rimuovi", "del"])
@admin_only()
@dm_only()
async def remove_quote(ctx: commands.Context, quote_id: int):
    """Rimuove una citazione per ID."""
    ok = await db.remove(quote_id)
    if ok:
        await ctx.send(f"🗑️ Citazione **#{quote_id}** rimossa.")
    else:
        await ctx.send(f"Nessuna citazione con ID **#{quote_id}**.")


# --------------------------------------------------------------------------- #
# Comandi disponibili OVUNQUE (server e DM): consultazione
# --------------------------------------------------------------------------- #
@bot.command(name="random", aliases=["caso", "rand"])
async def random_quote(ctx: commands.Context):
    """Restituisce una citazione a caso."""
    row = await db.random()
    if row is None:
        await ctx.send("Non c'è ancora nessuna citazione. Aggiungine una in privato!")
        return
    await ctx.send(embed=quote_embed(row))


@bot.command(name="author", aliases=["autore"])
async def by_author(ctx: commands.Context, *, author: str = ""):
    """Filtra le citazioni per autore."""
    if not author.strip():
        await ctx.send(f"Uso: `{PREFIX}author nome autore`")
        return
    rows = await db.by_author(author.strip())
    if not rows:
        await ctx.send(f"Nessuna citazione trovata per autore «{author}».")
        return
    await _send_list(ctx, rows, f"Citazioni di «{author}»")


@bot.command(name="search", aliases=["cerca"])
async def search(ctx: commands.Context, *, keyword: str = ""):
    """Cerca per parola chiave in testo, autore o contesto."""
    if not keyword.strip():
        await ctx.send(f"Uso: `{PREFIX}search parola chiave`")
        return
    rows = await db.search(keyword.strip())
    if not rows:
        await ctx.send(f"Nessun risultato per «{keyword}».")
        return
    await _send_list(ctx, rows, f"Risultati per «{keyword}»")


async def _send_list(ctx: commands.Context, rows, title: str):
    """Invia una lista compatta; se è un solo risultato usa l'embed completo."""
    if len(rows) == 1:
        await ctx.send(embed=quote_embed(rows[0]))
        return
    embed = discord.Embed(title=title, color=discord.Color.blurple())
    for row in rows[:25]:
        snippet = row["text"] if len(row["text"]) <= 200 else row["text"][:197] + "…"
        embed.add_field(
            name=f"#{row['id']} — {row['author']}",
            value=f"“{snippet}”",
            inline=False,
        )
    if len(rows) > 25:
        embed.set_footer(text=f"Mostrati i primi 25 di {len(rows)} risultati.")
    await ctx.send(embed=embed)


@bot.command(name="help", aliases=["aiuto"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Bot Citazioni", color=discord.Color.green())
    embed.add_field(
        name="Solo in chat privata (DM)",
        value=(
            f"`{PREFIX}add testo | autore | contesto` — aggiunge una citazione\n"
            f"`{PREFIX}remove <id>` — rimuove una citazione\n"
            f"`{PREFIX}import` (con file JSON allegato) — importa citazioni in blocco\n"
            f"`{PREFIX}export` — esporta tutte le citazioni in un file JSON"
        ),
        inline=False,
    )
    embed.add_field(
        name="Ovunque (server e DM)",
        value=(
            f"`{PREFIX}random` — una citazione a caso\n"
            f"`{PREFIX}author <nome>` — filtra per autore\n"
            f"`{PREFIX}search <parola>` — cerca per parola chiave"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


# --------------------------------------------------------------------------- #
# Gestione errori
# --------------------------------------------------------------------------- #
@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure) and str(error) == "dm_only":
        try:
            await ctx.message.delete()  # nasconde il comando dal canale pubblico
        except (discord.Forbidden, discord.NotFound):
            pass
        await ctx.send(
            f"{ctx.author.mention} questo comando va usato **in chat privata** con il bot, "
            "non sui canali del server.",
            delete_after=10,
        )
    elif isinstance(error, commands.CheckFailure) and str(error) == "admin_missing_role":
        await ctx.send("Non hai il ruolo necessario per usare questo comando.")
    elif isinstance(error, commands.CheckFailure) and str(error) == "admin_not_configured":
        await ctx.send(
            "Comando non disponibile: il bot non ha GUILD_ID/ADMIN_ROLE_ID configurati."
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Manca un argomento. Prova `{PREFIX}help`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Argomento non valido (l'ID dev'essere un numero).")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        raise error


@bot.event
async def on_ready():
    await db.init()
    total = await db.count()
    print(f"Connesso come {bot.user} — {total} citazioni nel database.")


def main():
    if not TOKEN:
        raise SystemExit("Variabile d'ambiente DISCORD_TOKEN mancante.")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
