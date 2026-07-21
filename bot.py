import io
import json
import os
import random

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


async def is_admin(ctx: commands.Context) -> bool:
    """Come admin_only(), ma restituisce un bool invece di sollevare un'eccezione."""
    if GUILD_ID is None or ADMIN_ROLE_ID is None:
        return False
    guild = ctx.bot.get_guild(GUILD_ID)
    if guild is None:
        return False
    member = guild.get_member(ctx.author.id)
    if member is None:
        try:
            member = await guild.fetch_member(ctx.author.id)
        except discord.NotFound:
            return False
    return any(role.id == ADMIN_ROLE_ID for role in member.roles)


async def can_see_secrets(ctx: commands.Context) -> bool:
    """Le citazioni segrete si vedono solo in DM e solo agli admin."""
    return ctx.guild is None and await is_admin(ctx)


def quote_embed(row) -> discord.Embed:
    embed = discord.Embed(
        description=f"“{row['text']}”",
        color=discord.Color.blurple(),
    )
    embed.set_author(name=row["author"])
    if row["context"]:
        embed.add_field(name="Contesto", value=row["context"], inline=False)
    footer = f"Citazione #{row['id']}"
    if row["secret"]:
        footer += " · 🔒 Segreta"
    embed.set_footer(text=footer)
    return embed


# --------------------------------------------------------------------------- #
# Comandi SOLO in DM: aggiungere / rimuovere
# --------------------------------------------------------------------------- #
@bot.command(name="add", aliases=["aggiungi", "asd"])
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


@bot.command(name="addsecret")
@admin_only()
@dm_only()
async def add_secret_quote(ctx: commands.Context, *, payload: str = ""):
    """Aggiunge una citazione segreta. Formato: testo | autore | contesto(opzionale)"""
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await ctx.send(
            "Formato non valido.\n"
            f"Usa: `{PREFIX}addsecret testo della citazione | autore | contesto (opzionale)`"
        )
        return

    text, author = parts[0], parts[1]
    context = parts[2] if len(parts) >= 3 and parts[2] else None
    qid = await db.add(text, author, context, str(ctx.author), secret=True)
    await ctx.send(f"🔒 Citazione segreta **#{qid}** aggiunta.")


@bot.command(name="removesecret")
@admin_only()
@dm_only()
async def remove_secret_quote(ctx: commands.Context, quote_id: int):
    """Rimuove una citazione segreta per ID."""
    ok = await db.remove_secret(quote_id)
    if ok:
        await ctx.send(f"🗑️ Citazione segreta **#{quote_id}** rimossa.")
    else:
        await ctx.send(f"Nessuna citazione segreta con ID **#{quote_id}**.")


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


@bot.command(name="randomsecret")
@admin_only()
@dm_only()
async def random_secret_quote(ctx: commands.Context):
    """Restituisce una citazione segreta a caso."""
    row = await db.random_secret()
    if row is None:
        await ctx.send("Non c'è ancora nessuna citazione segreta.")
        return
    await ctx.send(embed=quote_embed(row))


@bot.command(name="id")
async def by_id(ctx: commands.Context, quote_id: int):
    """Cerca una citazione per ID."""
    row = await db.get(quote_id)
    if row is None:
        await ctx.send(f"Nessuna citazione con ID **#{quote_id}**.")
        return
    if row["secret"] and not await can_see_secrets(ctx):
        await ctx.send("No questa è per pochi, mi dispiace, ahah xd.")
        return
    await ctx.send(embed=quote_embed(row))


@bot.command(name="author", aliases=["autore"])
async def by_author(ctx: commands.Context, *, author: str = ""):
    """Filtra le citazioni per autore."""
    if not author.strip():
        await ctx.send(f"Uso: `{PREFIX}author nome autore`")
        return
    include_secret = await can_see_secrets(ctx)
    rows = await db.by_author(author.strip(), include_secret=include_secret)
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
    include_secret = await can_see_secrets(ctx)
    rows = await db.search(keyword.strip(), include_secret=include_secret)
    if not rows:
        await ctx.send(f"Nessun risultato per «{keyword}».")
        return
    await _send_list(ctx, rows, f"Risultati per «{keyword}»")


@bot.command(name="stats", aliases=["statistiche"])
async def stats(ctx: commands.Context):
    """Conta quante citazioni ci sono per ogni autore (autori con '/' vengono separati)."""
    include_secret = await can_see_secrets(ctx)
    counts = await db.author_counts(include_secret=include_secret)
    if not counts:
        await ctx.send("Non c'è ancora nessuna citazione.")
        return

    page_size = 20
    chunks = [counts[i : i + page_size] for i in range(0, len(counts), page_size)]
    embeds = []
    for idx, chunk in enumerate(chunks):
        embed = discord.Embed(title="📊 Citazioni per autore", color=discord.Color.blurple())
        embed.description = "\n".join(f"**{author}** — {n}" for author, n in chunk)
        embed.set_footer(text=f"Pagina {idx + 1}/{len(chunks)} — {len(counts)} autori totali")
        embeds.append(embed)
    await _send_paginated(ctx, embeds)


async def _send_list(ctx: commands.Context, rows, title: str):
    """Invia una lista compatta, paginata se non ci sta tutta in un embed."""
    if len(rows) == 1:
        await ctx.send(embed=quote_embed(rows[0]))
        return

    page_size = 10
    chunks = [rows[i : i + page_size] for i in range(0, len(rows), page_size)]
    embeds = []
    for idx, chunk in enumerate(chunks):
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        for row in chunk:
            snippet = row["text"] if len(row["text"]) <= 200 else row["text"][:197] + "…"
            embed.add_field(
                name=f"#{row['id']} — {row['author']}",
                value=f"“{snippet}”",
                inline=False,
            )
        embed.set_footer(text=f"Pagina {idx + 1}/{len(chunks)} — {len(rows)} risultati totali")
        embeds.append(embed)
    await _send_paginated(ctx, embeds)


class PaginatorView(discord.ui.View):
    """Vista con pulsanti ◀ ▶ per scorrere una lista di embed già pronti."""

    def __init__(self, embeds: list[discord.Embed], author_id: int):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.author_id = author_id
        self.index = 0
        self.message: discord.Message | None = None
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.embeds) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


async def _send_paginated(ctx: commands.Context, embeds: list[discord.Embed]):
    """Invia il primo embed; se ce n'è più di uno, aggiunge i pulsanti di navigazione."""
    if len(embeds) == 1:
        await ctx.send(embed=embeds[0])
        return
    view = PaginatorView(embeds, ctx.author.id)
    view.message = await ctx.send(embed=embeds[0], view=view)


def _weighted_sample_without_replacement(
    names: list[str], weights: list[int], k: int
) -> list[str]:
    """Estrae fino a k nomi distinti con probabilità proporzionale al peso (stessa
    distribuzione usata da !stats), senza ripetizioni."""
    pool = list(zip(names, weights))
    chosen: list[str] = []
    while pool and len(chosen) < k:
        pool_names = [a for a, _ in pool]
        pool_weights = [w for _, w in pool]
        pick = random.choices(pool_names, weights=pool_weights, k=1)[0]
        chosen.append(pick)
        pool = [(a, w) for a, w in pool if a != pick]
    return chosen


def _weighted_distractor_combos(
    counts: list[tuple[str, int]], correct_authors: list[str], k: int, n: int
) -> list[list[str]]:
    """Genera fino a n combinazioni di k autori (senza autori ripetuti al loro interno),
    campionati con la distribuzione pesata di !stats, evitando di riproporre lo stesso
    gruppo di persone (né quello corretto né combinazioni già scelte)."""
    names = [a for a, _ in counts]
    weights = [c for _, c in counts]
    seen = {frozenset(correct_authors)}
    combos: list[list[str]] = []
    max_attempts = n * 20 + 20
    for _ in range(max_attempts):
        if len(combos) >= n:
            break
        combo = _weighted_sample_without_replacement(names, weights, k)
        if len(combo) < k:
            break  # non ci sono abbastanza autori distinti per formare un'altra combinazione
        group = frozenset(combo)
        if group in seen:
            continue
        seen.add(group)
        combos.append(combo)
    return combos


class GameView(discord.ui.View):
    def __init__(self, player_id: int, correct_author: str):
        super().__init__(timeout=60)
        self.player_id = player_id
        self.correct_author = correct_author
        self.answered = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.player_id

    async def _finish(self, interaction: discord.Interaction, chosen: str):
        self.answered = True
        for child in self.children:
            child.disabled = True
            if child.label == self.correct_author:
                child.style = discord.ButtonStyle.success
            elif child.label == chosen and chosen != self.correct_author:
                child.style = discord.ButtonStyle.danger
        self.stop()

        if chosen == self.correct_author:
            points = await db.add_point(str(self.player_id))
            await interaction.response.edit_message(
                content=f"✅ Esatto, l'autore era **{self.correct_author}**! Hai ora **{points}** punti.",
                view=self,
            )
        else:
            await interaction.response.edit_message(
                content=f"❌ Sbagliato, l'autore corretto era **{self.correct_author}**.",
                view=self,
            )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    def make_button(self, author: str) -> discord.ui.Button:
        button = discord.ui.Button(label=author, style=discord.ButtonStyle.primary)

        async def callback(interaction: discord.Interaction):
            await self._finish(interaction, author)

        button.callback = callback
        return button


@bot.command(name="game", aliases=["gioco"])
@dm_only()
async def game(ctx: commands.Context):
    """Indovina l'autore di una citazione a caso tra 4 proposti."""
    row = await db.random()
    if row is None:
        await ctx.send("Non c'è ancora nessuna citazione.")
        return

    correct_authors = [a.strip() for a in row["author"].split("/") if a.strip()]
    correct_label = "/".join(correct_authors)

    counts = await db.author_counts()
    distractor_combos = _weighted_distractor_combos(counts, correct_authors, len(correct_authors), 3)

    options = [correct_label] + ["/".join(combo) for combo in distractor_combos]
    random.shuffle(options)

    view = GameView(ctx.author.id, correct_label)
    for author in options:
        view.add_item(view.make_button(author))

    embed = discord.Embed(
        description=f"“{row['text']}”",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Chi è l'autore?")
    await ctx.send(embed=embed, view=view)


@bot.command(name="help", aliases=["aiuto"])
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(title="📖 Bot Citazioni", color=discord.Color.green())
    embed.add_field(
        name="Solo in chat privata (DM), solo admin",
        value=(
            f"`{PREFIX}add testo | autore | contesto` — aggiunge una citazione (alias `{PREFIX}asd`)\n"
            f"`{PREFIX}remove <id>` — rimuove una citazione\n"
            f"`{PREFIX}addsecret testo | autore | contesto` — aggiunge una citazione segreta\n"
            f"`{PREFIX}removesecret <id>` — rimuove una citazione segreta\n"
            f"`{PREFIX}randomsecret` — una citazione segreta a caso\n"
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
            f"`{PREFIX}search <parola>` — cerca per parola chiave\n"
            f"`{PREFIX}id <id>` — cerca per ID\n"
            f"`{PREFIX}stats` — conta le citazioni per autore\n"
            f"`{PREFIX}game` — indovina l'autore (solo in DM)"
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
