import discord
from discord.ext import commands
from bot.services.permission_service import PermissionService, owner_or_delegate_check
from bot.services.economy_service import EconomyService

def setup_moderation_commands(bot):
    ps = PermissionService()
    econ = EconomyService()

    @bot.hybrid_command(name="kick", description="Kick a member")
    @commands.guild_only()
    async def kick_member(ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if not (ctx.author.guild_permissions.kick_members or ps.is_owner_or_delegate(ctx)):
            return await ctx.send("You lack kick permissions.")
        if not ps.can_act_on(ctx.author, member):
            return await ctx.send("You cannot act on that member.")
        try:
            await member.kick(reason=reason or f"Kicked by {ctx.author} via command")
            await ctx.send(f"Kicked {member.mention}.")
        except Exception as e:
            await ctx.send(f"Failed to kick: {e}")

    @bot.hybrid_command(name="ban", description="Ban a member")
    @commands.guild_only()
    async def ban_member(ctx: commands.Context, member: discord.Member, *, reason: str = None):
        if not (ctx.author.guild_permissions.ban_members or ps.is_owner_or_delegate(ctx)):
            return await ctx.send("You lack ban permissions.")
        if not ps.can_act_on(ctx.author, member):
            return await ctx.send("You cannot act on that member.")
        try:
            await member.ban(reason=reason or f"Banned by {ctx.author} via command")
            await ctx.send(f"Banned {member.mention}.")
        except Exception as e:
            await ctx.send(f"Failed to ban: {e}")

    @bot.hybrid_command(name="addmoney", description="[OWNER ONLY] Add money to a user")
    @owner_or_delegate_check()
    async def add_money_admin(ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        await ctx.send(f"⚠️ Are you sure you want to add **{amount:,} coins** to {member.mention}? (Type `confirm` to proceed)")
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
        try:
            await bot.wait_for('message', check=check, timeout=30)
        except:
            return await ctx.send("Operation cancelled.")
        ok = await econ.add_money(member.id, ctx.guild.id, amount)
        if ok:
            await ctx.send(f"✅ Added **{amount:,} coins** to {member.mention}'s balance.")
        else:
            await ctx.send("Failed to add money due to a database error.")
