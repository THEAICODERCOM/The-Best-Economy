import asyncio
import discord

class InviteService:
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def _create_invite(self, guild: discord.Guild) -> str | None:
        me = guild.me or guild.get_member(self.bot.user.id)
        if not me:
            return None
        for ch in list(getattr(guild, "text_channels", []))[:3]:
            try:
                perms = ch.permissions_for(me)
                if perms.create_instant_invite:
                    try:
                        inv = await asyncio.wait_for(ch.create_invite(max_age=3600, max_uses=1, unique=True), timeout=2.0)
                    except Exception:
                        inv = None
                    return getattr(inv, "url", None)
            except:
                pass
        return None

    async def list_servers(self) -> list[str]:
        guilds_sorted = sorted(self.bot.guilds, key=lambda g: (getattr(g, "member_count", 0) or 0), reverse=True)
        top = guilds_sorted[:3]
        async def _with_timeout(g):
            try:
                return await asyncio.wait_for(self._create_invite(g), timeout=1.5)
            except:
                return None
        try:
            invites = await asyncio.gather(*(_with_timeout(g) for g in top))
        except:
            invites = [None] * len(top)
        lines = []
        for i, g in enumerate(guilds_sorted):
            url = invites[i] if i < len(invites) else None
            mc = getattr(g, "member_count", 0) or 0
            lines.append(f"{g.name} • {mc} members • {url or 'no invite'}")
        return lines
