import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import random
import time
import aiosqlite
import json
import ssl
import certifi
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)
TOKEN = os.getenv('DISCORD_TOKEN')

# FIX: macOS SSL Certificate verification bug
# This is the most aggressive way to bypass the macOS certificate issue
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Monkeypatch aiohttp to completely disable SSL verification for Discord
orig_request = aiohttp.ClientSession._request
async def new_request(self, method, url, *args, **kwargs):
    kwargs['ssl'] = False
    return await orig_request(self, method, url, *args, **kwargs)
aiohttp.ClientSession._request = new_request

orig_ws_connect = aiohttp.ClientSession.ws_connect
async def new_ws_connect(self, url, *args, **kwargs):
    kwargs['ssl'] = False
    return await orig_ws_connect(self, url, *args, **kwargs)
aiohttp.ClientSession.ws_connect = new_ws_connect

# Database Setup
DB_FILE = 'empire_v2.db'

# Default Assets
DEFAULT_ASSETS = {
    "lemonade_stand": {"name": "Lemonade Stand", "price": 500, "income": 5},
    "gaming_pc": {"name": "Gaming PC", "price": 2500, "income": 30},
    "coffee_shop": {"name": "Coffee Shop", "price": 10000, "income": 150},
}

# Blackjack Card Emojis
CARD_EMOJIS = {
    # 2s
    ('2', '♣️'): '<:2_of_clubs:1464574130169839707>',
    ('2', '♦️'): '<:2_of_diamonds:1464574132866777281>',
    ('2', '♥️'): '<:2_of_hearts:1464574134620131442>',
    ('2', '♠️'): '<:2_of_spades:1464574137111416874>',
    # 3s
    ('3', '♣️'): '<:3_of_clubs:1464574140265791692>',
    ('3', '♦️'): '<:3_of_diamonds:1464574142643699765>',
    ('3', '♥️'): '<:3_of_hearts:1464574145047036047>',
    ('3', '♠️'): '<:3_of_spades:1464574147832184862>',
    # 4s
    ('4', '♣️'): '<:4_of_clubs:1464574149660901593>',
    ('4', '♦️'): '<:4_of_diamonds:1464574151091159060>',
    ('4', '♥️'): '<:4_of_hearts:1464574158389379244>',
    ('4', '♠️'): '<:4_of_spades:1464574159949402299>',
    # 5s
    ('5', '♣️'): '<:5_of_clubs:1464574161404952576>',
    ('5', '♦️'): '<:5_of_diamonds:1464574163497783391>',
    ('5', '♥️'): '<:5_of_hearts:1464574165125169315>',
    ('5', '♠️'): '<:5_of_spades:1464574166526066769>',
    # 6s
    ('6', '♣️'): '<:6_of_clubs:1464574168585474089>',
    ('6', '♦️'): '<:6_of_diamonds:1464574171408502858>',
    ('6', '♥️'): '<:6_of_hearts:1464574173438279770>',
    ('6', '♠️'): '<:6_of_spades:1464574175678169214>',
    # 7s
    ('7', '♣️'): '<:7_of_clubs:1464574177712275466>',
    ('7', '♦️'): '<:7_of_diamonds:1464574179063103621>',
    ('7', '♥️'): '<:7_of_hearts:1464574180476321803>',
    ('7', '♠️'): '<:7_of_spades:1464574181977882634>',
    # 8s
    ('8', '♣️'): '<:8_of_clubs:1464574183852867805>',
    ('8', '♦️'): '<:8_of_diamonds:1464574185652359280>',
    ('8', '♥️'): '<:8_of_hearts:1464574187308974177>',
    ('8', '♠️'): '<:8_of_spades:1464574188848418982>',
    # 9s
    ('9', '♣️'): '<:9_of_clubs:1464574190639386736>',
    ('9', '♦️'): '<:9_of_diamonds:1464574192333885565>',
    ('9', '♥️'): '<:9_of_hearts:1464574193864540284>',
    ('9', '♠️'): '<:9_of_spades:1464574195357843539>',
    # 10s
    ('10', '♣️'): '<:10_of_clubs:1464574196762804326>',
    ('10', '♦️'): '<:10_of_diamonds:1464574198969143357>',
    ('10', '♥️'): '<:10_of_hearts:1464574200218910877>',
    ('10', '♠️'): '<:10_of_spades:1464574201661886506>',
    # Aces
    ('A', '♣️'): '<:ace_of_clubs:1464574202907459636>',
    ('A', '♦️'): '<:ace_of_diamonds:1464574204895690926>',
    ('A', '♥️'): '<:ace_of_hearts:1464574206368026769>',
    ('A', '♠️'): '<:ace_of_spades:1464574208188092466>',
    # Jacks
    ('J', '♣️'): '<:w_jack_of_clubs:1464575453888249961>',
    ('J', '♦️'): '<:w_jack_of_diamonds:1464575455305928788>',
    ('J', '♥️'): '<:w_jack_of_hearts:1464575456937513104>',
    ('J', '♠️'): '<:w_jack_of_spades:1464575460854993070>',
    # Queens
    ('Q', '♣️'): '<:w_queen_of_clubs:1464575475228872796>',
    ('Q', '♦️'): '<:w_queen_of_diamonds:1464575477057454366>',
    ('Q', '♥️'): '<:w_queen_of_hearts:1464575479779561636>',
    ('Q', '♠️'): '<:w_queen_of_spades:1464575481235116088>',
    # Kings
    ('K', '♣️'): '<:w_king_of_clubs:1464575462763266142>',
    ('K', '♦️'): '<:w_king_of_diamonds:1464575470875054259>',
    ('K', '♥️'): '<:w_king_of_hearts:1464575472745582878>',
    ('K', '♠️'): '<:w_king_of_spades:1464575473928634516>',
    # Back
    'back': '<:back:1464566298460553249>'
}

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER, guild_id INTEGER, balance INTEGER DEFAULT 100,
            bank INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            prestige INTEGER DEFAULT 0, last_work INTEGER DEFAULT 0,
            last_crime INTEGER DEFAULT 0, last_rob INTEGER DEFAULT 0,
            last_vote INTEGER DEFAULT 0, auto_deposit INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )''')
        # Ensure new columns exist for existing databases
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_vote INTEGER DEFAULT 0')
            await db.execute('ALTER TABLE users ADD COLUMN auto_deposit INTEGER DEFAULT 0')
        except:
            pass # Already exists
            
        await db.execute('''CREATE TABLE IF NOT EXISTS user_assets (
            user_id INTEGER, guild_id INTEGER, asset_id TEXT, count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id, asset_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY, prefix TEXT DEFAULT '.',
            role_shop_json TEXT DEFAULT '{}', custom_assets_json TEXT DEFAULT '{}'
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS global_votes (
            user_id INTEGER PRIMARY KEY, last_vote INTEGER DEFAULT 0
        )''')
        await db.commit()

async def get_prefix(bot, message):
    if not message.guild: return '.'
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT prefix FROM guild_config WHERE guild_id = ?', (message.guild.id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else '.'

# Bot setup
intents = discord.Intents.default()
# ENABLE message_content and members so prefix commands work!
intents.members = True
intents.message_content = True 
bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# Debug: Check if token is loaded
if not TOKEN:
    print("CRITICAL: DISCORD_TOKEN not found in .env file!")
else:
    TOKEN = TOKEN.strip()

# --- Database Helpers ---
async def ensure_user(user_id, guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)', (user_id, guild_id))
        await db.commit()

async def add_xp(user_id, guild_id, amount):
    await ensure_user(user_id, guild_id)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET xp = xp + ? WHERE user_id = ? AND guild_id = ?', (amount, user_id, guild_id))
        await db.commit()
        
        # Check for level up
        async with db.execute('SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                current_xp, current_level = row
                next_level_xp = current_level * 500
                if current_xp >= next_level_xp:
                    new_level = current_level + 1
                    await db.execute('UPDATE users SET level = ?, xp = xp - ? WHERE user_id = ? AND guild_id = ?', 
                                    (new_level, next_level_xp, user_id, guild_id))
                    await db.commit()
                    return True, new_level
    return False, None

async def get_user_data(user_id, guild_id):
    await ensure_user(user_id, guild_id)
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        # Get last_vote from global_votes table (preferred), fallback to user-specific last_vote
        # Use CASE to properly compare and select the maximum timestamp
        async with db.execute('''
            SELECT u.*, 
                   CASE 
                       WHEN COALESCE(gv.last_vote, 0) > COALESCE(u.last_vote, 0) 
                       THEN gv.last_vote 
                       ELSE COALESCE(u.last_vote, 0) 
                   END as last_vote
            FROM users u
            LEFT JOIN global_votes gv ON u.user_id = gv.user_id
            WHERE u.user_id = ? AND u.guild_id = ?
        ''', (user_id, guild_id)) as cursor:
            row = await cursor.fetchone()
            return row

async def get_guild_assets(guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT custom_assets_json FROM guild_config WHERE guild_id = ?', (int(guild_id),)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    custom = json.loads(row[0])
                    # Merge default and custom
                    # Custom assets (which include defaults if edited in dashboard) will overwrite
                    return {**DEFAULT_ASSETS, **custom}
                except json.JSONDecodeError:
                    return DEFAULT_ASSETS
    return DEFAULT_ASSETS

# --- Logic Functions (Shared by Prefix & Slash) ---
async def work_logic(user_id, guild_id):
    data = await get_user_data(user_id, guild_id)
    now = int(time.time())
    if now - data['last_work'] < 300:
        return False, f"⏳ Your workers are tired! Wait **{300 - (now - data['last_work'])}s**."
    
    earned = random.randint(100, 300) * data['level'] * (data['prestige'] + 1)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ? AND guild_id = ?', 
                        (earned, now, user_id, guild_id))
        await db.commit()
    
    # Use helper for XP to trigger level up notifications
    leveled_up, new_level = await add_xp(user_id, guild_id, 20)
    
    return True, f"⚒️ You supervised the mines and earned **{earned:,} coins**!" + (f"\n🎊 **LEVEL UP!** You reached **Level {new_level}**!" if leveled_up else "")

# --- Tasks ---
@tasks.loop(minutes=10)
async def passive_income_task():
    async with aiosqlite.connect(DB_FILE) as db:
        # Fetch all assets and user data in one go to handle auto-deposit and income
        async with db.execute('''
            SELECT ua.user_id, ua.guild_id, ua.asset_id, ua.count, u.auto_deposit, u.last_vote
            FROM user_assets ua
            JOIN users u ON ua.user_id = u.user_id AND ua.guild_id = u.guild_id
            WHERE ua.count > 0
        ''') as cursor:
            rows = await cursor.fetchall()
        
        if not rows: return

        now = int(time.time())
        # Group by guild to fetch configs once
        guild_groups = {}
        for uid, gid, aid, count, auto_dep, last_vote in rows:
            if gid not in guild_groups: guild_groups[gid] = []
            guild_groups[gid].append((uid, aid, count, auto_dep, last_vote))

        updates_balance = [] # List of (income, uid, gid)
        updates_bank = []    # List of (income, uid, gid)

        for gid, members in guild_groups.items():
            assets_config = await get_guild_assets(gid)
            user_data = {} # uid -> {'income': 0, 'auto_dep': 0, 'last_vote': 0}
            
            for uid, aid, count, auto_dep, last_vote in members:
                if aid in assets_config:
                    income = assets_config[aid]['income'] * count
                    if uid not in user_data:
                        user_data[uid] = {'income': 0, 'auto_dep': auto_dep, 'last_vote': last_vote}
                    user_data[uid]['income'] += income
            
            for uid, data in user_data.items():
                if data['income'] > 0:
                    # Check if auto-deposit is active (voted in last 12 hours)
                    is_voter = (now - data['last_vote']) < 43200 # 12 hours
                    if data['auto_dep'] and is_voter:
                        updates_bank.append((data['income'], uid, gid))
                    else:
                        updates_balance.append((data['income'], uid, gid))

        if updates_balance:
            await db.executemany('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', updates_balance)
        if updates_bank:
            await db.executemany('UPDATE users SET bank = bank + ? WHERE user_id = ? AND guild_id = ?', updates_bank)
        
        await db.commit()

@tasks.loop(hours=1)
async def interest_task():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT user_id, guild_id, bank FROM users WHERE bank > 0') as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                uid, gid, bank = row
                # 1% to 2% random interest
                interest = int(bank * random.uniform(0.01, 0.02))
                if interest > 0:
                    await db.execute('UPDATE users SET bank = bank + ? WHERE user_id = ? AND guild_id = ?', (interest, uid, gid))
        await db.commit()

@tasks.loop(minutes=5)
async def vote_reminder_task():
    """Check for users whose vote expired in the last 5 minutes and notify them."""
    now = int(time.time())
    twelve_hours_ago = now - 43200
    
    async with aiosqlite.connect(DB_FILE) as db:
        # Find users who voted exactly 12h (+/- 5 mins) ago
        async with db.execute('''
            SELECT DISTINCT user_id FROM users 
            WHERE last_vote > ? AND last_vote <= ?
        ''', (twelve_hours_ago - 300, twelve_hours_ago)) as cursor:
            rows = await cursor.fetchall()
            
    for row in rows:
        user_id = row[0]
        try:
            user = await bot.fetch_user(user_id)
            if user:
                vote_url = f"https://top.gg/bot/{bot.user.id}/vote"
                embed = discord.Embed(title="⌛ Vote Expired!", color=0xffa500)
                embed.description = f"Your 12-hour vote rewards for **Empire Nexus** have expired!\n\n" \
                                    f"Vote again now to keep your **Auto-Deposit** active and support the bot!\n\n" \
                                    f"[**Click here to revote on Top.gg**]({vote_url})"
                await user.send(embed=embed)
        except:
            pass # User might have DMs closed

@tasks.loop(minutes=30)
async def update_topgg_stats():
    """Automatically update the bot's server count on Top.gg."""
    topgg_token = os.getenv('TOPGG_TOKEN')
    if not topgg_token:
        return
    
    url = f"https://top.gg/api/bots/{bot.user.id}/stats"
    headers = {"Authorization": topgg_token}
    payload = {"server_count": len(bot.guilds)}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    print(f"DEBUG: Successfully updated Top.gg server count to {len(bot.guilds)}")
                else:
                    print(f"DEBUG: Failed to update Top.gg stats: {resp.status}")
        except Exception as e:
            print(f"DEBUG: Error updating Top.gg stats: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(error.retry_after, 60)
        return await ctx.send(f"⏳ **Cooldown!** Try again in **{int(minutes)}m {int(seconds)}s**.", delete_after=10)
    elif isinstance(error, commands.MissingPermissions):
        return await ctx.send("❌ You don't have permission to use this command!")
    elif isinstance(error, commands.BadArgument):
        return await ctx.send("❌ Invalid argument provided! Check `.help`.")
    print(f"DEBUG Error: {error}")

@bot.event
async def on_command_completion(ctx):
    # Reward 5 XP per command used
    leveled_up, new_level = await add_xp(ctx.author.id, ctx.guild.id, 5)
    if leveled_up:
        await ctx.send(f"🎊 **LEVEL UP!** {ctx.author.mention} reached **Level {new_level}**!")

@bot.event
async def on_ready():
    await init_db()
    interest_task.start()
    passive_income_task.start()
    vote_reminder_task.start()
    update_topgg_stats.start()
    
    # Manually register all commands to the tree if they aren't appearing
    for command in bot.commands:
        if isinstance(command, commands.HybridCommand):
            print(f"DEBUG: Ensuring hybrid command /{command.name} is in tree")

    try:
        # Force a fresh sync
        synced = await bot.tree.sync()
        print(f"DEBUG: Synced {len(synced)} global slash commands:")
        for cmd in synced:
            print(f" - /{cmd.name}")
    except Exception as e:
        print(f"CRITICAL: Error syncing slash commands: {e}")
    print(f'Logged in as {bot.user.name}')

# --- Hybrid Commands ---

@bot.hybrid_command(name="start", description="New to the Empire? Start your tutorial here!")
async def start_tutorial(ctx: commands.Context):
    embed = discord.Embed(
        title="🌅 Welcome to Empire Nexus",
        description=(
            "You have inherited a small plot of land and 100 coins. Your goal: **Build the wealthiest empire in the server.**\n\n"
            "**Step 1: Get Started**\n"
            "Use `.work` or `/work` to supervise the mines and earn your first coins.\n\n"
            "**Step 2: Invest Wisely**\n"
            "Visit the `.shop` and buy your first **Lemonade Stand**. It will generate income for you every 10 minutes, even while you sleep!\n\n"
            "**Step 3: Secure Your Wealth**\n"
            "Other rulers can `.rob` you! Use `.deposit <amount>` (or `.dep`) to move your coins into the **Bank**. Banked coins are safe from thieves and earn **hourly interest**.\n\n"
            "**Step 4: Expand & Conquer**\n"
            "Once you reach Level 10, you can `.prestige` to reset your progress for a permanent income bonus.\n\n"
            "**Need more help?**\n"
            "Type `.help` for a full command list or `.setup` to configure your server's dashboard."
        ),
        color=0x00d2ff
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Your journey to greatness begins now.")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="help", description="Show all available commands")
async def help_command(ctx: commands.Context):
    prefix = await get_prefix(bot, ctx.message)
    embed = discord.Embed(
        title="🏰 Empire Nexus | Grand Library", 
        description=(
            f"Welcome to the Nexus. Use `{prefix}command` or `/command` to interact.\n\n"
            "🔗 [**Nexus Dashboard**](https://thegoatchessbot.alwaysdata.net/)\n"
            "🛠️ [**Support Server**](https://discord.gg/zsqWFX2gBV)"
        ), 
        color=0x00d2ff
    )
    
    embed.add_field(name="💰 Economy & Growth", value=(
        f"**`{prefix}balance`** (bal) • Check your vault\n"
        f"**`{prefix}deposit`** (dep) • Safe storage\n"
        f"**`{prefix}withdraw`** • Access funds\n"
        f"**`{prefix}work`** • Supervise mines\n"
        f"**`{prefix}crime`** • High stakes heist\n"
        f"**`{prefix}leaderboard`** (lb) • Global ranks\n"
        f"**`{prefix}rank`** • Check level & XP"
    ), inline=True)

    embed.add_field(name="🚀 Rewards & Assets", value=(
        f"**`{prefix}vote`** • Get Top.gg rewards\n"
        f"**`{prefix}autodeposit`** • Auto-save income\n"
        f"**`{prefix}shop`** • Buy income assets\n"
        f"**`{prefix}inventory`** (inv) • Your assets\n"
        f"**`{prefix}buyrole`** • Purchase server roles\n"
        f"**`{prefix}prestige`** • Ascend for bonus"
    ), inline=True)
    
    embed.add_field(name="🎰 Royal Casino", value=(
        f"**`{prefix}blackjack`** (bj) • Pro Blackjack\n"
        f"**`{prefix}roulette`** • Spin the wheel\n"
        f"**`{prefix}riddle`** • Mental challenge\n"
        f"*(Roulette: try red, black, 1st, 2nd, 3rd, or 0-36)*"
    ), inline=True)
    
    embed.add_field(name="🏗️ Empire Management", value=(
        f"**`{prefix}shop`** • Browse assets\n"
        f"**`{prefix}buy <id>`** • Expand empire\n"
        f"**`{prefix}inventory`** • View assets\n"
        f"**`{prefix}profile`** • Detailed stats\n"
        f"**`{prefix}prestige`** • Level 10 reset\n"
        f"**`{prefix}buyrole`** • Buy server roles"
    ), inline=False)
    
    embed.add_field(name="⚙️ Configuration", value=(
        f"**`{prefix}setup`** • Dashboard link\n"
        f"**`{prefix}setprefix`** • Admin only"
    ), inline=True)

    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Use .start for a quick tutorial!")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="prestige", description="Reset your balance and level for a permanent income multiplier")
async def prestige(ctx: commands.Context):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    
    # Requirement: Level 10 + 50,000 coins in bank
    needed_level = 10
    needed_bank = 50000
    
    if data['level'] < needed_level or data['bank'] < needed_bank:
        return await ctx.send(f"❌ You aren't ready to prestige! You need **Level {needed_level}** and **{needed_bank:,} coins** in your bank.")
    
    embed = discord.Embed(title="✨ Ascend to Greatness?", description=f"Prestiging will reset your **Level, XP, Balance, and Bank** to zero.\n\n**In return, you get:**\n💎 Prestige Level {data['prestige'] + 1}\n🚀 Permanent **{(data['prestige'] + 1) * 50}%** income bonus\n\nType `confirm` to proceed.", color=0xffd700)
    await ctx.send(embed=embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'confirm'

    try:
        await bot.wait_for('message', check=check, timeout=30)
    except:
        return await ctx.send("Prestige cancelled.")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = 100, bank = 0, xp = 0, level = 1, prestige = prestige + 1 WHERE user_id = ? AND guild_id = ?', 
                        (ctx.author.id, ctx.guild.id))
        # Clear assets too? Usually prestige resets everything
        await db.execute('DELETE FROM user_assets WHERE user_id = ? AND guild_id = ?', (ctx.author.id, ctx.guild.id))
        await db.commit()
    
    await ctx.send(f"🎊 **CONGRATULATIONS!** You have reached Prestige Level **{data['prestige'] + 1}**! Your empire begins anew, but stronger than ever.")

@bot.hybrid_command(name="inventory", description="View your owned assets")
async def inventory(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT asset_id, count FROM user_assets WHERE user_id = ? AND guild_id = ? AND count > 0', (target.id, ctx.guild.id)) as cursor:
            assets_rows = await cursor.fetchall()
    
    if not assets_rows:
        return await ctx.send(f"📦 {target.display_name} doesn't own any assets yet.")

    assets_config = await get_guild_assets(ctx.guild.id)
    inv_str = ""
    total_income = 0
    
    for aid, count in assets_rows:
        if aid in assets_config:
            name = assets_config[aid]['name']
            income = assets_config[aid]['income'] * count
            inv_str += f"• **{count}x {name}** (Income: 💸 {income:,}/10min)\n"
            total_income += income
        else:
            inv_str += f"• **{count}x {aid}** (Unknown Asset)\n"
            
    embed = discord.Embed(title=f"🎒 {target.display_name}'s Assets", color=0x00d2ff)
    embed.description = inv_str
    embed.add_field(name="📈 Total Passive Income", value=f"💸 {total_income:,} coins / 10 minutes")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="roulette", description="Bet your coins on a roulette spin")
async def roulette(ctx: commands.Context, amount: str = None, space: str = None):
    if amount is None or space is None:
        prefix = await get_prefix(bot, ctx.message)
        return await ctx.send(f"❌ Incorrect format! Use: `{prefix}roulette <amount> <space>`")
    
    user = await get_user_data(ctx.author.id, ctx.guild.id)
    balance = user['balance']

    if amount.lower() == 'all':
        bet_amount = balance
    elif amount.lower() == 'half':
        bet_amount = balance // 2
    else:
        try:
            bet_amount = int(amount)
        except ValueError:
            return await ctx.send("❌ Invalid amount! Use a number, 'half', or 'all'.")

    if bet_amount <= 0: return await ctx.send("❌ Bet a positive amount!")
    if balance < bet_amount: return await ctx.send("❌ You don't have enough coins!")

    space = space.lower()
    
    # Define valid spaces and their multipliers
    # red/black = 2x, 1st/2nd/3rd = 3x, green = 14x, number = 36x
    valid_colors = ['red', 'black', 'green']
    valid_dozens = ['1st', '2nd', '3rd']
    
    is_number = False
    try:
        num = int(space)
        if 0 <= num <= 36:
            is_number = True
        else:
            return await ctx.send("❌ Number must be between 0 and 36!")
    except ValueError:
        if space not in valid_colors and space not in valid_dozens:
            return await ctx.send("❌ Invalid space! Use: `red`, `black`, `green`, `1st`, `2nd`, `3rd`, or a number `0-36`.")
    
    # Roll logic
    roll = random.randint(0, 36)
    
    # Determine roll color
    if roll == 0: 
        roll_color = 'green'
    elif roll in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
        roll_color = 'red'
    else:
        roll_color = 'black'
        
    # Determine roll dozen
    if 1 <= roll <= 12: roll_dozen = '1st'
    elif 13 <= roll <= 24: roll_dozen = '2nd'
    elif 25 <= roll <= 36: roll_dozen = '3rd'
    else: roll_dozen = None

    # Check win
    win = False
    multiplier = 0
    
    if is_number:
        if int(space) == roll:
            win = True
            multiplier = 36
    elif space == roll_color:
        win = True
        multiplier = 14 if space == 'green' else 2
    elif space == roll_dozen:
        win = True
        multiplier = 3

    async with aiosqlite.connect(DB_FILE) as db:
        if win:
            winnings = bet_amount * (multiplier - 1)
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (winnings, ctx.author.id, ctx.guild.id))
            result_msg = f"✅ **WIN!** The ball landed on **{roll_color.upper()} {roll}**.\nYou won **{bet_amount * multiplier:,} coins**!"
            color_embed = 0x2ecc71 # Green
        else:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (bet_amount, ctx.author.id, ctx.guild.id))
            result_msg = f"❌ **LOSS!** The ball landed on **{roll_color.upper()} {roll}**.\nYou lost **{bet_amount:,} coins**."
            color_embed = 0xe74c3c # Red
        await db.commit()
    
    embed = discord.Embed(title="🎡 Roulette Spin", description=result_msg, color=color_embed)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="riddle", description="Get a riddle to solve")
async def riddle(ctx: commands.Context):
    riddles = [
        ("What has to be broken before you can use it?", "egg"),
        ("I’m tall when I’m young, and I’m short when I’m old. What am I?", "candle"),
        ("What is full of holes but still holds water?", "sponge"),
        ("What gets wet while drying?", "towel"),
        ("What has a head and a tail but no body?", "coin"),
        ("What has keys but can't open locks?", "piano"),
        ("The more of this there is, the less you see. What is it?", "darkness")
    ]
    q, a = random.choice(riddles)
    
    # Store the active riddle in a temporary dictionary
    if not hasattr(bot, 'active_riddles'):
        bot.active_riddles = {}
    
    bot.active_riddles[ctx.author.id] = {
        'answer': a,
        'reward': random.randint(400, 800),
        'expires': time.time() + 60
    }
    
    embed = discord.Embed(title="🧩 Riddle Challenge", description=f"*{q}*", color=0xf1c40f)
    prefix = await get_prefix(bot, ctx.message)
    embed.set_footer(text=f"Use {prefix}answer <your answer> to solve! (60s)")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="answer", description="Answer an active riddle")
async def answer(ctx: commands.Context, *, response: str):
    if not hasattr(bot, 'active_riddles') or ctx.author.id not in bot.active_riddles:
        return await ctx.send("❌ You don't have an active riddle! Use `.riddle` first.")
    
    riddle_data = bot.active_riddles[ctx.author.id]
    
    if time.time() > riddle_data['expires']:
        del bot.active_riddles[ctx.author.id]
        return await ctx.send("⏰ Your riddle has expired! Try again with `.riddle`.")
    
    if response.lower().strip() == riddle_data['answer']:
        reward = riddle_data['reward']
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', 
                            (reward, ctx.author.id, ctx.guild.id))
            await db.commit()
        
        # Use helper for XP to trigger level up notifications
        leveled_up, new_level = await add_xp(ctx.author.id, ctx.guild.id, 50)
        
        del bot.active_riddles[ctx.author.id]
        msg = f"✅ **CORRECT!** You earned **{reward:,} coins**!"
        if leveled_up:
            msg += f"\n🎊 **LEVEL UP!** You reached **Level {new_level}**!"
        await ctx.send(msg)
    else:
        # Don't delete on wrong answer, let them try until timeout
        await ctx.send("❌ That's not it! Try again.")

@bot.hybrid_command(name="blackjack", aliases=["bj"], description="Play a game of Blackjack")
@app_commands.describe(amount="The amount of coins to bet")
async def blackjack(ctx: commands.Context, amount: str = None):
    if amount is None:
        prefix = await get_prefix(bot, ctx.message)
        return await ctx.send(f"❌ Incorrect format! Use: `{prefix}bj <amount>`")
    
    user = await get_user_data(ctx.author.id, ctx.guild.id)
    balance = user['balance']

    if amount.lower() == 'all':
        bet_amount = balance
    elif amount.lower() == 'half':
        bet_amount = balance // 2
    else:
        try:
            bet_amount = int(amount)
        except ValueError:
            return await ctx.send("❌ Invalid amount! Use a number, 'half', or 'all'.")

    if bet_amount <= 0: return await ctx.send("❌ Bet a positive amount!")
    if balance < bet_amount: return await ctx.send("❌ You don't have enough coins!")

    # Deck setup
    suits = {'♠': '♠️', '♥': '♥️', '♦': '♦️', '♣': '♣️'}
    values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    
    def get_card():
        val = random.choice(values)
        suit_icon = random.choice(list(suits.values()))
        return val, suit_icon

    def calc_hand(hand):
        total = 0
        aces = 0
        for val, _ in hand:
            if val in ['J', 'Q', 'K']: total += 10
            elif val == 'A': aces += 1
            else: total += int(val)
        for _ in range(aces):
            if total + 11 <= 21: total += 11
            else: total += 1
        return total

    player_hand = [get_card(), get_card()]
    dealer_hand = [get_card(), get_card()]

    def format_hand(hand, hide_first=False):
        if hide_first:
            # Show the back emoji for the first card, and the emoji for the second card
            back_emoji = CARD_EMOJIS.get('back', '🎴')
            second_card = hand[1]
            second_emoji = CARD_EMOJIS.get((second_card[0], second_card[1]), f"**[{second_card[0]}]** {second_card[1]}")
            return f"{back_emoji} {second_emoji}"
        
        emojis = []
        for val, suit in hand:
            emoji = CARD_EMOJIS.get((val, suit))
            if emoji:
                emojis.append(emoji)
            else:
                # Fallback for missing cards (J, Q, K, 10 of Spades, Ace of Spades)
                emojis.append(f"**[{val}]** {suit}")
        
        return " ".join(emojis)

    class BlackjackView(discord.ui.View):
        def __init__(self, ctx, can_double=True, can_split=False):
            super().__init__(timeout=30)
            self.ctx = ctx
            self.value = None
            if not can_double:
                self.double_down.disabled = True
            if not can_split:
                self.split.disabled = True

        @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, custom_id="hit")
        async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("This isn't your game!", ephemeral=True)
            self.value = "hit"
            await interaction.response.defer()
            self.stop()

        @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary, custom_id="stand")
        async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("This isn't your game!", ephemeral=True)
            self.value = "stand"
            await interaction.response.defer()
            self.stop()

        @discord.ui.button(label="Double Down", style=discord.ButtonStyle.secondary, custom_id="double")
        async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("This isn't your game!", ephemeral=True)
            self.value = "double"
            await interaction.response.defer()
            self.stop()

        @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary, custom_id="split")
        async def split(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.ctx.author.id:
                return await interaction.response.send_message("This isn't your game!", ephemeral=True)
            await interaction.response.send_message("Split is not yet implemented!", ephemeral=True)

    async def get_bj_embed(show_dealer=False, result_text=None):
        # Using a bright color as requested (Cyan/Bright Blue)
        embed = discord.Embed(color=0x00FFFF) 
        embed.set_author(name=f"{ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        # Dealer side
        if show_dealer:
            d_val = calc_hand(dealer_hand)
            d_str = format_hand(dealer_hand)
        else:
            visible_card_value = calc_hand([dealer_hand[1]])
            d_val = visible_card_value
            d_str = format_hand(dealer_hand, hide_first=True)
        
        # Player side
        p_val = calc_hand(player_hand)

        if result_text:
            # Result formatting like UnbelievaBoat
            embed.description = f"**Result: {result_text}**"
            if "Win" in result_text: embed.color = 0x00ff00 # Bright Green
            elif "Loss" in result_text or "Bust" in result_text or "Timed Out" in result_text: embed.color = 0xff0000 # Bright Red
            else: embed.color = 0xffff00 # Bright Yellow
        
        # Hand display side-by-side
        embed.add_field(name="Your Hand", value=f"{format_hand(player_hand)}\n\n**Value: {p_val}**", inline=True)
        embed.add_field(name="Dealer Hand", value=f"{d_str}\n\n**Value: {d_val}**", inline=True)
        
        return embed

    view = BlackjackView(ctx, can_double=(balance >= bet_amount * 2))
    msg = await ctx.send(embed=await get_bj_embed(), view=view)

    # Game Loop
    while True:
        if calc_hand(player_hand) >= 21:
            break
            
        await view.wait()
        
        if view.value == "hit":
            player_hand.append(get_card())
            if calc_hand(player_hand) >= 21:
                break
            view = BlackjackView(ctx, can_double=False) # Can't double after hitting
            await msg.edit(embed=await get_bj_embed(), view=view)
        elif view.value == "stand":
            break
        elif view.value == "double":
            bet_amount *= 2
            player_hand.append(get_card())
            break

    # Dealer Turn
    p_total = calc_hand(player_hand)
    if p_total > 21:
        result = f"Bust 🍞 -{bet_amount:,}"
        win_status = "loss"
    else:
        # Dealer must hit until 17
        while calc_hand(dealer_hand) < 17:
            dealer_hand.append(get_card())
        
        d_total = calc_hand(dealer_hand)
        if d_total > 21:
            result = f"Win 🍞 +{bet_amount:,}"
            win_status = "win"
        elif d_total > p_total:
            result = f"Loss 🍞 -{bet_amount:,}"
            win_status = "loss"
        elif d_total < p_total:
            result = f"Win 🍞 +{bet_amount:,}"
            win_status = "win"
        else:
            result = f"Push 🍞 +0"
            win_status = "push"

    async with aiosqlite.connect(DB_FILE) as db:
        if win_status == "win":
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (bet_amount, ctx.author.id, ctx.guild.id))
        elif win_status == "loss":
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (bet_amount, ctx.author.id, ctx.guild.id))
        await db.commit()

    await msg.edit(embed=await get_bj_embed(show_dealer=True, result_text=result), view=None)

@bot.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into the bank")
async def deposit(ctx: commands.Context, amount: str):
    user = await get_user_data(ctx.author.id, ctx.guild.id)
    if amount.lower() == 'all':
        amt = user['balance']
    else:
        try: amt = int(amount)
        except: return await ctx.send("Enter a valid number or 'all'.")
    
    if amt <= 0: return await ctx.send("Amount must be positive.")
    if user['balance'] < amt: return await ctx.send("You don't have enough coins!")
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance - ?, bank = bank + ? WHERE user_id = ? AND guild_id = ?', (amt, amt, ctx.author.id, ctx.guild.id))
        await db.commit()
    await ctx.send(f"🏦 Deposited **{amt:,} coins**.")

@bot.hybrid_command(name="withdraw", description="Withdraw coins from your bank")
async def withdraw(ctx: commands.Context, amount: str):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if amount.lower() == 'all':
        amt = data['bank']
    else:
        try: amt = int(amount)
        except: return await ctx.send("Invalid amount.")
    
    if amt <= 0: return await ctx.send("Amount must be positive.")
    if amt > data['bank']: return await ctx.send("You don't have that much in your bank!")
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance + ?, bank = bank - ? WHERE user_id = ? AND guild_id = ?', 
                        (amt, amt, ctx.author.id, ctx.guild.id))
        await db.commit()
    await ctx.send(f"✅ Withdrew **{amt:,} coins**.")

@bot.hybrid_command(name="vote", description="Vote for the bot on Top.gg to get rewards!")
async def vote(ctx: commands.Context):
    await ctx.defer()
    vote_url = f"https://top.gg/bot/{bot.user.id}/vote"
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    now = int(time.time())
    last_vote_time = data['last_vote'] if data['last_vote'] else 0
    time_since_vote = now - last_vote_time
    
    # Debug logging
    print(f"DEBUG: /vote command - User: {ctx.author.id}, Last Vote: {last_vote_time}, Now: {now}, Time Since: {time_since_vote}s")
    
    embed = discord.Embed(title="🗳️ Vote for Empire Nexus", color=0x00d2ff)
    embed.description = f"Support the bot and unlock exclusive rewards for **12 hours**!\n\n" \
                        f"🎁 **Rewards:**\n" \
                        f"• 🏦 **Auto-Deposit:** Passive income goes straight to your bank!\n" \
                        f"• 💰 **Bonus Coins:** (Coming Soon)\n\n" \
                        f"[**Click here to vote on Top.gg**]({vote_url})"
    
    if time_since_vote < 43200:
        remaining = 43200 - time_since_vote
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        embed.add_field(name="✅ Status", value=f"You have already voted! Rewards active for **{hours}h {minutes}m**.")
    else:
        embed.add_field(name="❌ Status", value="You haven't voted in the last 12 hours.")
        
    await ctx.send(embed=embed)

@bot.hybrid_command(name="autodeposit", description="Toggle auto-deposit of passive income (requires active vote)")
async def autodeposit(ctx: commands.Context):
    await ctx.defer()
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    now = int(time.time())
    last_vote_time = data['last_vote'] if data['last_vote'] else 0
    time_since_vote = now - last_vote_time
    is_voter = time_since_vote < 43200
    
    # Debug logging
    print(f"DEBUG: /autodeposit command - User: {ctx.author.id}, Last Vote: {last_vote_time}, Now: {now}, Time Since: {time_since_vote}s, Is Voter: {is_voter}")
    
    if not is_voter:
        vote_url = f"https://top.gg/bot/{bot.user.id}/vote"
        return await ctx.send(f"❌ You need an active vote to use this! [**Vote here**]({vote_url}) to unlock auto-deposit for 12 hours.")
    
    new_state = 0 if data['auto_deposit'] else 1
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET auto_deposit = ? WHERE user_id = ? AND guild_id = ?', (new_state, ctx.author.id, ctx.guild.id))
        await db.commit()
    
    if new_state:
        remaining = 43200 - time_since_vote
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        await ctx.send(f"✅ **Auto-deposit starting now!** You have **{hours}h {minutes}m** left until your vote expires.")
    else:
        await ctx.send("✅ Auto-deposit is now **DISABLED**.")

@bot.hybrid_command(name="shop", description="View the asset shop")
async def shop(ctx: commands.Context):
    assets = await get_guild_assets(ctx.guild.id)
    embed = discord.Embed(title="🛒 Kingdom Asset Shop", description="Buy assets to earn passive income every 10 minutes!", color=0x00d2ff)
    for aid, data in assets.items():
        embed.add_field(name=f"{data['name']} (ID: {aid})", value=f"Price: 🪙 {data['price']:,}\nIncome: 💸 {data['income']:,}/10min", inline=False)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="buy", description="Buy a passive income asset")
async def buy_asset(ctx: commands.Context, asset_id: str, count: int = 1):
    if count <= 0: return await ctx.send("Count must be positive.")
    assets = await get_guild_assets(ctx.guild.id)
    if asset_id not in assets: return await ctx.send("Invalid asset ID!")
    
    asset = assets[asset_id]
    total_price = asset['price'] * count
    user = await get_user_data(ctx.author.id, ctx.guild.id)
    
    if user['balance'] < total_price: return await ctx.send(f"You need **{total_price - user['balance']:,} more coins**!")
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (total_price, ctx.author.id, ctx.guild.id))
        await db.execute('INSERT INTO user_assets (user_id, guild_id, asset_id, count) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, guild_id, asset_id) DO UPDATE SET count = count + ?', 
                        (ctx.author.id, ctx.guild.id, asset_id, count, count))
        await db.commit()
    await ctx.send(f"✅ Bought **{count}x {asset['name']}** for **{total_price:,} coins**!")

@bot.hybrid_command(name="profile", description="View your empire status")
async def profile(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    data = await get_user_data(target.id, ctx.guild.id)
    
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT asset_id, count FROM user_assets WHERE user_id = ? AND guild_id = ? AND count > 0', (target.id, ctx.guild.id)) as cursor:
            assets_rows = await cursor.fetchall()
    
    assets_str = "\n".join([f"• {count}x {aid}" for aid, count in assets_rows]) if assets_rows else "No assets."
    
    embed = discord.Embed(title=f"👑 {target.display_name}'s Empire", color=0x00d2ff)
    embed.add_field(name="📊 Stats", value=f"Level: {data['level']}\nXP: {data['xp']}\nPrestige: {data['prestige']}", inline=True)
    embed.add_field(name="💰 Wealth", value=f"Wallet: {data['balance']:,}\nBank: {data['bank']:,}", inline=True)
    embed.add_field(name="🏗️ Assets", value=assets_str, inline=False)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="crime", description="Commit a crime for high rewards (or risk!)")
@commands.cooldown(1, 1800, commands.BucketType.user)
async def crime(ctx: commands.Context):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    now = int(time.time())
    
    # Keeping the old check as a backup, but commands.cooldown is better
    if now - data['last_crime'] < 1800: 
        return await ctx.send(f"🚔 Cops are searching for you! Wait **{1800 - (now - data['last_crime'])}s**.")
    
    if random.random() < 0.30: # Slightly lower success rate for higher stakes
        earned = random.randint(1000, 3000) * (data['level'])
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance + ?, last_crime = ? WHERE user_id = ? AND guild_id = ?', (earned, now, ctx.author.id, ctx.guild.id))
            await db.commit()
        await ctx.send(f"😈 You pulled off a heist and got **{earned:,} coins**!")
    else:
        loss = random.randint(500, 1000)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = MAX(0, balance - ?), last_crime = ? WHERE user_id = ? AND guild_id = ?', (loss, now, ctx.author.id, ctx.guild.id))
            await db.commit()
        await ctx.send(f"👮 BUSTED! You lost **{loss:,} coins** while escaping.")

# --- Hybrid Commands (Prefix + Slash) ---

@bot.hybrid_command(name="balance", aliases=["bal"], description="Check your balance")
async def balance(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    data = await get_user_data(target.id, ctx.guild.id)
    embed = discord.Embed(title=f"💰 {target.display_name}'s Vault", color=0xf1c40f)
    embed.add_field(name="Wallet", value=f"🪙 `{data['balance']:,}`", inline=True)
    embed.add_field(name="Bank", value=f"🏦 `{data['bank']:,}`", inline=True)
    embed.set_footer(text=f"Total: {data['balance'] + data['bank']:,} coins")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="work", description="Work to earn coins")
@commands.cooldown(1, 300, commands.BucketType.user)
async def work(ctx: commands.Context):
    success, message = await work_logic(ctx.author.id, ctx.guild.id)
    color = 0x2ecc71 if success else 0xe74c3c
    embed = discord.Embed(description=message, color=color)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="rob", description="Try to rob someone")
@app_commands.describe(target="The user you want to rob")
@commands.cooldown(1, 1800, commands.BucketType.user)
async def rob(ctx: commands.Context, target: discord.Member):
    if target.id == ctx.author.id: return await ctx.send("Don't rob yourself.")
    stealer = await get_user_data(ctx.author.id, ctx.guild.id)
    victim = await get_user_data(target.id, ctx.guild.id)
    if victim['balance'] < 500: return await ctx.send("Target is too poor! They need at least 500 coins.")
    
    now = int(time.time())
    if now - stealer['last_rob'] < 1800: 
        return await ctx.send(f"Wait {1800 - (now - stealer['last_rob'])}s.")
    
    if random.random() < 0.35: # Lowered from 0.4
        stolen = random.randint(50, int(victim['balance'] * 0.25)) # Lowered max steal from 30%
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance + ?, last_rob = ? WHERE user_id = ? AND guild_id = ?', (stolen, now, ctx.author.id, ctx.guild.id))
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (stolen, target.id, ctx.guild.id))
            await db.commit()
        embed = discord.Embed(description=f"🧤 Stole **{stolen:,}** from {target.mention}!", color=0x2ecc71)
        await ctx.send(embed=embed)
    else:
        fine = random.randint(300, 600)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = MAX(0, balance - ?), last_rob = ? WHERE user_id = ? AND guild_id = ?', (fine, now, ctx.author.id, ctx.guild.id))
            await db.commit()
        embed = discord.Embed(description=f"🚔 Caught! Fined {fine:,} coins.", color=0xe74c3c)
        await ctx.send(embed=embed)

@bot.hybrid_command(name="buyrole", description="Buy a role from the server shop")
async def buyrole(ctx: commands.Context, role: discord.Role):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT role_shop_json FROM guild_config WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if not row: return await ctx.send("❌ This server hasn't set up a role shop yet!")
            shop = json.loads(row[0])

    role_id = str(role.id)
    if role_id not in shop:
        return await ctx.send("❌ This role is not for sale!")

    price = shop[role_id]
    user = await get_user_data(ctx.author.id, ctx.guild.id)

    if user['balance'] < price:
        return await ctx.send(f"❌ You need **{price - user['balance']:,} more coins**!")

    try:
        await ctx.author.add_roles(role)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (price, ctx.author.id, ctx.guild.id))
            await db.commit()
        await ctx.send(f"✅ Successfully bought the **{role.name}** role!")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to give you that role! (Make sure my role is higher than the one you're buying)")

@bot.hybrid_command(name="rank", description="Check your current level and XP")
async def rank(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    data = await get_user_data(target.id, ctx.guild.id)
    
    xp = data['xp']
    level = data['level']
    needed_xp = level * 500
    
    # Simple progress bar
    progress = min(1.0, xp / needed_xp)
    bar_length = 10
    filled = int(progress * bar_length)
    bar = "🟩" * filled + "⬜" * (bar_length - filled)
    
    embed = discord.Embed(title=f"📊 {target.display_name}'s Rank", color=0x00d2ff)
    embed.add_field(name="Level", value=f"⭐ `{level}`", inline=True)
    embed.add_field(name="Prestige", value=f"👑 `{data['prestige']}`", inline=True)
    embed.add_field(name="Progress", value=f"{bar} ({xp}/{needed_xp} XP)", inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="leaderboard", aliases=["lb"], description="View the global leaderboard")
@app_commands.choices(type=[
    app_commands.Choice(name="Money", value="money"),
    app_commands.Choice(name="XP", value="xp")
])
async def leaderboard(ctx: commands.Context, type: str = "money"):
    async with aiosqlite.connect(DB_FILE) as db:
        if type == "money":
            query = 'SELECT user_id, balance + bank as total FROM users WHERE guild_id = ? ORDER BY total DESC LIMIT 10'
            title = f"🏆 {ctx.guild.name} Wealth Leaderboard"
            symbol = "🪙"
        else:
            query = 'SELECT user_id, level, xp FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10'
            title = f"🏆 {ctx.guild.name} Experience Leaderboard"
            symbol = "⭐"

        async with db.execute(query, (ctx.guild.id,)) as cursor:
            rows = await cursor.fetchall()
    
    if not rows: return await ctx.send("The leaderboard is empty!")
    
    lb_str = ""
    for i, row in enumerate(rows, 1):
        uid = row[0]
        val = row[1]
        user = bot.get_user(uid)
        name = user.name if user else f"Unknown({uid})"
        
        if type == "money":
            lb_str += f"**{i}. {name}** — {symbol} {val:,}\n"
        else:
            level = row[1]
            xp = row[2]
            lb_str += f"**{i}. {name}** — Lvl {level} ({xp} XP)\n"
    
    embed = discord.Embed(title=title, description=lb_str, color=0x00d2ff)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="setup", aliases=["dashboard", "configure"], description="Get the dashboard link to configure the bot")
async def setup_cmd(ctx: commands.Context):
    embed = discord.Embed(
        title="⚙️ Empire Nexus Setup",
        description=(
            "Configure your kingdom, set up the role shop, and create custom assets via the web dashboard.\n\n"
            "🔗 [**Nexus Dashboard**](https://thegoatchessbot.alwaysdata.net/)\n"
            "🛠️ [**Support Server**](https://discord.gg/zsqWFX2gBV)\n\n"
            "*Note: Only server administrators can deploy changes.*"
        ),
        color=0x00d2ff
    )
    embed.set_footer(text="Rule with iron, prosper with gold.")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="setprefix", description="Change the bot's prefix for this server")
@commands.has_permissions(administrator=True)
async def set_prefix_cmd(ctx: commands.Context, new_prefix: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            INSERT INTO guild_config (guild_id, prefix) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix
        ''', (ctx.guild.id, new_prefix))
        await db.commit()
    await ctx.send(f"✅ Prefix successfully updated to `{new_prefix}`")

if __name__ == '__main__':
    bot.run(TOKEN)

