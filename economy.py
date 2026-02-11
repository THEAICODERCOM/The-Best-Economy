import discord
from discord.ext import commands
from bot.services.economy_service import EconomyService
from shared.constants import DEFAULT_BANK_PLANS

def setup_economy_commands(bot):
    econ = EconomyService()

    @bot.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into the bank")
    async def deposit(ctx: commands.Context, amount: str):
        user = await econ.get_global_money(ctx.author.id)
        if amount.lower() == 'all':
            amt = user['balance']
        else:
            try:
                amt = int(amount)
            except:
                return await ctx.send("Enter a valid number or 'all'.")
        if amt <= 0:
            return await ctx.send("Amount must be positive.")
        if user['balance'] < amt:
            return await ctx.send("You don't have enough coins!")
        ok = await econ.move_global_wallet_to_bank(ctx.author.id, amt)
        if ok:
            await ctx.send(f"🏦 Deposited **{amt:,} coins**.")
        else:
            await ctx.send("Failed to deposit due to a database error.")

    @bot.hybrid_command(name="withdraw", description="Withdraw coins from your bank")
    async def withdraw(ctx: commands.Context, amount: str):
        data = await econ.get_global_money(ctx.author.id)
        if amount.lower() == 'all':
            amt = data['bank']
        else:
            try:
                amt = int(amount)
            except:
                return await ctx.send("Invalid amount.")
        if amt <= 0:
            return await ctx.send("Amount must be positive.")
        if amt > data['bank']:
            return await ctx.send("You don't have that much in your bank!")
        ok = await econ.move_global_bank_to_wallet(ctx.author.id, amt)
        if ok:
            await ctx.send(f"✅ Withdrew **{amt:,} coins**.")
        else:
            await ctx.send("Failed to withdraw due to a database error.")

    @bot.hybrid_command(name="gift", description="Gift coins to another user (global money)")
    async def gift(ctx: commands.Context, member: discord.Member, amount: int):
        if member.id == ctx.author.id:
            return await ctx.send("You can't gift yourself.")
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        sender = await econ.get_global_money(ctx.author.id)
        if sender['balance'] < amount:
            return await ctx.send("You don't have enough coins.")
        ok = await econ.transfer_global_balance(ctx.author.id, member.id, amount)
        if ok:
            await ctx.send(f"🎁 {ctx.author.mention} gifted **{amount:,}** coins to {member.mention}.")
        else:
            await ctx.send("Failed to gift due to a database error.")

    @bot.hybrid_command(name="balance", aliases=["bal"], description="Check your balance")
    async def balance(ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        data = await econ.get_global_money(target.id)
        bank_plan = data['bank_plan'] if 'bank_plan' in data.keys() else 'standard'
        banks = DEFAULT_BANK_PLANS
        plan = banks.get(bank_plan) or banks.get('standard')
        if plan:
            rate_min = plan.get('min', 0.01)
            rate_max = plan.get('max', 0.02)
            plan_name = plan.get('name', 'Standard Vault')
            rate_str = f"{rate_min*100:.2f}%–{rate_max*100:.2f}%/h"
        else:
            plan_name = "Standard Vault"
            rate_str = "1.00%–2.00%/h"
        embed = discord.Embed(title=f"💰 {target.display_name}'s Vault", color=0xf1c40f)
        embed.add_field(name="Wallet", value=f"🪙 `{data['balance']:,}`", inline=True)
        embed.add_field(name="Bank", value=f"🏦 `{data['bank']:,}`", inline=True)
        embed.add_field(name="Bank Plan", value=f"{plan_name}\n{rate_str}", inline=False)
        embed.set_footer(text=f"Total: {data['balance'] + data['bank']:,} coins")
        await ctx.send(embed=embed)

    @bot.hybrid_command(name="rob", description="Try to rob someone")
    async def rob(ctx: commands.Context, target: discord.Member):
        if target.id == ctx.author.id:
            return await ctx.send("Don't rob yourself.")
        ok, value = await econ.rob_user(ctx.author.id, target.id)
        if ok is True and isinstance(value, int):
            embed = discord.Embed(description=f"🧤 Stole **{value:,}** from {target.mention}!", color=0x2ecc71)
            return await ctx.send(embed=embed)
        if ok is False and isinstance(value, int):
            embed = discord.Embed(description=f"🚔 Caught! Fined {value:,} coins.", color=0xe74c3c)
            return await ctx.send(embed=embed)
        return await ctx.send("Rob failed.")

    @bot.hybrid_command(name="crime", description="Commit a crime for high rewards (or risk!)")
    async def crime(ctx: commands.Context):
        ok, value = await econ.crime_action(ctx.author.id)
        if ok is True and isinstance(value, int):
            await ctx.send(f"😈 You pulled off a heist and got **{value:,} coins**!")
        elif ok is False and isinstance(value, int):
            await ctx.send(f"👮 BUSTED! You lost **{value:,} coins** while escaping.")
        else:
            await ctx.send("Crime failed.")

    @bot.hybrid_command(name="work", description="Work to earn coins")
    async def work(ctx: commands.Context):
        ok, earned, leveled_up, new_level = await econ.work_action(ctx.author.id, ctx.guild.id)
        if ok is True and isinstance(earned, int):
            msg = f"⚒️ You supervised the mines and earned **{earned:,} coins**!"
            if leveled_up:
                msg += f"\n🎊 **LEVEL UP!** You reached **Level {new_level}**!"
            embed = discord.Embed(description=msg, color=0x2ecc71)
            return await ctx.send(embed=embed)
        if isinstance(earned, str):
            return await ctx.send(earned)
        return await ctx.send("Work failed.")
    @bot.hybrid_command(name="bank", description="View and switch bank plans")
    async def bank_cmd(ctx: commands.Context, plan_id: str = None):
        data = await econ.get_global_money(ctx.author.id)
        banks = DEFAULT_BANK_PLANS
        current = data['bank_plan'] if 'bank_plan' in data.keys() and data['bank_plan'] else 'standard'
        if not plan_id:
            desc = ""
            for b_id, info in banks.items():
                rate_min = float(info.get('min', 0.01)) * 100
                rate_max = float(info.get('max', 0.02)) * 100
                price = int(info.get('price', 0))
                min_level = int(info.get('min_level', 0))
                marker = "✅" if b_id == current else "➖"
                desc += f"{marker} **{info.get('name', b_id)}** (`{b_id}`)\n{rate_min:.2f}%–{rate_max:.2f}%/h • Cost: {price:,} • Min Lvl: {min_level}\n\n"
            embed = discord.Embed(title="🏦 Bank Plans", description=desc or "No plans configured.", color=0x00d2ff)
            embed.set_footer(text="Use /bank <plan_id> to switch.")
            await ctx.send(embed=embed)
            return
        plan_id = plan_id.lower()
        if plan_id not in banks:
            return await ctx.send("Invalid plan ID. Use /bank to view available plans.")
        info = banks[plan_id]
        price = int(info.get('price', 0))
        min_level = int(info.get('min_level', 0))
        if data.get('level', 0) < min_level:
            return await ctx.send(f"You need at least level {min_level} to use this plan.")
        if price > 0 and data['balance'] < price:
            return await ctx.send(f"You need {price - data['balance']:,} more coins in your wallet.")
        ok = await econ.switch_bank_plan(ctx.author.id, plan_id, price)
        if ok:
            await ctx.send(f"Switched your bank plan to **{info.get('name', plan_id)}**.")
        else:
            await ctx.send("Failed to switch bank plan due to a database error.")
