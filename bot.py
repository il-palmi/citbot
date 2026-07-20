import os

import discord
from discord.ext import commands

from db import QuoteDB

PREFIX = os.getenv("BOT_PREFIX", "!")
TOKEN = os.getenv("DISCORD_TOKEN")

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


@bot.command(name="remove", aliases=["rimuovi", "del"])
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
            f"`{PREFIX}remove <id>` — rimuove una citazione"
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
