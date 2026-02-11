import json
import discord
import aiosqlite
from discord.ext import commands
from bot.services.economy_service import EconomyService
from shared.constants import DB_FILE

def setup_profile_commands(bot):
    econ = EconomyService()

    @bot.hybrid_command(name="profile", description="View your empire status")
    async def profile(ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        data = await econ.get_global_money(target.id)
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT asset_id, count FROM user_assets WHERE user_id = ? AND guild_id = ? AND count > 0', (target.id, ctx.guild.id)) as cursor:
                assets_rows = await cursor.fetchall()
            async with db.execute('SELECT multipliers_json, titles_json, medals_json FROM user_rewards WHERE user_id = ?', (target.id,)) as cursor:
                reward_row = await cursor.fetchone()
        assets_str = "\n".join([f"• {count}x {aid}" for aid, count in assets_rows]) if assets_rows else "No assets."
        titles_str = "None"
        medals_str = ""
        if reward_row:
            try:
                titles = json.loads(reward_row['titles_json'])
                medals = json.loads(reward_row['medals_json'])
                if titles:
                    titles_str = ", ".join([t['title'] for t in titles])
                if medals:
                    medals_str = " " + " ".join([m['medal'] for m in medals])
            except:
                pass
        embed = discord.Embed(title=f"👑 {target.display_name}'s Empire{medals_str}", color=0x00d2ff)
        embed.add_field(name="📊 Stats", value=f"Level: {data['level']}\nXP: {data['xp']}\nPrestige: {data['prestige']}", inline=True)
        embed.add_field(name="💰 Wealth (Global)", value=f"Wallet: {data['balance']:,}\nBank: {data['bank']:,}", inline=True)
        embed.add_field(name="🏷️ Titles", value=titles_str, inline=False)
        embed.add_field(name="🏗️ Assets", value=assets_str, inline=False)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="rank", description="Check your current level and XP")
    async def rank(ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?', (target.id, ctx.guild.id)) as cursor:
                row = await cursor.fetchone()
        xp = int((row['xp'] or 0)) if row else 0
        level = int((row['level'] or 1)) if row else 1
        needed_xp = max(100, level * 100)
        progress = min(1.0, xp / needed_xp)
        bar_length = 10
        filled = int(progress * bar_length)
        bar = "🟩" * filled + "⬜" * (bar_length - filled)
        embed = discord.Embed(title=f"📈 {target.display_name}'s Rank", color=0x00d2ff)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{xp} / {needed_xp}", inline=True)
        embed.add_field(name="Progress", value=bar, inline=False)
        await ctx.send(embed=embed)
