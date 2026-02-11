import discord
from discord.ext import commands
from bot.services.economy_service import EconomyService

def setup_quests_commands(bot):
    econ = EconomyService()

    @bot.hybrid_command(name="dailyquests", description="View your daily quest progress")
    async def dailyquests(ctx: commands.Context):
        await econ.ensure_quest_resets(ctx.author.id, ctx.guild.id)
        state = await econ.get_quest_state(ctx.author.id, ctx.guild.id)
        done = state["daily_commands"]
        completed = state["daily_completed"]
        quests = econ._pick_daily(ctx.guild.id)
        embed = discord.Embed(title="📅 Daily Quests", color=0x00d2ff)
        if not quests:
            embed.description = "No quests configured."
        else:
            for q in quests:
                target = q["target"]
                reward = q["reward"]
                progress_pct = min(100, int(done / target * 100)) if target > 0 else 100
                bar_len = 12
                filled = int(bar_len * progress_pct / 100)
                bar = "🟦" * filled + "⬛" * (bar_len - filled)
                is_done = completed.get(q["id"], False)
                prefix = "✅" if is_done else "❌"
                status = "Completed" if is_done else ("Ready" if done >= target else "In progress")
                embed.add_field(
                    name=f"{prefix} {q['description']}",
                    value=f"Reward: {reward:,} coins\nProgress: {min(done, target)} / {target} ({progress_pct}%)\n{bar}\nStatus: {status}",
                    inline=False
                )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="weeklyquests", description="View your weekly quest progress")
    async def weeklyquests(ctx: commands.Context):
        await econ.ensure_quest_resets(ctx.author.id, ctx.guild.id)
        state = await econ.get_quest_state(ctx.author.id, ctx.guild.id)
        done = state["weekly_commands"]
        completed = state["weekly_completed"]
        quests = econ._pick_weekly(ctx.guild.id)
        embed = discord.Embed(title="📆 Weekly Quests", color=0x00d2ff)
        if not quests:
            embed.description = "No quests configured."
        else:
            for q in quests:
                target = q["target"]
                reward = q["reward"]
                progress_pct = min(100, int(done / target * 100)) if target > 0 else 100
                bar_len = 12
                filled = int(bar_len * progress_pct / 100)
                bar = "🟦" * filled + "⬛" * (bar_len - filled)
                is_done = completed.get(q["id"], False)
                prefix = "✅" if is_done else "❌"
                status = "Completed" if is_done else ("Ready" if done >= target else "In progress")
                embed.add_field(
                    name=f"{prefix} {q['description']}",
                    value=f"Reward: {reward:,} coins\nProgress: {min(done, target)} / {target} ({progress_pct}%)\n{bar}\nStatus: {status}",
                    inline=False
                )
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="daily", description="Claim your daily reward and build a login streak")
    async def daily(ctx: commands.Context):
        ok, remaining, streak, reward = await econ.claim_daily(ctx.author.id)
        if not ok:
            hours, rem = divmod(int(remaining), 3600)
            minutes, _ = divmod(rem, 60)
            return await ctx.send(f"⏳ Your daily is not ready. Come back in **{hours}h {minutes}m**.")
        await ctx.send(f"📅 Daily claimed! **+{reward:,}** coins. Streak: **{streak}**.")
