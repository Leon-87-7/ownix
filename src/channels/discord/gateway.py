"""DM-only Discord Gateway client and live intake dispatch."""

from __future__ import annotations

import discord

from src import database
from src.auth import session as session_store
from src.channels.discord.adapter import message_to_intake_message, render_response
from src.config import settings
from src.intake import router
from src.utils.logger import get_logger

log = get_logger(__name__)
PAIRING_INSTRUCTIONS = (
    "This Discord account is not paired. Sign in to the Ownix dashboard, "
    "create a Discord pairing code, then send the code here."
)


def build_client() -> discord.Client:
    intents = discord.Intents.none()
    intents.dm_messages = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_message(message) -> None:
        await handle_message(message, client.user)

    return client


async def handle_message(message, bot_user=None) -> None:
    if message.author.bot or (bot_user is not None and message.author.id == bot_user.id):
        return
    if message.guild is not None:  # DM-only: ignore all guild/server traffic.
        return

    sender_id = str(message.author.id)
    owner_id = await database.get_identity_owner("discord", sender_id)
    content = (message.content or "").strip()

    # Pairing takes priority over normal dispatch. Codes are opaque URL-safe
    # tokens, so accepting the first whitespace-delimited word supports
    # friendly messages such as "pair <code>" without broad command parsing.
    candidates = content.split()
    token = candidates[-1] if candidates else ""
    paired_owner = await session_store.redeem_discord_pairing(token) if token else None
    if paired_owner is not None:
        winner = await database.link_identity(
            "discord", sender_id, paired_owner, verified=True
        )
        if winner != paired_owner:
            await message.channel.send("This Discord account is already paired.")
        else:
            await message.channel.send("Discord pairing complete. You can now send links here.")
        return

    if owner_id is None:
        await message.channel.send(
            "That pairing code is invalid or expired. " + PAIRING_INSTRUCTIONS
            if token else PAIRING_INSTRUCTIONS
        )
        return

    response = await router.handle(message_to_intake_message(message, owner_id))
    await render_response(message, response)


async def run() -> None:
    """Connect with discord.py's built-in reconnect/resume behavior."""
    if not settings.DISCORD_BOT_TOKEN:
        log.info("discord_gateway_disabled")
        return
    await build_client().start(settings.DISCORD_BOT_TOKEN, reconnect=True)
