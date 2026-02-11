from discord.ext import commands
from bot.services.invite_service import InviteService
from bot.utils.response_builder import ResponseBuilder

def setup_owner_commands(bot):
    rb = ResponseBuilder()
    invite_service = InviteService(bot)

    @bot.hybrid_command(name="servers", aliases=["server"], description="Owner-only: DM the bot's servers and invite links")
    async def servers_owner(ctx: commands.Context):
        await rb.send_progress(ctx, "Building servers list…")
        try:
            lines = await invite_service.list_servers()
            msg = "Servers:\n" + ("\n".join(lines) if lines else "None")
            await rb.send_dm_or_channel(ctx, msg)
        except:
            await rb.send_dm_or_channel(ctx, "Servers list unavailable.")
