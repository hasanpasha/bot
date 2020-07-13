import logging
from typing import Optional

import discord
from discord import Color
from discord.ext import commands
from discord.ext.commands import Cog

from bot import constants
from bot.bot import Bot
from bot.constants import MODERATION_ROLES
from bot.utils.checks import with_role_check
from bot.utils.messages import send_attachments
from bot.utils.webhooks import send_webhook

log = logging.getLogger(__name__)


class DMRelay(Cog):
    """Relay direct messages to and from the bot."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.webhook_id = constants.Webhooks.dm_log
        self.webhook = None
        self.bot.loop.create_task(self.fetch_webhook())
        self.last_dm_user = None

    @commands.command(aliases=("reply",))
    async def send_dm(self, ctx: commands.Context, member: Optional[discord.Member], *, message: str) -> None:
        """
        Allows you to send a DM to a user from the bot.

        If `member` is not provided, it will send to the last user who DM'd the bot.

        This feature should be used extremely sparingly. Use ModMail if you need to have a serious
        conversation with a user. This is just for responding to extraordinary DMs, having a little
        fun with users, and telling people they are DMing the wrong bot.

        NOTE: This feature will be removed if it is overused.
        """
        if member:
            await member.send(message)
            await ctx.message.add_reaction("✅")
            return
        elif self.last_dm_user:
            await self.last_dm_user.send(message)
            await ctx.message.add_reaction("✅")
            return
        else:
            log.debug("Unable to send a DM to the user.")
            await ctx.message.add_reaction("❌")

    async def fetch_webhook(self) -> None:
        """Fetches the webhook object, so we can post to it."""
        await self.bot.wait_until_guild_available()

        try:
            self.webhook = await self.bot.fetch_webhook(self.webhook_id)
        except discord.HTTPException:
            log.exception(f"Failed to fetch webhook with id `{self.webhook_id}`")

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Relays the message's content and attachments to the dm_log channel."""
        # Only relay DMs from humans
        if message.author.bot or message.guild or self.webhook is None:
            return

        clean_content = message.clean_content
        if clean_content:
            await send_webhook(
                webhook=self.webhook,
                content=message.clean_content,
                username=message.author.display_name,
                avatar_url=message.author.avatar_url
            )
            self.last_dm_user = message.author

        # Handle any attachments
        if message.attachments:
            try:
                await send_attachments(message, self.webhook)
            except (discord.errors.Forbidden, discord.errors.NotFound):
                e = discord.Embed(
                    description=":x: **This message contained an attachment, but it could not be retrieved**",
                    color=Color.red()
                )
                await send_webhook(
                    webhook=self.webhook,
                    embed=e,
                    username=message.author.display_name,
                    avatar_url=message.author.avatar_url
                )
            except discord.HTTPException:
                log.exception("Failed to send an attachment to the webhook")

    def cog_check(self, ctx: commands.Context) -> bool:
        """Only allow moderators to invoke the commands in this cog."""
        return with_role_check(ctx, *MODERATION_ROLES)


def setup(bot: Bot) -> None:
    """Load the DMRelay  cog."""
    bot.add_cog(DMRelay(bot))
