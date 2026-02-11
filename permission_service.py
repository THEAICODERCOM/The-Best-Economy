import discord
from discord.ext import commands

BOT_OWNERS = [1324354578338025533]

class PermissionService:
    def is_owner_or_delegate(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
        if ctx.author.id in BOT_OWNERS:
            return True
        if ctx.author.id == ctx.guild.owner_id:
            return True
        return False

    def can_act_on(self, actor: discord.Member, target: discord.Member) -> bool:
        if actor.id in BOT_OWNERS:
            return True
        if actor.guild.owner_id == actor.id:
            return True
        if actor.id == target.id:
            return False
        try:
            return actor.top_role > target.top_role
        except:
            return False

def owner_or_delegate_check():
    async def predicate(ctx):
        ps = PermissionService()
        return ps.is_owner_or_delegate(ctx)
    return commands.check(predicate)
