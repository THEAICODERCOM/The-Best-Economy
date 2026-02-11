import discord
from discord.ext import commands
from bot.services.assets_service import AssetsService

def setup_assets_commands(bot):
    assets = AssetsService()

    @bot.hybrid_command(name="shop", description="View the asset shop")
    async def shop(ctx: commands.Context):
        config = await assets.get_guild_assets(ctx.guild.id)
        embed = discord.Embed(title="🛒 Kingdom Asset Shop", description="Buy assets to earn passive income every 10 minutes!", color=0x00d2ff)
        for aid, data in config.items():
            embed.add_field(name=f"{data['name']} (ID: {aid})", value=f"Price: 🪙 {data['price']:,}\nIncome: 💸 {data['income']:,}/10min", inline=False)
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="buy", description="Buy a passive income asset")
    async def buy_asset(ctx: commands.Context, asset_id: str, count: int = 1):
        ok, msg = await assets.buy_asset(ctx.author.id, ctx.guild.id, asset_id, count)
        if ok:
            await ctx.send(msg)
        else:
            await ctx.send(msg)
