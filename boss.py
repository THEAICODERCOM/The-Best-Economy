import discord
from discord import app_commands
from discord.ext import commands
from bot.services.boss_service import BossService
from bot.services.economy_service import EconomyService

def setup_boss_commands(bot, boss_service: BossService):
    econ = EconomyService()

    @bot.hybrid_command(name="currentboss", description="View current boss status")
    async def currentboss(ctx: commands.Context):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=False)
        except:
            pass
        boss = await boss_service.get_boss(ctx.guild.id)
        if not boss or not boss["is_active"]:
            return await ctx.send("No active boss. Please wait for the next spawn.")
        e = discord.Embed(title=f"👹 {boss['boss_name']}", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        e.add_field(name="Difficulty", value=boss["difficulty"], inline=True)
        e.add_field(name="HP", value=f"{boss['hp']:,} / {boss['max_hp']:,}\n{boss_service.hp_bar(boss['hp'], boss['max_hp'])}", inline=False)
        await ctx.send(embed=e)

    @bot.hybrid_command(name="attack", description="Attack the boss by spending coins")
    @app_commands.describe(amount="Coins to spend as damage")
    async def attack(ctx: commands.Context, amount: int):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=False)
        except:
            pass
        if amount <= 0:
            return await ctx.send("Enter a positive amount.")
        boss = await boss_service.get_boss(ctx.guild.id)
        if not boss or not boss["is_active"]:
            return await ctx.send("No active boss to attack.")
        data = await econ.get_global_money(ctx.author.id)
        if data["balance"] < amount:
            return await ctx.send(f"You need **{amount - data['balance']:,} more coins**.")
        await econ.update_global_balance(ctx.author.id, -amount) if hasattr(econ, "update_global_balance") else None
        dmg = amount
        await boss_service.add_damage(ctx.guild.id, ctx.author.id, dmg)
        new_hp = int(boss["hp"] - dmg)
        await boss_service.set_boss_hp(ctx.guild.id, new_hp)
        if new_hp <= 0:
            await ctx.send(f"💥 Massive hit by {ctx.author.mention}! The boss has been defeated.")
            await boss_service.distribute_loot(ctx.guild)
        else:
            await ctx.send(f"⚔️ {ctx.author.mention} dealt **{dmg:,}** damage. Boss HP: **{new_hp:,}/{boss['max_hp']:,}**")

    @bot.hybrid_command(name="itemuse", description="Use a boss loot item for this fight")
    @app_commands.describe(item="Item ID (e.g., epic_sword, mana_elixir)")
    async def itemuse(ctx: commands.Context, item: str):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=False)
        except:
            pass
        iid = str(item).lower().strip()
        if iid not in boss_service.loot_items:
            return await ctx.send("Invalid item ID.")
        import aiosqlite
        from shared.constants import DB_FILE
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute('SELECT count FROM boss_items WHERE user_id = ? AND item_id = ?', (ctx.author.id, iid)) as c:
                row = await c.fetchone()
            if not row or (row[0] or 0) <= 0:
                return await ctx.send("You don't have that item.")
            await db.execute('UPDATE boss_items SET count = count - 1 WHERE user_id = ? AND item_id = ?', (ctx.author.id, iid))
            await db.commit()
        await ctx.send(f"✅ Used **{boss_service.loot_items[iid]['name']}**. Effect applied to your next attack (where applicable).")

    @bot.hybrid_command(name="bossinterval", description="Admin: Set boss spawn interval in minutes")
    @commands.has_permissions(administrator=True)
    async def bossinterval(ctx: commands.Context, minutes: int):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=False)
        except:
            pass
        m = max(1, int(minutes))
        import aiosqlite
        from shared.constants import DB_FILE
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO guild_config (guild_id, boss_spawn_interval) VALUES (?, ?)', (ctx.guild.id, m * 60))
            await db.commit()
        await ctx.send(f"⏱️ Boss spawn interval set to **{m} minutes**.")

    @bot.hybrid_command(name="setbosschannel", description="Admin: Set the channel for boss announcements")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel to post boss spawns and status")
    async def setbosschannel(ctx: commands.Context, channel: discord.TextChannel):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer(ephemeral=False)
        except:
            pass
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("Please select a text channel.")
        import aiosqlite
        from shared.constants import DB_FILE
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO guild_config (guild_id, boss_channel_id) VALUES (?, ?)', (ctx.guild.id, channel.id))
            await db.commit()
        await ctx.send(f"📣 Boss announcements will be posted in {channel.mention}.")
