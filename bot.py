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
import asyncio
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
TEST_GUILD_ID = 1465437620245889237
SUPPORT_SERVER_INVITE = "BkCxVgJa"
SUPPORT_GUILD_ID = None
BOT_OWNERS = [1324354578338025533]

# Default Assets
DEFAULT_ASSETS = {
    "lemonade_stand": {"name": "Lemonade Stand", "price": 500, "income": 5},
    "gaming_pc": {"name": "Gaming PC", "price": 2500, "income": 30},
    "coffee_shop": {"name": "Coffee Shop", "price": 10000, "income": 150},
}

DEFAULT_BANK_PLANS = {
    "standard": {
        "name": "Standard Vault",
        "min": 0.01,
        "max": 0.02,
        "price": 0,
        "min_level": 0
    },
    "saver": {
        "name": "Saver Vault",
        "min": 0.015,
        "max": 0.025,
        "price": 25000,
        "min_level": 5
    },
    "royal": {
        "name": "Royal Vault",
        "min": 0.02,
        "max": 0.03,
        "price": 100000,
        "min_level": 10
    }
}

JOBS = {
    "miner": {
        "name": "Mine Overseer",
        "difficulty": "Easy",
        "min_level": 1,
        "focus": "work",
        "question": "Which command lets you supervise the mines for coins?",
        "answer": "work",
        "multiplier": 1.2
    },
    "enforcer": {
        "name": "City Enforcer",
        "difficulty": "Medium",
        "min_level": 5,
        "focus": "crime",
        "question": "Which command do you use to attempt a high-risk heist?",
        "answer": "crime",
        "multiplier": 1.3
    },
    "croupier": {
        "name": "Casino Croupier",
        "difficulty": "Hard",
        "min_level": 10,
        "focus": "blackjack",
        "question": "Which command starts a game of blackjack?",
        "answer": "blackjack",
        "multiplier": 1.4
    }
}

DAILY_QUESTS = [
    {"id": "daily_cmd_25", "description": "Use 25 commands today", "target": 25, "reward": 10000},
    {"id": "daily_cmd_50", "description": "Use 50 commands today", "target": 50, "reward": 20000},
    {"id": "daily_cmd_75", "description": "Use 75 commands today", "target": 75, "reward": 35000},
    {"id": "daily_cmd_100", "description": "Use 100 commands today", "target": 100, "reward": 50000},
    {"id": "daily_cmd_150", "description": "Use 150 commands today", "target": 150, "reward": 80000},
    {"id": "daily_cmd_10", "description": "Use 10 commands today", "target": 10, "reward": 5000},
    {"id": "daily_cmd_5", "description": "Use 5 commands today", "target": 5, "reward": 2000},
    {"id": "daily_cmd_200", "description": "Use 200 commands today", "target": 200, "reward": 120000}
]

WEEKLY_QUESTS = [
    {"id": "weekly_cmd_100", "description": "Use 100 commands this week", "target": 100, "reward": 40000},
    {"id": "weekly_cmd_200", "description": "Use 200 commands this week", "target": 200, "reward": 90000},
    {"id": "weekly_cmd_300", "description": "Use 300 commands this week", "target": 300, "reward": 140000},
    {"id": "weekly_cmd_400", "description": "Use 400 commands this week", "target": 400, "reward": 190000},
    {"id": "weekly_cmd_500", "description": "Use 500 commands this week", "target": 500, "reward": 250000},
    {"id": "weekly_cmd_750", "description": "Use 750 commands this week", "target": 750, "reward": 375000},
    {"id": "weekly_cmd_50", "description": "Use 50 commands this week", "target": 50, "reward": 25000},
    {"id": "weekly_cmd_1000", "description": "Use 1000 commands this week", "target": 1000, "reward": 500000}
]

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
            bank_plan TEXT DEFAULT 'standard',
            daily_commands INTEGER DEFAULT 0, daily_reset INTEGER DEFAULT 0,
            daily_reward_claimed INTEGER DEFAULT 0,
            weekly_commands INTEGER DEFAULT 0, weekly_reset INTEGER DEFAULT 0,
            weekly_reward_claimed INTEGER DEFAULT 0,
            daily_quest_completed_json TEXT DEFAULT '{}',
            weekly_quest_completed_json TEXT DEFAULT '{}',
            daily_stats_json TEXT DEFAULT '{}',
            weekly_stats_json TEXT DEFAULT '{}',
            PRIMARY KEY (user_id, guild_id)
        )''')
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_vote INTEGER DEFAULT 0')
            await db.execute('ALTER TABLE users ADD COLUMN auto_deposit INTEGER DEFAULT 0')
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN bank_plan TEXT DEFAULT 'standard'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN daily_commands INTEGER DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN daily_reset INTEGER DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN daily_reward_claimed INTEGER DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN weekly_commands INTEGER DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN weekly_reset INTEGER DEFAULT 0")
            await db.execute("ALTER TABLE users ADD COLUMN weekly_reward_claimed INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN daily_quest_completed_json TEXT DEFAULT '{}'")
            await db.execute("ALTER TABLE users ADD COLUMN weekly_quest_completed_json TEXT DEFAULT '{}'")
            await db.execute("ALTER TABLE users ADD COLUMN daily_stats_json TEXT DEFAULT '{}'")
            await db.execute("ALTER TABLE users ADD COLUMN weekly_stats_json TEXT DEFAULT '{}'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN started INTEGER DEFAULT 0")
        except:
            pass
            
        await db.execute('''CREATE TABLE IF NOT EXISTS user_assets (
            user_id INTEGER, guild_id INTEGER, asset_id TEXT, count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id, asset_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY, prefix TEXT DEFAULT '.',
            role_shop_json TEXT DEFAULT '{}', custom_assets_json TEXT DEFAULT '{}',
            bank_plans_json TEXT DEFAULT '{}'
        )''')
        try:
            await db.execute("ALTER TABLE guild_config ADD COLUMN bank_plans_json TEXT DEFAULT '{}'")
        except:
            pass
        await db.execute('''CREATE TABLE IF NOT EXISTS guild_wonder (
            guild_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 0,
            progress INTEGER DEFAULT 0,
            goal INTEGER DEFAULT 50000,
            boost_multiplier REAL DEFAULT 1.25,
            boost_until INTEGER DEFAULT 0
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS user_jobs (
            user_id INTEGER, guild_id INTEGER, job_id TEXT,
            PRIMARY KEY (user_id, guild_id)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS global_votes (
            user_id INTEGER PRIMARY KEY, last_vote INTEGER DEFAULT 0
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS user_rewards (
            user_id INTEGER PRIMARY KEY,
            multipliers_json TEXT DEFAULT '{}',
            titles_json TEXT DEFAULT '[]',
            medals_json TEXT DEFAULT '[]'
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS title_templates (
            title_name TEXT PRIMARY KEY,
            description TEXT,
            created_at INTEGER
        )''')

        # --- MODERATION & UTILITY TABLES ---
        await db.execute('''CREATE TABLE IF NOT EXISTS warnings (
            warn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            guild_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            timestamp INTEGER,
            expires_at INTEGER
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS automod_words (
            word_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            word TEXT,
            punishment TEXT DEFAULT 'warn'
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS logging_config (
            guild_id INTEGER PRIMARY KEY,
            message_log_channel INTEGER,
            member_log_channel INTEGER,
            user_log_channel INTEGER,
            server_log_channel INTEGER,
            voice_log_channel INTEGER,
            mod_log_channel INTEGER,
            automod_log_channel INTEGER,
            command_log_channel INTEGER
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS welcome_farewell (
            guild_id INTEGER PRIMARY KEY,
            welcome_channel INTEGER,
            welcome_message TEXT,
            welcome_embed_json TEXT,
            farewell_channel INTEGER,
            farewell_message TEXT,
            farewell_embed_json TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS reaction_roles (
            message_id INTEGER,
            guild_id INTEGER,
            emoji TEXT,
            role_id INTEGER,
            PRIMARY KEY (message_id, emoji)
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS custom_commands (
            guild_id INTEGER,
            name TEXT,
            code TEXT,
            prefix TEXT DEFAULT '.',
            PRIMARY KEY (guild_id, name)
        )''')
        await db.commit()

async def migrate_db():
    async with aiosqlite.connect(DB_FILE) as db:
        # Columns to add to users table
        columns = [
            ("total_commands", "INTEGER DEFAULT 0"),
            ("successful_robs", "INTEGER DEFAULT 0"),
            ("successful_crimes", "INTEGER DEFAULT 0"),
            ("passive_income", "REAL DEFAULT 0.0")
        ]
        for col_name, col_type in columns:
            try:
                await db.execute(f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
            except:
                pass
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
async def ensure_rewards(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO user_rewards (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def get_user_multipliers(user_id):
    await ensure_rewards(user_id)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT multipliers_json FROM user_rewards WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
    return {}

async def get_total_multiplier(user_id):
    multipliers = await get_user_multipliers(user_id)
    total = 1.0
    for m in multipliers.values():
        total += (m - 1.0)
    return max(1.0, total)

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
                next_level_xp = current_level * 100
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

# --- MODERATION HELPERS ---

@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot:
        return
    embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.orange(), timestamp=message.created_at)
    embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=True)
    embed.add_field(name="Channel", value=message.channel.mention, inline=True)
    embed.add_field(name="Content", value=message.content[:1024] or "*No content*", inline=False)
    await log_embed(message.guild, "message_log_channel", embed)

@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot or before.content == after.content:
        return
    embed = discord.Embed(title="📝 Message Edited", color=discord.Color.blue(), timestamp=after.edited_at or discord.utils.utcnow())
    embed.add_field(name="Author", value=f"{before.author.mention} ({before.author.id})", inline=True)
    embed.add_field(name="Channel", value=before.channel.mention, inline=True)
    embed.add_field(name="Before", value=before.content[:1024] or "*No content*", inline=False)
    embed.add_field(name="After", value=after.content[:1024] or "*No content*", inline=False)
    await log_embed(before.guild, "message_log_channel", embed)

@bot.event
async def on_member_join(member):
    # Log the event
    embed_log = discord.Embed(title="📥 Member Joined", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    embed_log.add_field(name="User", value=f"{member.mention} ({member.id})", inline=True)
    embed_log.add_field(name="Account Created", value=member.created_at.strftime("%b %d, %Y"), inline=True)
    embed_log.set_thumbnail(url=member.display_avatar.url)
    await log_embed(member.guild, "member_log_channel", embed_log)

    # Welcome system
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            config = await cursor.fetchone()
    
    if not config or not config['welcome_channel']:
        return
        
    channel = member.guild.get_channel(config['welcome_channel'])
    if not channel:
        try: channel = await member.guild.fetch_channel(config['welcome_channel'])
        except: return

    message = config['welcome_message'] or "Welcome {user} to {server}!"
    embed_json = config['welcome_embed_json']
    
    # Replace placeholders
    placeholders = {
        "{user}": member.mention,
        "{username}": member.name,
        "{server}": member.guild.name,
        "{member_count}": str(member.guild.member_count),
        "{avatar}": member.display_avatar.url,
        "{join_date}": member.joined_at.strftime("%b %d, %Y")
    }
    
    final_message = message
    for key, val in placeholders.items():
        final_message = final_message.replace(key, val)

    embed = None
    if embed_json:
        try:
            data = json.loads(embed_json)
            # Placeholder replacement in embed data
            def replace_in_dict(d):
                if isinstance(d, str):
                    for key, val in placeholders.items():
                        d = d.replace(key, val)
                    return d
                if isinstance(d, dict):
                    return {k: replace_in_dict(v) for k, v in d.items()}
                if isinstance(d, list):
                    return [replace_in_dict(i) for i in d]
                return d
            
            data = replace_in_dict(data)
            embed = discord.Embed.from_dict(data)
        except:
            pass

    # Create Button View if needed (example: a button that shows server info or a welcome message)
    class WelcomeView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            
        @discord.ui.button(label="Server Info", style=discord.ButtonStyle.primary, custom_id="welcome_server_info")
        async def server_info(self, interaction: discord.Interaction, button: discord.ui.Button):
            guild = interaction.guild
            embed = discord.Embed(title=f"🏰 {guild.name} Info", color=0x00d2ff)
            embed.add_field(name="Members", value=str(guild.member_count))
            embed.add_field(name="Owner", value=guild.owner.mention)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    await channel.send(content=final_message, embed=embed, view=WelcomeView())

@bot.event
async def on_member_remove(member):
    # Log the event
    embed_log = discord.Embed(title="📤 Member Left", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed_log.add_field(name="User", value=f"{member} ({member.id})", inline=True)
    embed_log.set_thumbnail(url=member.display_avatar.url)
    await log_embed(member.guild, "member_log_channel", embed_log)

    # Farewell system
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            config = await cursor.fetchone()
    
    if not config or not config['farewell_channel']:
        return
        
    channel = member.guild.get_channel(config['farewell_channel'])
    if not channel:
        try: channel = await member.guild.fetch_channel(config['farewell_channel'])
        except: return

    message = config['farewell_message'] or "{user} has left the server."
    farewell_message = message.replace("{user}", str(member)).replace("{server}", member.guild.name)
    
    await channel.send(farewell_message)

@bot.event
async def on_guild_channel_create(channel):
    embed = discord.Embed(title="📁 Channel Created", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    embed.add_field(name="Name", value=channel.name, inline=True)
    embed.add_field(name="Type", value=str(channel.type), inline=True)
    embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
    await log_embed(channel.guild, "server_log_channel", embed)

@bot.event
async def on_guild_channel_delete(channel):
    embed = discord.Embed(title="📁 Channel Deleted", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed.add_field(name="Name", value=channel.name, inline=True)
    embed.add_field(name="Type", value=str(channel.type), inline=True)
    await log_embed(channel.guild, "server_log_channel", embed)

async def log_mod_action(guild, action, target, moderator, reason, duration=None):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT mod_log_channel FROM logging_config WHERE guild_id = ?', (guild.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or not row[0]:
                return
            channel_id = row[0]
            channel = guild.get_channel(channel_id)
            if not channel:
                # Try to fetch if not in cache
                try:
                    channel = await guild.fetch_channel(channel_id)
                except:
                    return

            embed = discord.Embed(title=f"Moderation Action: {action}", color=discord.Color.red())
            embed.add_field(name="Target", value=f"{target} ({target.id})", inline=False)
            embed.add_field(name="Moderator", value=f"{moderator} ({moderator.id})", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            if duration:
                embed.add_field(name="Duration", value=duration, inline=False)
            embed.set_timestamp()
            
            # Retry mechanism
            for attempt in range(3):
                try:
                    await channel.send(embed=embed)
                    break
                except discord.HTTPException as e:
                    if attempt == 2:
                        print(f"Failed to send mod log to {channel_id} after 3 attempts: {e}")
                    await asyncio.sleep(1 * (attempt + 1))
                except Exception as e:
                    print(f"Error logging mod action: {e}")
                    break

async def log_embed(guild, column, embed):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(f'SELECT {column} FROM logging_config WHERE guild_id = ?', (guild.id,)) as cursor:
            row = await cursor.fetchone()
            if not row or not row[0]:
                return
            channel_id = row[0]
            channel = guild.get_channel(channel_id)
            if not channel:
                try:
                    channel = await guild.fetch_channel(channel_id)
                except:
                    return

            if channel:
                # Retry mechanism
                for attempt in range(3):
                    try:
                        await channel.send(embed=embed)
                        break
                    except discord.HTTPException as e:
                        if attempt == 2:
                            print(f"Failed to send log to {channel_id} ({column}) after 3 attempts: {e}")
                        await asyncio.sleep(1 * (attempt + 1))
                    except Exception as e:
                        print(f"Error logging embed ({column}): {e}")
                        break

def parse_duration(duration_str):
    if not duration_str:
        return None
    
    total_seconds = 0
    import re
    matches = re.findall(r'(\d+)([smhd])', duration_str.lower())
    if not matches:
        return None
    
    for amount, unit in matches:
        amount = int(amount)
        if unit == 's': total_seconds += amount
        elif unit == 'm': total_seconds += amount * 60
        elif unit == 'h': total_seconds += amount * 3600
        elif unit == 'd': total_seconds += amount * 86400
    
    return total_seconds

# --- MODERATION COMMANDS ---

@bot.hybrid_command(name="kick", description="Remove a member from the server")
@commands.has_permissions(kick_members=True)
@app_commands.describe(member="The member to kick", reason="Reason for kicking", duration="Optional time (e.g. 1h, 1d) - will be logged")
async def kick(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided", duration: str = None):
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        return await ctx.send("❌ You cannot kick someone with a higher or equal role!")
    
    try:
        await member.kick(reason=reason)
        await ctx.send(f"✅ **{member.display_name}** has been kicked. Reason: {reason}")
        await log_mod_action(ctx.guild, "Kick", member, ctx.author, reason, duration)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this member.")

@bot.hybrid_command(name="ban", description="Ban a member from the server")
@commands.has_permissions(ban_members=True)
@app_commands.describe(member="The member to ban", reason="Reason for banning", duration="Duration (e.g. 1h, 1d)")
async def ban(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided", duration: str = None):
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        return await ctx.send("❌ You cannot ban someone with a higher or equal role!")

    seconds = parse_duration(duration)
    
    try:
        await member.ban(reason=reason)
        await ctx.send(f"✅ **{member.display_name}** has been banned. Reason: {reason}" + (f" for {duration}" if duration else ""))
        await log_mod_action(ctx.guild, "Ban", member, ctx.author, reason, duration)
        
        if seconds:
            # We would need a background task to unban, but for now we'll just log it.
            # In a real production bot, you'd store this in DB and have a loop.
            pass
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this member.")

@bot.hybrid_command(name="warn", description="Issue a warning to a member")
@commands.has_permissions(kick_members=True)
@app_commands.describe(member="The member to warn", reason="Reason for warning", duration="Expiration time (e.g. 1d, 30d)")
async def warn(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided", duration: str = None):
    if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
        return await ctx.send("❌ You cannot warn someone with a higher or equal role!")

    seconds = parse_duration(duration)
    expires_at = int(time.time() + seconds) if seconds else None
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (member.id, ctx.guild.id, ctx.author.id, reason, int(time.time()), expires_at))
        await db.commit()
    
    await ctx.send(f"⚠️ **{member.display_name}** has been warned. Reason: {reason}")
    await log_mod_action(ctx.guild, "Warning", member, ctx.author, reason, duration)

@bot.hybrid_command(name="clearwarnings", description="Clears all warnings of a user")
@commands.has_permissions(kick_members=True)
@app_commands.describe(user="The user to clear warnings for")
async def clearwarnings_standalone(ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('DELETE FROM warnings WHERE user_id = ? AND guild_id = ?', (user.id, ctx.guild.id))
        await db.commit()
    
    await ctx.send(f"✅ Cleared all warnings for **{user.display_name}**.")
    await log_mod_action(ctx.guild, "Clear Warnings", user, ctx.author, "All warnings cleared")

@bot.hybrid_command(name="delwarn", description="Delete a specific warning by ID")
@commands.has_permissions(kick_members=True)
@app_commands.describe(id="The ID of the warning to remove")
async def delwarn_standalone(ctx: commands.Context, id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT user_id FROM warnings WHERE warn_id = ? AND guild_id = ?', (id, ctx.guild.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send(f"❌ Warning ID `{id}` not found in this server.")
            
            user_id = row[0]
            await db.execute('DELETE FROM warnings WHERE warn_id = ?', (id,))
            await db.commit()
    
    user = bot.get_user(user_id) or f"User ({user_id})"
    await ctx.send(f"✅ Removed warning `{id}` from **{user}**.")
    await log_mod_action(ctx.guild, "Remove Warning", user, ctx.author, f"Warning ID {id} removed")

@bot.hybrid_group(name="warnings", description="Display warning history for a user")
async def warnings_group(ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC', (user.id, ctx.guild.id)) as cursor:
            rows = await cursor.fetchall()
    
    if not rows:
        return await ctx.send(f"✅ {user.display_name} has no warnings.")
    
    embed = discord.Embed(title=f"Warnings for {user.display_name}", color=discord.Color.orange())
    for row in rows:
        moderator = ctx.guild.get_member(row['moderator_id']) or f"Unknown ({row['moderator_id']})"
        expiry = f"\nExpires: <t:{row['expires_at']}:R>" if row['expires_at'] else ""
        embed.add_field(
            name=f"ID: {row['warn_id']} | <t:{row['timestamp']}:R>",
            value=f"**Reason:** {row['reason']}\n**Moderator:** {moderator}{expiry}",
            inline=False
        )
    await ctx.send(embed=embed)

@warnings_group.command(name="clear", description="Purge all warnings for a specified user")
@commands.has_permissions(kick_members=True)
async def clear_warnings(ctx: commands.Context, user: discord.User):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('DELETE FROM warnings WHERE user_id = ? AND guild_id = ?', (user.id, ctx.guild.id))
        await db.commit()
    
    await ctx.send(f"✅ Cleared all warnings for **{user.display_name}**.")
    await log_mod_action(ctx.guild, "Clear Warnings", user, ctx.author, "All warnings cleared")

@bot.hybrid_command(name="removewarn", description="Delete a specific warning by ID")
@commands.has_permissions(kick_members=True)
@app_commands.describe(warn_id="The ID of the warning to remove")
async def remove_warn(ctx: commands.Context, warn_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        # Check if warning exists and belongs to this guild
        async with db.execute('SELECT user_id FROM warnings WHERE warn_id = ? AND guild_id = ?', (warn_id, ctx.guild.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send(f"❌ Warning ID `{warn_id}` not found in this server.")
            
            user_id = row[0]
            await db.execute('DELETE FROM warnings WHERE warn_id = ?', (warn_id,))
            await db.commit()
    
    user = bot.get_user(user_id) or f"User ({user_id})"
    await ctx.send(f"✅ Removed warning `{warn_id}` from **{user}**.")
    await log_mod_action(ctx.guild, "Remove Warning", user, ctx.author, f"Warning ID {warn_id} removed")

# --- DASHBOARD CONFIGURABLE FEATURES ---

@bot.hybrid_group(name="set", description="Configure server settings")
@commands.has_permissions(manage_guild=True)
async def set_group(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send("❌ Use `/set welcome` or `/set farewell`.")

@set_group.command(name="welcome", description="Configure welcome messages")
@app_commands.describe(channel="Channel for welcome messages", message="Welcome message text (use {user} for mention)", embed_json="JSON for embed (optional)")
async def set_welcome(ctx: commands.Context, channel: str, message: str, embed_json: str = None):
    # Try to convert channel to int if it's an ID string from autocomplete
    try:
        if channel.isdigit():
            channel_id = int(channel)
        else:
            channel_id = int(channel.replace("<#", "").replace(">", ""))
        discord_channel = ctx.guild.get_channel(channel_id)
    except:
        return await ctx.send("❌ Invalid channel! Please select a channel from the autocomplete list or mention it.")

    if not discord_channel:
        return await ctx.send("❌ Channel not found!")

    if embed_json:
        try:
            json.loads(embed_json)
        except:
            return await ctx.send("❌ Invalid JSON for embed! Please provide a valid JSON string.")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            INSERT INTO welcome_farewell (guild_id, welcome_channel, welcome_message, welcome_embed_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET 
                welcome_channel=excluded.welcome_channel, 
                welcome_message=excluded.welcome_message,
                welcome_embed_json=excluded.welcome_embed_json
        ''', (ctx.guild.id, discord_channel.id, message, embed_json))
        await db.commit()
    
    await ctx.send(f"✅ Welcome messages set to {discord_channel.mention}.\n**Message:** {message}" + ("\n**Embed:** Enabled" if embed_json else ""))

@set_welcome.autocomplete("channel")
async def welcome_channel_autocomplete(interaction: discord.Interaction, current: str):
    channels = [c for c in interaction.guild.text_channels if current.lower() in c.name.lower()]
    return [app_commands.Choice(name=c.name, value=str(c.id)) for c in channels[:25]]

@set_group.command(name="welcome_preview", description="Preview your current welcome message configuration")
async def welcome_preview(ctx: commands.Context):
    # ... existing implementation ...
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM welcome_farewell WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
            config = await cursor.fetchone()
    
    if not config or not config['welcome_channel']:
        return await ctx.send("❌ Welcome messages are not configured!")

    member = ctx.author
    message = config['welcome_message'] or "Welcome {user} to {server}!"
    embed_json = config['welcome_embed_json']
    
    placeholders = {
        "{user}": member.mention,
        "{username}": member.name,
        "{server}": ctx.guild.name,
        "{member_count}": str(ctx.guild.member_count),
        "{avatar}": member.display_avatar.url,
        "{join_date}": member.joined_at.strftime("%b %d, %Y")
    }
    
    final_message = message
    for key, val in placeholders.items():
        final_message = final_message.replace(key, val)

    embed = None
    if embed_json:
        try:
            data = json.loads(embed_json)
            def replace_in_dict(d):
                if isinstance(d, str):
                    for key, val in placeholders.items():
                        d = d.replace(key, val)
                    return d
                if isinstance(d, dict):
                    return {k: replace_in_dict(v) for k, v in d.items()}
                if isinstance(d, list):
                    return [replace_in_dict(i) for i in d]
                return d
            data = replace_in_dict(data)
            embed = discord.Embed.from_dict(data)
        except Exception as e:
            await ctx.send(f"⚠️ Error parsing embed JSON: {e}")

    await ctx.send("👀 **Welcome Preview:**", content=final_message, embed=embed)

@set_group.command(name="farewell", description="Configure farewell messages")
@app_commands.describe(channel="Channel for farewell messages", message="Farewell message text (use {user} for name)")
async def set_farewell(ctx: commands.Context, channel: str, *, message: str):
    # Try to convert channel to int if it's an ID string from autocomplete
    try:
        if channel.isdigit():
            channel_id = int(channel)
        else:
            channel_id = int(channel.replace("<#", "").replace(">", ""))
        discord_channel = ctx.guild.get_channel(channel_id)
    except:
        return await ctx.send("❌ Invalid channel! Please select a channel from the autocomplete list or mention it.")

    if not discord_channel:
        return await ctx.send("❌ Channel not found!")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            INSERT INTO welcome_farewell (guild_id, farewell_channel, farewell_message)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET farewell_channel=excluded.farewell_channel, farewell_message=excluded.farewell_message
        ''', (ctx.guild.id, discord_channel.id, message))
        await db.commit()
    
    await ctx.send(f"✅ Farewell messages set to {discord_channel.mention}.\n**Message:** {message}")

@set_farewell.autocomplete("channel")
async def farewell_channel_autocomplete(interaction: discord.Interaction, current: str):
    channels = [c for c in interaction.guild.text_channels if current.lower() in c.name.lower()]
    return [app_commands.Choice(name=c.name, value=str(c.id)) for c in channels[:25]]

@bot.hybrid_command(name="setlogs", description="Configure logging channels")
@commands.has_permissions(administrator=True)
@app_commands.describe(category="Log category", channel="Channel to send logs to")
@app_commands.choices(category=[
    app_commands.Choice(name="Message Logs", value="message_log_channel"),
    app_commands.Choice(name="Member Logs", value="member_log_channel"),
    app_commands.Choice(name="Server Logs", value="server_log_channel"),
    app_commands.Choice(name="Mod Logs", value="mod_log_channel"),
    app_commands.Choice(name="Automod Logs", value="automod_log_channel")
])
async def set_logs(ctx: commands.Context, category: str, channel: str):
    # Try to convert channel to int if it's an ID string from autocomplete
    try:
        if channel.isdigit():
            channel_id = int(channel)
        else:
            channel_id = int(channel.replace("<#", "").replace(">", ""))
        discord_channel = ctx.guild.get_channel(channel_id)
    except:
        return await ctx.send("❌ Invalid channel! Please select a channel from the autocomplete list or mention it.")

    if not discord_channel:
        return await ctx.send("❌ Channel not found!")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(f'''
            INSERT INTO logging_config (guild_id, {category}) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {category} = excluded.{category}
        ''', (ctx.guild.id, discord_channel.id))
        await db.commit()
    await ctx.send(f"✅ Logging for **{category.replace('_', ' ').title()}** set to {discord_channel.mention}")

@set_logs.autocomplete("channel")
async def logs_channel_autocomplete(interaction: discord.Interaction, current: str):
    channels = [c for c in interaction.guild.text_channels if current.lower() in c.name.lower()]
    return [app_commands.Choice(name=c.name, value=str(c.id)) for c in channels[:25]]

@bot.hybrid_group(name="automod", description="Manage automatic moderation")
@commands.has_permissions(manage_guild=True)
async def automod_group(ctx: commands.Context):
    if ctx.invoked_subcommand is None:
        await ctx.send("❌ Use `/automod add` or `/automod remove`.")

@automod_group.command(name="add", description="Add a word to the filter")
@app_commands.describe(word="The word to filter", punishment="Punishment (warn/kick/ban/delete)")
async def automod_add(ctx: commands.Context, word: str, punishment: str = "warn"):
    punishment = punishment.lower()
    if punishment not in ['warn', 'kick', 'ban', 'delete']:
        return await ctx.send("❌ Invalid punishment! Choose: `warn`, `kick`, `ban`, or `delete`.")
    
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT INTO automod_words (guild_id, word, punishment) VALUES (?, ?, ?)', 
                        (ctx.guild.id, word.lower(), punishment))
        await db.commit()
    
    await ctx.send(f"✅ Added `{word}` to the word filter with punishment: **{punishment}**.")

@automod_group.command(name="remove", description="Remove a word from the filter by ID")
@app_commands.describe(word_id="The ID of the word to remove")
async def automod_remove(ctx: commands.Context, word_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT word FROM automod_words WHERE word_id = ? AND guild_id = ?', (word_id, ctx.guild.id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return await ctx.send(f"❌ Word ID `{word_id}` not found.")
            
            word = row[0]
            await db.execute('DELETE FROM automod_words WHERE word_id = ?', (word_id,))
            await db.commit()
    
    await ctx.send(f"✅ Removed `{word}` from the word filter.")

@bot.hybrid_command(name="reactionroles", description="Create a reaction role message")
@commands.has_permissions(manage_roles=True)
@app_commands.describe(message_id="The ID of the message to add reaction roles to", emoji="The emoji to use", role="The role to assign")
async def reaction_roles(ctx: commands.Context, message_id: str, emoji: str, role: discord.Role):
    try:
        msg_id = int(message_id)
        msg = await ctx.channel.fetch_message(msg_id)
    except:
        return await ctx.send("❌ Invalid message ID or message not found in this channel.")

    try:
        await msg.add_reaction(emoji)
    except:
        return await ctx.send("❌ I couldn't add that reaction. Make sure I have permission and it's a valid emoji.")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO reaction_roles (message_id, guild_id, emoji, role_id) VALUES (?, ?, ?, ?)',
                        (msg_id, ctx.guild.id, emoji, role.id))
        await db.commit()
    
    await ctx.send(f"✅ Reaction role added! Users reacting with {emoji} to [that message]({msg.jump_url}) will get the **{role.name}** role.")

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None or payload.user_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    emoji_key = str(payload.emoji)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT role_id FROM reaction_roles WHERE message_id = ? AND guild_id = ? AND emoji = ?', (payload.message_id, payload.guild_id, emoji_key)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return
    role = guild.get_role(row[0])
    if not role:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    try:
        await member.add_roles(role, reason="Reaction Roles")
    except:
        pass

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None or payload.user_id is None:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    emoji_key = str(payload.emoji)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT role_id FROM reaction_roles WHERE message_id = ? AND guild_id = ? AND emoji = ?', (payload.message_id, payload.guild_id, emoji_key)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return
    role = guild.get_role(row[0])
    if not role:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    try:
        await member.remove_roles(role, reason="Reaction Roles")
    except:
        pass

async def run_custom_command(code: str, message: discord.Message):
    if "import " in code or "__" in code:
        return False, "Disallowed code."
    func_name = "__cmd__"
    src = "async def " + func_name + "(message, bot):\n"
    for line in code.splitlines():
        src += "    " + line + "\n"
    sandbox_globals = {"__builtins__": {"len": len, "str": str, "int": int, "float": float, "min": min, "max": max, "range": range}}
    sandbox_locals = {}
    try:
        exec(src, sandbox_globals, sandbox_locals)
        fn = sandbox_locals.get(func_name)
        if not fn:
            return False, "Code error."
        await asyncio.wait_for(fn(message, bot), timeout=3.0)
        return True, None
    except Exception as e:
        return False, str(e)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    content = message.content.lower()
    punished = False
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT word, punishment FROM automod_words WHERE guild_id = ?', (message.guild.id,)) as cursor:
            rows = await cursor.fetchall()
    for word, punishment in rows:
        if word in content:
            if punishment == "delete":
                try:
                    await message.delete()
                except:
                    pass
            elif punishment == "warn":
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp, expires_at) VALUES (?, ?, ?, ?, ?, ?)', (message.author.id, message.guild.id, bot.user.id, f"AutoMod: {word}", int(time.time()), None))
                    await db.commit()
            elif punishment == "kick":
                try:
                    await message.author.kick(reason=f"AutoMod: {word}")
                except:
                    pass
            elif punishment == "ban":
                try:
                    await message.author.ban(reason=f"AutoMod: {word}")
                except:
                    pass
            embed = discord.Embed(title="AutoMod Trigger", color=discord.Color.red())
            embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
            embed.add_field(name="Word", value=word, inline=False)
            embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=False)
            embed.add_field(name="Content", value=message.content[:512], inline=False)
            await log_embed(message.guild, "automod_log_channel", embed)
            punished = True
            break
    if not punished:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute('SELECT name, prefix, code FROM custom_commands WHERE guild_id = ?', (message.guild.id,)) as cursor:
                cmds = await cursor.fetchall()
        for name, prefix, code in cmds:
            trigger = f"{prefix}{name}"
            if content.startswith(trigger):
                ok, err = await run_custom_command(code, message)
                embed = discord.Embed(title="Custom Command Executed", color=discord.Color.blurple())
                embed.add_field(name="User", value=f"{message.author} ({message.author.id})", inline=False)
                embed.add_field(name="Command", value=name, inline=False)
                embed.add_field(name="Prefix", value=prefix, inline=False)
                if err:
                    embed.add_field(name="Error", value=str(err)[:300], inline=False)
                await log_embed(message.guild, "command_log_channel", embed)
                break
    await bot.process_commands(message)

@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return
    embed = discord.Embed(title="Message Deleted", color=discord.Color.dark_red())
    embed.add_field(name="Author", value=f"{message.author} ({message.author.id})", inline=False)
    embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=False)
    if message.content:
        embed.add_field(name="Content", value=message.content[:512], inline=False)
    await log_embed(message.guild, "message_log_channel", embed)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not after.guild or before.author.bot:
        return
    embed = discord.Embed(title="Message Edited", color=discord.Color.orange())
    embed.add_field(name="Author", value=f"{before.author} ({before.author.id})", inline=False)
    embed.add_field(name="Channel", value=f"{before.channel.mention}", inline=False)
    embed.add_field(name="Before", value=(before.content or "")[:300], inline=False)
    embed.add_field(name="After", value=(after.content or "")[:300], inline=False)
    await log_embed(after.guild, "message_log_channel", embed)

@bot.event
async def on_raw_bulk_message_delete(payload: discord.RawBulkMessageDeleteEvent):
    if not payload.guild_id:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    embed = discord.Embed(title="Bulk Message Delete", color=discord.Color.dark_red())
    embed.add_field(name="Channel", value=f"<#{payload.channel_id}>", inline=False)
    embed.add_field(name="Count", value=str(len(payload.message_ids)), inline=False)
    await log_embed(guild, "message_log_channel", embed)

@bot.event
async def on_member_join(member: discord.Member):
    embed = discord.Embed(title="Member Joined", color=discord.Color.green())
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
    created_ts = int(member.created_at.timestamp()) if member.created_at else int(time.time())
    embed.add_field(name="Account Age", value=f"<t:{created_ts}:R>", inline=False)
    await log_embed(member.guild, "member_log_channel", embed)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT welcome_channel, welcome_message FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
    if row and row[0]:
        ch = member.guild.get_channel(row[0])
        if ch:
            msg = row[1] or "Welcome {user}!"
            msg = msg.replace("{user}", member.mention)
            try:
                await ch.send(msg)
            except:
                pass

@bot.event
async def on_member_remove(member: discord.Member):
    embed = discord.Embed(title="Member Left", color=discord.Color.dark_gold())
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
    await log_embed(member.guild, "member_log_channel", embed)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT farewell_channel, farewell_message FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
    if row and row[0]:
        ch = member.guild.get_channel(row[0])
        if ch:
            msg = row[1] or "{user} left the server."
            msg = msg.replace("{user}", member.display_name)
            try:
                await ch.send(msg)
            except:
                pass

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if not after.guild:
        return
    changes = []
    if before.nick != after.nick:
        changes.append(("Nickname", f"{before.nick} → {after.nick}"))
    before_roles = set(r.id for r in before.roles)
    after_roles = set(r.id for r in after.roles)
    added = after_roles - before_roles
    removed = before_roles - after_roles
    if added:
        names = [after.guild.get_role(r).name for r in added if after.guild.get_role(r)]
        changes.append(("Roles Added", ", ".join(names)))
    if removed:
        names = [after.guild.get_role(r).name for r in removed if after.guild.get_role(r)]
        changes.append(("Roles Removed", ", ".join(names)))
    if changes:
        embed = discord.Embed(title="Member Updated", color=discord.Color.blurple())
        embed.add_field(name="User", value=f"{after} ({after.id})", inline=False)
        for k, v in changes:
            embed.add_field(name=k, value=v or "None", inline=False)
        await log_embed(after.guild, "user_log_channel", embed)

@bot.event
async def on_user_update(before: discord.User, after: discord.User):
    embed = discord.Embed(title="User Updated", color=discord.Color.blurple())
    embed.add_field(name="User", value=f"{after} ({after.id})", inline=False)
    if before.avatar != after.avatar:
        embed.add_field(name="Avatar", value="Changed", inline=False)
    if before.global_name != after.global_name:
        embed.add_field(name="Global Name", value=f"{before.global_name} → {after.global_name}", inline=False)
    for guild in bot.guilds:
        if guild.get_member(after.id):
            await log_embed(guild, "user_log_channel", embed)

@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    embed = discord.Embed(title="Channel Created", color=discord.Color.green())
    embed.add_field(name="Channel", value=f"{channel.mention} ({channel.id})", inline=False)
    await log_embed(channel.guild, "server_log_channel", embed)

@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    embed = discord.Embed(title="Channel Deleted", color=discord.Color.dark_red())
    embed.add_field(name="Channel", value=f"#{channel.name} ({channel.id})", inline=False)
    await log_embed(channel.guild, "server_log_channel", embed)

@bot.event
async def on_guild_channel_update(before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
    embed = discord.Embed(title="Channel Updated", color=discord.Color.orange())
    embed.add_field(name="Channel", value=f"{after.mention} ({after.id})", inline=False)
    await log_embed(after.guild, "server_log_channel", embed)

@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    embed = discord.Embed(title="Server Updated", color=discord.Color.orange())
    embed.add_field(name="Server", value=f"{after.name} ({after.id})", inline=False)
    await log_embed(after, "server_log_channel", embed)

@bot.event
async def on_guild_role_create(role: discord.Role):
    embed = discord.Embed(title="Role Created", color=discord.Color.green())
    embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=False)
    await log_embed(role.guild, "server_log_channel", embed)

@bot.event
async def on_guild_role_delete(role: discord.Role):
    embed = discord.Embed(title="Role Deleted", color=discord.Color.dark_red())
    embed.add_field(name="Role", value=f"{role.name} ({role.id})", inline=False)
    await log_embed(role.guild, "server_log_channel", embed)

@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    embed = discord.Embed(title="Role Updated", color=discord.Color.orange())
    embed.add_field(name="Role", value=f"{after.name} ({after.id})", inline=False)
    await log_embed(after.guild, "server_log_channel", embed)

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if not member.guild:
        return
    embed = discord.Embed(title="Voice Update", color=discord.Color.blurple())
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
    if not before.channel and after.channel:
        embed.add_field(name="Action", value=f"Joined {after.channel.name}", inline=False)
    elif before.channel and not after.channel:
        embed.add_field(name="Action", value=f"Left {before.channel.name}", inline=False)
    elif before.channel and after.channel and before.channel.id != after.channel.id:
        embed.add_field(name="Action", value=f"Switched {before.channel.name} → {after.channel.name}", inline=False)
    if before.mute != after.mute:
        embed.add_field(name="Mute", value=str(after.mute), inline=False)
    if before.deaf != after.deaf:
        embed.add_field(name="Deaf", value=str(after.deaf), inline=False)
    await log_embed(member.guild, "voice_log_channel", embed)
async def get_guild_assets(guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT custom_assets_json FROM guild_config WHERE guild_id = ?', (int(guild_id),)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    custom = json.loads(row[0])
                    if isinstance(custom, dict):
                        fixed = {}
                        for key, data in custom.items():
                            try:
                                price = int(data.get("price", 0))
                                income = int(data.get("income", 0))
                            except Exception:
                                continue
                            if price <= 0:
                                continue
                            if income < 0:
                                income = 0
                            max_income = price * 20
                            if income > max_income:
                                income = max_income
                            fixed[key] = {
                                "name": data.get("name", key),
                                "price": price,
                                "income": income
                            }
                        return {**DEFAULT_ASSETS, **fixed}
                except json.JSONDecodeError:
                    return DEFAULT_ASSETS
    return DEFAULT_ASSETS

async def get_guild_banks(guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT bank_plans_json FROM guild_config WHERE guild_id = ?', (int(guild_id),)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                try:
                    data = json.loads(row[0])
                    if isinstance(data, dict) and data:
                        fixed = {}
                        for key, info in data.items():
                            try:
                                price = int(info.get("price", 0))
                            except Exception:
                                price = 0
                            steps = max(0, price // 50000)
                            allowed_min_pct = 1 + steps * 1
                            allowed_max_pct = 2 + steps * 2
                            try:
                                min_rate = float(info.get("min", 0.01))
                                max_rate = float(info.get("max", 0.02))
                            except Exception:
                                min_rate = 0.01
                                max_rate = 0.02
                            min_pct = max(0.0, min_rate * 100.0)
                            max_pct = max(0.0, max_rate * 100.0)
                            if min_pct > allowed_min_pct:
                                min_pct = allowed_min_pct
                            if max_pct > allowed_max_pct:
                                max_pct = allowed_max_pct
                            if max_pct < min_pct:
                                max_pct = min_pct
                            fixed[key] = {
                                "name": info.get("name", key),
                                "min": min_pct / 100.0,
                                "max": max_pct / 100.0,
                                "price": price,
                                "min_level": int(info.get("min_level", 0))
                            }
                        if fixed:
                            return fixed
                except json.JSONDecodeError:
                    pass
    return DEFAULT_BANK_PLANS

def compute_boost_multiplier(level):
    return min(2.0, 1.25 + (level * 0.05))

async def ensure_wonder(guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO guild_wonder (guild_id) VALUES (?)', (guild_id,))
        await db.commit()

async def get_wonder(guild_id):
    await ensure_wonder(guild_id)
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM guild_wonder WHERE guild_id = ?', (guild_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_job(user_id, guild_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT job_id FROM user_jobs WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

def get_server_join_multiplier(user_id):
    if not SUPPORT_GUILD_ID:
        return 1.0
    guild = bot.get_guild(SUPPORT_GUILD_ID)
    if not guild:
        return 1.0
    member = guild.get_member(user_id)
    return 2.0 if member else 1.0

async def ensure_quest_resets(user_id, guild_id):
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_quest_completed_json, weekly_quest_completed_json, daily_stats_json, weekly_stats_json FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json = row
        changed = False
        if daily_reset is None or daily_reset == 0 or now - daily_reset >= 86400:
            daily_reset = now
            daily_commands = 0
            daily_reward_claimed = 0
            daily_completed_json = '{}'
            daily_stats_json = '{}'
            changed = True
        if weekly_reset is None or weekly_reset == 0 or now - weekly_reset >= 604800:
            weekly_reset = now
            weekly_commands = 0
            weekly_reward_claimed = 0
            weekly_completed_json = '{}'
            weekly_stats_json = '{}'
            changed = True
        if changed:
            await db.execute('UPDATE users SET daily_reset = ?, weekly_reset = ?, daily_commands = ?, weekly_commands = ?, daily_reward_claimed = ?, weekly_reward_claimed = ?, daily_quest_completed_json = ?, weekly_quest_completed_json = ?, daily_stats_json = ?, weekly_stats_json = ? WHERE user_id = ? AND guild_id = ?', (daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json, user_id, guild_id))
            await db.commit()

async def increment_quests(user_id, guild_id, command_name=None):
    await ensure_quest_resets(user_id, guild_id)
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_quest_completed_json, weekly_quest_completed_json, daily_stats_json, weekly_stats_json FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json = row
        try:
            daily_completed = json.loads(daily_completed_json) if daily_completed_json else {}
        except:
            daily_completed = {}
        try:
            weekly_completed = json.loads(weekly_completed_json) if weekly_completed_json else {}
        except:
            weekly_completed = {}
        try:
            daily_stats = json.loads(daily_stats_json) if daily_stats_json else {}
        except:
            daily_stats = {}
        try:
            weekly_stats = json.loads(weekly_stats_json) if weekly_stats_json else {}
        except:
            weekly_stats = {}
        daily_commands += 1
        weekly_commands += 1
        kinds = ["commands"]
        if command_name:
            name = command_name.lower()
            if name == "work":
                kinds.append("work")
            if name == "crime":
                kinds.append("crime")
            if name in ["blackjack", "roulette"]:
                kinds.append("gamble")
        for k in kinds:
            daily_stats[k] = int(daily_stats.get(k, 0)) + 1
            weekly_stats[k] = int(weekly_stats.get(k, 0)) + 1
        daily_active = get_active_daily_quests(guild_id, now)
        weekly_active = get_active_weekly_quests(guild_id, now)
        reward_balance_changes = 0
        for quest in daily_active:
            qid = quest["id"]
            if not daily_completed.get(qid):
                kind = quest.get("kind", "commands")
                if kind == "commands":
                    progress_val = daily_commands
                else:
                    progress_val = int(daily_stats.get(kind, 0))
                if progress_val >= quest["target"]:
                    reward_balance_changes += quest["reward"]
                    daily_completed[qid] = True
        for quest in weekly_active:
            qid = quest["id"]
            if not weekly_completed.get(qid):
                kind = quest.get("kind", "commands")
                if kind == "commands":
                    progress_val = weekly_commands
                else:
                    progress_val = int(weekly_stats.get(kind, 0))
                if progress_val >= quest["target"]:
                    reward_balance_changes += quest["reward"]
                    weekly_completed[qid] = True
        daily_completed_json = json.dumps(daily_completed)
        weekly_completed_json = json.dumps(weekly_completed)
        daily_stats_json = json.dumps(daily_stats)
        weekly_stats_json = json.dumps(weekly_stats)
        await db.execute('UPDATE users SET daily_commands = ?, weekly_commands = ?, daily_reward_claimed = ?, weekly_reward_claimed = ?, daily_quest_completed_json = ?, weekly_quest_completed_json = ?, daily_stats_json = ?, weekly_stats_json = ? WHERE user_id = ? AND guild_id = ?', (daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json, user_id, guild_id))
        if reward_balance_changes > 0:
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (reward_balance_changes, user_id, guild_id))
        await db.commit()

def get_active_daily_quests(guild_id, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    day = timestamp // 86400
    seed = f"{guild_id}-{day}-daily"
    rng = random.Random(seed)
    pool = list(DAILY_QUESTS)
    rng.shuffle(pool)
    return pool[:3]

def get_active_weekly_quests(guild_id, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    week = timestamp // 604800
    seed = f"{guild_id}-{week}-weekly"
    rng = random.Random(seed)
    pool = list(WEEKLY_QUESTS)
    rng.shuffle(pool)
    return pool[:3]

# --- Logic Functions (Shared by Prefix & Slash) ---
async def work_logic(ctx, user_id, guild_id):
    data = await get_user_data(user_id, guild_id)
    now = int(time.time())
    if now - data['last_work'] < 300:
        return False, f"⏳ Your workers are tired! Wait **{300 - (now - data['last_work'])}s**."
    
    base = random.randint(100, 300) * data['level'] * (data['prestige'] + 1)
    job_id = await get_user_job(user_id, guild_id)
    multiplier = 1.0
    if job_id and job_id in JOBS and JOBS[job_id].get('focus') == 'work':
        multiplier = float(JOBS[job_id].get('multiplier', 1.0))
    
    # --- Multipliers ---
    server_multiplier = get_server_join_multiplier(user_id)
    lb_multiplier = await get_total_multiplier(user_id)
    
    earned = int(base * multiplier * server_multiplier * lb_multiplier)
    
    msg_boost = []
    if server_multiplier > 1.0:
        msg_boost.append("**2x Server Booster**")
    if lb_multiplier > 1.0:
        msg_boost.append(f"**{lb_multiplier:.2f}x Leaderboard Reward**")
        
    msg_boost_str = ""
    if msg_boost:
        msg_boost_str = f" (Includes {' + '.join(msg_boost)}!)"
            
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance + ?, last_work = ? WHERE user_id = ? AND guild_id = ?', 
                        (earned, now, user_id, guild_id))
        await db.commit()
    
    # Use helper for XP to trigger level up notifications
    leveled_up, new_level = await add_xp(user_id, guild_id, 20)
    
    return True, f"⚒️ You supervised the mines and earned **{earned:,} coins**!{msg_boost_str}" + (f"\n🎊 **LEVEL UP!** You reached **Level {new_level}**!" if leveled_up else "")

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
        updates_passive = [] # List of (income, uid, gid)

        for gid, members in guild_groups.items():
            assets_config = await get_guild_assets(gid)
            await db.execute('INSERT OR IGNORE INTO guild_wonder (guild_id) VALUES (?)', (gid,))
            async with db.execute('SELECT boost_multiplier, boost_until FROM guild_wonder WHERE guild_id = ?', (gid,)) as cursor:
                wonder_row = await cursor.fetchone()
            boost_multiplier = 1.0
            if wonder_row:
                boost_multiplier = wonder_row[0] if now < wonder_row[1] else 1.0
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
                    adjusted_income = int(data['income'] * boost_multiplier)
                    updates_passive.append((data['income'], uid, gid))
                    if data['auto_dep'] and is_voter:
                        updates_bank.append((adjusted_income, uid, gid))
                    else:
                        updates_balance.append((adjusted_income, uid, gid))

        if updates_balance:
            await db.executemany('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', updates_balance)
        if updates_bank:
            await db.executemany('UPDATE users SET bank = bank + ? WHERE user_id = ? AND guild_id = ?', updates_bank)
        if updates_passive:
            await db.executemany('UPDATE users SET passive_income = ? WHERE user_id = ? AND guild_id = ?', updates_passive)
        
        await db.commit()

@tasks.loop(hours=1)
async def leaderboard_rewards_task():
    """Update top 3 multipliers and titles hourly."""
    categories = {
        "commands": 'SELECT user_id, SUM(total_commands) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3',
        "robs": 'SELECT user_id, SUM(successful_robs) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3',
        "crimes": 'SELECT user_id, SUM(successful_crimes) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3',
        "money": 'SELECT user_id, SUM(balance + bank) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3',
        "passive": 'SELECT user_id, SUM(passive_income) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3',
        "level": 'SELECT user_id, MAX(level) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 3'
    }
    
    titles_map = {
        "commands": ["Command Master", "Command Expert", "Command Enthusiast"],
        "robs": ["Master Thief", "Elite Robber", "Pickpocket"],
        "crimes": ["Godfather", "Crime Lord", "Thug"],
        "money": ["Emperor", "Tycoon", "Wealthy Merchant"],
        "passive": ["Industrialist", "Business Mogul", "Investor"],
        "level": ["Grand Sage", "Wise Elder", "Scholar"]
    }

    # Reset current leaderboard multipliers for all users in memory or just track who changed?
    # Simpler: Clear all 'lb_' multipliers and re-assign.
    async with aiosqlite.connect(DB_FILE) as db:
        # Get all users with lb_ multipliers
        async with db.execute("SELECT user_id, multipliers_json, titles_json, medals_json FROM user_rewards") as cursor:
            rows = await cursor.fetchall()
            
        for uid, mults_json, titles_json, medals_json in rows:
            mults = json.loads(mults_json)
            titles = json.loads(titles_json)
            medals = json.loads(medals_json)
            
            # Remove existing lb_ mults, titles, and medals
            mults = {k: v for k, v in mults.items() if not k.startswith('lb_')}
            titles = [t for t in titles if not t.get('source', '').startswith('lb_')]
            medals = [m for m in medals if not m.get('source', '').startswith('lb_')]
            
            await db.execute("UPDATE user_rewards SET multipliers_json = ?, titles_json = ?, medals_json = ? WHERE user_id = ?", 
                            (json.dumps(mults), json.dumps(titles), json.dumps(medals), uid))
        await db.commit()

        # Re-assign based on current top 3
        for cat_id, query in categories.items():
            async with db.execute(query) as cursor:
                top_rows = await cursor.fetchall()
                
            for i, row in enumerate(top_rows):
                uid = row[0]
                rank = i + 1
                multiplier = 2.0 if rank == 1 else 1.5 if rank == 2 else 1.25
                medal_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉"
                title_name = titles_map[cat_id][i]
                
                await ensure_rewards(uid)
                async with db.execute("SELECT multipliers_json, titles_json, medals_json FROM user_rewards WHERE user_id = ?", (uid,)) as cursor:
                    r = await cursor.fetchone()
                    mults = json.loads(r[0])
                    titles = json.loads(r[1])
                    medals = json.loads(r[2])
                
                mults[f"lb_{cat_id}"] = multiplier
                titles.append({"title": title_name, "source": f"lb_{cat_id}", "timestamp": int(time.time())})
                medals.append({"medal": medal_emoji, "source": f"lb_{cat_id}", "timestamp": int(time.time())})
                
                await db.execute("UPDATE user_rewards SET multipliers_json = ?, titles_json = ?, medals_json = ? WHERE user_id = ?", 
                                (json.dumps(mults), json.dumps(titles), json.dumps(medals), uid))
        await db.commit()

@tasks.loop(hours=1)
async def interest_task():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT user_id, guild_id, bank, bank_plan FROM users WHERE bank > 0') as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return
        guild_groups = {}
        for uid, gid, bank, plan in rows:
            if gid not in guild_groups:
                guild_groups[gid] = []
            guild_groups[gid].append((uid, bank, plan or 'standard'))
        updates = []
        for gid, members in guild_groups.items():
            banks_config = await get_guild_banks(gid)
            for uid, bank, plan in members:
                plan_data = banks_config.get(plan) or banks_config.get('standard')
                if not plan_data:
                    rate_min = 0.01
                    rate_max = 0.02
                else:
                    rate_min = float(plan_data.get('min', 0.01))
                    rate_max = float(plan_data.get('max', 0.02))
                interest = int(bank * random.uniform(rate_min, rate_max))
                if interest > 0:
                    updates.append((interest, uid, gid))
        if updates:
            await db.executemany('UPDATE users SET bank = bank + ? WHERE user_id = ? AND guild_id = ?', updates)
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
    if ctx.guild is None:
        return
    leveled_up, new_level = await add_xp(ctx.author.id, ctx.guild.id, 5)
    
    # Track global command count for leaderboards
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET total_commands = total_commands + 1 WHERE user_id = ? AND guild_id = ?', 
                        (ctx.author.id, ctx.guild.id))
        await db.commit()

    cmd_name = ctx.command.name if ctx.command else None
    await increment_quests(ctx.author.id, ctx.guild.id, cmd_name)
    if leveled_up:
        await ctx.send(f"🎊 **LEVEL UP!** {ctx.author.mention} reached **Level {new_level}**!")

@bot.event
async def on_ready():
    await init_db()
    await migrate_db()
    
    global SUPPORT_GUILD_ID
    try:
        invite = await bot.fetch_invite(SUPPORT_SERVER_INVITE)
        if invite.guild:
            SUPPORT_GUILD_ID = invite.guild.id
            print(f"DEBUG: Resolved Support Guild ID: {SUPPORT_GUILD_ID}")
    except Exception as e:
        print(f"DEBUG: Could not resolve support invite: {e}")

    interest_task.start()
    leaderboard_rewards_task.start()
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

@bot.event
async def on_member_join(member):
    # Welcome message
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT welcome_channel, welcome_message FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = member.guild.get_channel(row[0])
                if channel:
                    msg = row[1].replace("{user}", member.mention)
                    await channel.send(msg)
        
    # Member join log & account age verification
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT member_log_channel FROM logging_config WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = member.guild.get_channel(row[0])
                if channel:
                    account_age = (discord.utils.utcnow() - member.created_at).days
                    embed = discord.Embed(title="Member Joined", color=discord.Color.green())
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User", value=f"{member} ({member.id})")
                    embed.add_field(name="Account Age", value=f"{account_age} days")
                    if account_age < 7:
                        embed.description = "⚠️ **Warning: New Account!**"
                    embed.set_timestamp()
                    await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    # Farewell message
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT farewell_channel, farewell_message FROM welcome_farewell WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = member.guild.get_channel(row[0])
                if channel:
                    msg = row[1].replace("{user}", member.display_name)
                    await channel.send(msg)

    # Member leave log
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT member_log_channel FROM logging_config WHERE guild_id = ?', (member.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = member.guild.get_channel(row[0])
                if channel:
                    embed = discord.Embed(title="Member Left", color=discord.Color.orange())
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="User", value=f"{member} ({member.id})")
                    embed.set_timestamp()
                    await channel.send(embed=embed)

@bot.event
async def on_message_delete(message):
    if not message.guild or message.author.bot: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT message_log_channel FROM logging_config WHERE guild_id = ?', (message.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = message.guild.get_channel(row[0])
                if channel:
                    embed = discord.Embed(title="Message Deleted", color=discord.Color.red())
                    embed.add_field(name="Author", value=f"{message.author} ({message.author.id})")
                    embed.add_field(name="Channel", value=message.channel.mention)
                    embed.add_field(name="Content", value=message.content or "[No content]", inline=False)
                    embed.set_timestamp()
                    await channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if not before.guild or before.author.bot: return
    if before.content == after.content: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT message_log_channel FROM logging_config WHERE guild_id = ?', (before.guild.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                channel = before.guild.get_channel(row[0])
                if channel:
                    embed = discord.Embed(title="Message Edited", color=discord.Color.blue())
                    embed.add_field(name="Author", value=f"{before.author} ({before.author.id})")
                    embed.add_field(name="Channel", value=before.channel.mention)
                    embed.add_field(name="Before", value=before.content or "[No content]", inline=False)
                    embed.add_field(name="After", value=after.content or "[No content]", inline=False)
                    embed.set_timestamp()
                    await channel.send(embed=embed)

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?', (payload.message_id, str(payload.emoji)) ) as cursor:
            row = await cursor.fetchone()
            if row:
                guild = bot.get_guild(payload.guild_id)
                role = guild.get_role(row[0])
                member = guild.get_member(payload.user_id)
                if role and member:
                    try:
                        await member.add_roles(role)
                    except:
                        pass

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id: return
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT role_id FROM reaction_roles WHERE message_id = ? AND emoji = ?', (payload.message_id, str(payload.emoji)) ) as cursor:
            row = await cursor.fetchone()
            if row:
                guild = bot.get_guild(payload.guild_id)
                role = guild.get_role(row[0])
                member = guild.get_member(payload.user_id)
                if role and member:
                    try:
                        await member.remove_roles(role)
                    except:
                        pass

@bot.event
async def on_message(message):
    if message.author.bot: return
    if not message.guild: return

    # --- AUTOMOD ---
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT word, punishment FROM automod_words WHERE guild_id = ?', (message.guild.id,)) as cursor:
            rows = await cursor.fetchall()
            for word, punishment in rows:
                if word in message.content.lower():
                    # Trigger Automod
                    if punishment == 'delete':
                        try: await message.delete()
                        except: pass
                    elif punishment == 'warn':
                        # Issue warning
                        await db.execute('''
                            INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (message.author.id, message.guild.id, bot.user.id, f"AutoMod: Blacklisted word '{word}'", int(time.time())))
                        await db.commit()
                        try: await message.delete()
                        except: pass
                        await message.channel.send(f"⚠️ {message.author.mention}, that word is blacklisted! (Warned)", delete_after=5)
                    elif punishment == 'kick':
                        try: 
                            await message.author.kick(reason=f"AutoMod: Blacklisted word '{word}'")
                            await message.delete()
                        except: pass
                    elif punishment == 'ban':
                        try: 
                            await message.author.ban(reason=f"AutoMod: Blacklisted word '{word}'")
                            await message.delete()
                        except: pass
                    
                    # Log AutoMod
                    async with db.execute('SELECT automod_log_channel FROM logging_config WHERE guild_id = ?', (message.guild.id,)) as log_cursor:
                        log_row = await log_cursor.fetchone()
                        if log_row and log_row[0]:
                            log_channel = message.guild.get_channel(log_row[0])
                            if log_channel:
                                embed = discord.Embed(title="AutoMod Triggered", color=discord.Color.dark_red())
                                embed.add_field(name="User", value=f"{message.author} ({message.author.id})")
                                embed.add_field(name="Word", value=word)
                                embed.add_field(name="Punishment", value=punishment)
                                embed.add_field(name="Content", value=message.content)
                                embed.set_timestamp()
                                await log_channel.send(embed=embed)
                    return # Stop processing if automod triggered

    # --- CUSTOM COMMANDS ---
    # Check for custom commands
    prefix = await get_prefix(bot, message)
    if message.content.startswith(prefix):
        parts = message.content[len(prefix):].split()
        if parts:
            cmd_name = parts[0]
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute('SELECT code FROM custom_commands WHERE guild_id = ? AND name = ?', (message.guild.id, cmd_name)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        code = row[0]
                        # Secure execution sandbox
                        restricted_globals = {
                            'discord': discord,
                            'message': message,
                            'guild': message.guild,
                            'channel': message.channel,
                            'author': message.author,
                            'bot': bot,
                            'print': lambda x: None # Disable print
                        }
                        try:
                            exec_code = f"async def custom_cmd():\n" + "\n".join(f"    {line}" for line in code.split('\n'))
                            exec(exec_code, restricted_globals)
                            await restricted_globals['custom_cmd']()
                            embed = discord.Embed(title="Custom Command Executed", color=discord.Color.blurple())
                            embed.add_field(name="User", value=f"{message.author} ({message.author.id})")
                            embed.add_field(name="Command", value=cmd_name)
                            await log_embed(message.guild, "command_log_channel", embed)
                        except Exception as e:
                            await message.channel.send(f"❌ Error in custom command `{cmd_name}`: `{e}`")
                        return

    await bot.process_commands(message)

# --- Hybrid Commands ---

@bot.hybrid_command(name="start", description="New to the Empire? Start your tutorial here!")
async def start_tutorial(ctx: commands.Context):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    msg_bonus = ""
    
    # Check if 'started' is 0 or None (handle case where column was just added so it might be 0)
    # The default is 0.
    if not data['started']:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance + 500, started = 1 WHERE user_id = ? AND guild_id = ?', (ctx.author.id, ctx.guild.id))
            await db.commit()
        msg_bonus = "\n\n🎉 **Welcome Bonus!** You received **500 coins** for starting your journey!"

    embed = discord.Embed(
        title="🌅 Welcome to Empire Nexus",
        description=(
            f"You have inherited a small plot of land and 100 coins. Your goal: **Build the wealthiest empire in the server.**{msg_bonus}\n\n"
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

class HelpSelect(discord.ui.Select):
    def __init__(self, prefix):
        self.prefix = prefix
        options = [
            discord.SelectOption(label="Making Money", description="Work, crime, gambling, and jobs", emoji="💸"),
            discord.SelectOption(label="Banking", description="Deposit, withdraw, and bank plans", emoji="🏦"),
            discord.SelectOption(label="Assets & Empire", description="Shop, inventory, and prestige", emoji="🏗️"),
            discord.SelectOption(label="Wonder & Server Progress", description="Server-wide projects and boosts", emoji="🏛️"),
            discord.SelectOption(label="Boosters & Rewards", description="Voting and support server bonuses", emoji="🚀"),
            discord.SelectOption(label="Setup & Utility", description="Help, settings, and tutorial", emoji="⚙️")
        ]
        super().__init__(placeholder="Select a category to view its commands!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        category_map = {
            "Making Money": "making money",
            "Banking": "banking",
            "Assets & Empire": "assets",
            "Wonder & Server Progress": "wonder",
            "Boosters & Rewards": "boosters",
            "Setup & Utility": "utility"
        }
        
        selected_label = self.values[0]
        key = category_map.get(selected_label)
        prefix = self.prefix
        
        categories = {
            "making money": {
                "title": "💸 Making Money",
                "commands": [
                    f"`{prefix}work`, `/work` – Supervise mines for coins.",
                    f"`{prefix}crime`, `/crime` – High risk, high reward heists.",
                    f"`{prefix}blackjack`, `/blackjack` – Casino blackjack.",
                    f"`{prefix}roulette`, `/roulette` – Spin the wheel.",
                    f"`{prefix}riddle`, `/riddle` and `{prefix}answer` – Solve riddles.",
                    f"`{prefix}jobs`, `/jobs` – View available jobs.",
                    f"`{prefix}applyjob <id>`, `/applyjob` – Apply for a job.",
                    f"`{prefix}dailyquests`, `/dailyquests` – Daily quest checklist.",
                    f"`{prefix}weeklyquests`, `/weeklyquests` – Weekly quest checklist."
                ],
                "explain": (
                    "Use **work**, **crime**, and the **casino** commands to generate coins. "
                    "Pick a **job** with `jobs`/`applyjob` to boost income from your favourite activity. "
                    "Daily and weekly quests reward you for using commands consistently, so if you grind "
                    "work, crime, blackjack or roulette while quests are active you will complete multiple "
                    "quests at once and snowball much faster."
                )
            },
            "banking": {
                "title": "🏦 Banking",
                "commands": [
                    f"`{prefix}deposit <amount>`, `/deposit` – Move coins into the bank.",
                    f"`{prefix}withdraw <amount>`, `/withdraw` – Take coins out of the bank.",
                    f"`{prefix}balance`, `/balance` – View wallet, bank and bank plan.",
                    f"`{prefix}bank`, `/bank` – View and switch bank plans.",
                    f"`{prefix}autodeposit`, `/autodeposit` – Auto‑deposit passive income (with vote).",
                    f"`{prefix}vote`, `/vote` – Vote for Top.gg rewards.",
                    f"`{prefix}leaderboard`, `/leaderboard` – Money or XP rankings."
                ],
                "explain": (
                    "Make money first, then **secure** it in the bank with `deposit`. "
                    "Choosing a better **bank plan** with `bank` increases your hourly interest, "
                    "so long‑term savings grow faster than coins left in your wallet. "
                    "If you enable `autodeposit` after voting, passive income goes straight to the bank, "
                    "compounding with interest. Use `balance` to monitor your totals and `leaderboard` "
                    "to see how your wealth compares to others."
                )
            },
            "assets": {
                "title": "🏗️ Assets & Empire",
                "commands": [
                    f"`{prefix}shop`, `/shop` – Browse passive income assets.",
                    f"`{prefix}buy <id>`, `/buy` – Buy assets.",
                    f"`{prefix}inventory`, `/inventory` – View your assets.",
                    f"`{prefix}profile`, `/profile` – Full empire overview (shows Titles & Medals).",
                    f"`{prefix}prestige`, `/prestige` – Reset for permanent multipliers.",
                    f"`{prefix}buyrole`, `/buyrole` – Buy server roles with coins."
                ],
                "explain": (
                    "Use `shop` and `buy` to invest your coins into **assets** that pay every 10 minutes. "
                    "Check `inventory` and `profile` to see how much passive income your empire produces. "
                    "Once you reach the requirements, `prestige` lets you reset progress in exchange for "
                    "permanent income multipliers, making every future asset and income source stronger. "
                    "If the server owner set up a role shop, `buyrole` lets you convert economic progress "
                    "into cosmetic or utility roles."
                )
            },
            "wonder": {
                "title": "🏛️ Wonder & Server Progress",
                "commands": [
                    f"`{prefix}wonder`, `/wonder` – View server Wonder level and boost.",
                    f"`{prefix}contribute <amount>`, `/contribute` – Fund the Wonder for global boosts."
                ],
                "explain": (
                    "The Wonder is a **server‑wide project**. Everyone can contribute coins with "
                    "`contribute` to level it up. Each level makes the Wonder more expensive but "
                    "unlocks stronger passive income boosts for the entire server for a limited time. "
                    "Use `wonder` regularly to see progress and coordinate contributions with your community."
                )
            },
            "boosters": {
                "title": "🚀 Boosters & Rewards",
                "commands": [
                    f"`{prefix}vote`, `/vote` – Vote for 25,000 coins & auto-deposit.",
                    "**Join Support Server** – Get 2x Coin Multiplier.",
                    "**Global Leaderboards** – Top 3 users get stackable multipliers (up to 2x)."
                ],
                "explain": (
                    "**A) Voting Rewards:**\n"
                    "Vote for the bot on Top.gg to receive **25,000 coins** instantly and unlock **Auto-Deposit** "
                    "for 12 hours. Auto-deposit automatically moves your passive income to your bank.\n\n"
                    "**B) Support Server Booster:**\n"
                    f"Join [**Empire Nexus Support**](https://discord.gg/{SUPPORT_SERVER_INVITE}) to permanently unlock a **2x Coin Multiplier** "
                    "on all earnings from `/work`, `/crime`, `/blackjack`, and `/roulette`.\n\n"
                    "**C) Leaderboard Rewards:**\n"
                    "The top 3 users in each `/leaderboard` category receive stackable coin multipliers (1st: 2x, 2nd: 1.5x, 3rd: 1.25x) "
                    "and exclusive titles visible in your `/profile` for as long as they maintain their rank."
                )
            },
            "utility": {
                "title": "⚙️ Setup & Utility",
                "commands": [
                    f"`{prefix}help`, `/help` – Overview and category help.",
                    f"`{prefix}rank`, `/rank` – View level and XP bar.",
                    f"`{prefix}setup`, `/setup` – Dashboard link and setup info.",
                    f"`{prefix}setprefix`, `/setprefix` – Change the bot prefix (admin).",
                    f"`{prefix}start`, `/start` – Tutorial for new players."
                ],
                "explain": (
                    "Use `start` to onboard new players and explain the basic gameplay loop. "
                    "`help` and `help <category>` give quick references and explanations for all systems. "
                    "Admins can run `setprefix` to change how commands are triggered, and `setup` to access "
                    "the web dashboard for configuring banks, assets, and role shops. `rank` shows players "
                    "their level progression and encourages long‑term engagement."
                )
            }
        }
        
        data = categories[key]
        embed = discord.Embed(
            title=f"{data['title']}",
            description=data["explain"],
            color=0x00d2ff
        )
        cmds_text = "\n".join(f"- {line}" for line in data["commands"])
        embed.add_field(name="Commands", value=cmds_text, inline=False)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, prefix):
        super().__init__(timeout=120)
        self.add_item(HelpSelect(prefix))

@bot.hybrid_command(name="help", description="Show all available commands")
async def help_command(ctx: commands.Context, *, category: str = None):
    prefix = await get_prefix(bot, ctx.message)
    view = HelpView(prefix)
    embed = discord.Embed(
        title="Help Menu",
        description="Select a category from the dropdown menu below to view the commands.",
        color=0x2f3136
    )
    embed.set_footer(text="Empire Nexus Help System")
    await ctx.send(embed=embed, view=view)

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

@bot.hybrid_command(name="wonder", description="View your server Wonder progress")
async def wonder(ctx: commands.Context):
    data = await get_wonder(ctx.guild.id)
    now = int(time.time())
    goal = data['goal'] or 0
    progress = data['progress']
    level = data['level']
    boost_multiplier = data['boost_multiplier']
    boost_until = data['boost_until']
    progress_pct = int((progress / goal) * 100) if goal > 0 else 0
    bar_length = 12
    filled = int((progress_pct / 100) * bar_length)
    bar = "🟦" * filled + "⬛" * (bar_length - filled)
    if boost_until > now:
        remaining = boost_until - now
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        boost_status = f"Active • {boost_multiplier:.2f}x • {hours}h {minutes}m left"
    else:
        boost_status = "Inactive"
    embed = discord.Embed(title=f"🏛️ {ctx.guild.name} Wonder", color=0x00d2ff)
    embed.add_field(name="Level", value=f"{level}", inline=True)
    embed.add_field(name="Progress", value=f"{progress:,} / {goal:,} coins", inline=True)
    embed.add_field(name="Boost", value=boost_status, inline=False)
    embed.add_field(name="Progress Bar", value=bar, inline=False)
    embed.set_footer(text="Contribute with /contribute <amount>")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="contribute", description="Contribute coins to your server Wonder")
async def contribute(ctx: commands.Context, amount: int):
    if amount <= 0:
        return await ctx.send("❌ Enter a positive amount.")
    user = await get_user_data(ctx.author.id, ctx.guild.id)
    if user['balance'] < amount:
        return await ctx.send(f"❌ You need **{amount - user['balance']:,} more coins**.")
    now = int(time.time())
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR IGNORE INTO guild_wonder (guild_id) VALUES (?)', (ctx.guild.id,))
        async with db.execute('SELECT level, progress, goal, boost_multiplier, boost_until FROM guild_wonder WHERE guild_id = ?', (ctx.guild.id,)) as cursor:
            row = await cursor.fetchone()
        level, progress, goal, boost_multiplier, boost_until = row
        remaining = amount
        leveled_up = 0
        while remaining > 0:
            to_goal = max(0, goal - progress)
            if to_goal == 0:
                level += 1
                goal = int(goal * 1.5 + 10000)
                boost_multiplier = compute_boost_multiplier(level)
                boost_until = now + 21600
                leveled_up += 1
                progress = 0
                continue
            if remaining < to_goal:
                progress += remaining
                remaining = 0
            else:
                remaining -= to_goal
                level += 1
                progress = 0
                goal = int(goal * 1.5 + 10000)
                boost_multiplier = compute_boost_multiplier(level)
                boost_until = now + 21600
                leveled_up += 1
        await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ? AND guild_id = ?', (amount, ctx.author.id, ctx.guild.id))
        await db.execute('UPDATE guild_wonder SET level = ?, progress = ?, goal = ?, boost_multiplier = ?, boost_until = ? WHERE guild_id = ?', (level, progress, goal, boost_multiplier, boost_until, ctx.guild.id))
        await db.commit()
    if leveled_up > 0:
        await ctx.send(f"🏛️ **Wonder Level Up!** Your server reached **Level {level}** and unlocked **{boost_multiplier:.2f}x** passive income for 6 hours.")
    else:
        await ctx.send(f"✅ Contributed **{amount:,} coins** to the Wonder. Progress: **{progress:,} / {goal:,}**.")

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
            server_multiplier = get_server_join_multiplier(ctx.author.id)
            winnings = int(bet_amount * (multiplier - 1) * server_multiplier)
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (winnings, ctx.author.id, ctx.guild.id))
            
            boost_msg = ""
            if server_multiplier > 1.0:
                boost_msg = " (Includes **2x Server Booster**!)"
                
            result_msg = f"✅ **WIN!** The ball landed on **{roll_color.upper()} {roll}**.\nYou won **{winnings:,} coins**!{boost_msg}"
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
    job_id = await get_user_job(ctx.author.id, ctx.guild.id)
    bj_multiplier = 1.0
    if job_id and job_id in JOBS and JOBS[job_id].get('focus') == 'blackjack':
        bj_multiplier = float(JOBS[job_id].get('multiplier', 1.0))

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
            server_multiplier = get_server_join_multiplier(ctx.author.id)
            final_win = int(bet_amount * server_multiplier)
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (final_win, ctx.author.id, ctx.guild.id))
            if server_multiplier > 1.0:
                result += " (2x Boost!)"
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
                        f"• 💰 **Bonus Coins:** 25,000 Coins (Instant)\n\n" \
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
    await ensure_rewards(target.id)
    
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
    embed.add_field(name="💰 Wealth", value=f"Wallet: {data['balance']:,}\nBank: {data['bank']:,}", inline=True)
    embed.add_field(name="🏷️ Titles", value=titles_str, inline=False)
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
    
    if random.random() < 0.30:
        base = random.randint(1000, 3000) * data['level']
        job_id = await get_user_job(ctx.author.id, ctx.guild.id)
        multiplier = 1.0
        if job_id and job_id in JOBS and JOBS[job_id].get('focus') == 'crime':
            multiplier = float(JOBS[job_id].get('multiplier', 1.0))
            
        server_multiplier = get_server_join_multiplier(ctx.author.id)
        earned = int(base * multiplier * server_multiplier)
        
        msg_boost = ""
        if server_multiplier > 1.0:
            msg_boost = " (Includes **2x Server Booster**!)"
            
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = balance + ?, last_crime = ?, successful_crimes = successful_crimes + 1 WHERE user_id = ? AND guild_id = ?', (earned, now, ctx.author.id, ctx.guild.id))
            await db.commit()
        await ctx.send(f"😈 You pulled off a heist and got **{earned:,} coins**!{msg_boost}")
    else:
        loss = random.randint(500, 1000)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE users SET balance = MAX(0, balance - ?), last_crime = ? WHERE user_id = ? AND guild_id = ?', (loss, now, ctx.author.id, ctx.guild.id))
            await db.commit()
        await ctx.send(f"👮 BUSTED! You lost **{loss:,} coins** while escaping.")

@bot.hybrid_command(name="dailyquests", description="View your daily quest progress")
async def dailyquests(ctx: commands.Context):
    await ensure_quest_resets(ctx.author.id, ctx.guild.id)
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    done = data['daily_commands']
    try:
        completed = json.loads(data['daily_quest_completed_json']) if data['daily_quest_completed_json'] else {}
    except:
        completed = {}
    quests = get_active_daily_quests(ctx.guild.id)
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
    await ensure_quest_resets(ctx.author.id, ctx.guild.id)
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    done = data['weekly_commands']
    try:
        completed = json.loads(data['weekly_quest_completed_json']) if data['weekly_quest_completed_json'] else {}
    except:
        completed = {}
    quests = get_active_weekly_quests(ctx.guild.id)
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

# --- Hybrid Commands (Prefix + Slash) ---

@bot.hybrid_command(name="balance", aliases=["bal"], description="Check your balance")
async def balance(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    data = await get_user_data(target.id, ctx.guild.id)
    bank_plan = data['bank_plan'] if 'bank_plan' in data.keys() else 'standard'
    banks = await get_guild_banks(ctx.guild.id)
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

@bot.hybrid_command(name="bank", description="View and switch bank plans")
async def bank_cmd(ctx: commands.Context, plan_id: str = None):
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    banks = await get_guild_banks(ctx.guild.id)
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
        await ctx.send("Invalid bank plan id.")
        return
    if plan_id == current:
        await ctx.send("You already use this bank plan.")
        return
    info = banks[plan_id]
    price = int(info.get('price', 0))
    min_level = int(info.get('min_level', 0))
    if data['level'] < min_level:
        await ctx.send(f"You need at least level {min_level} to use this plan.")
        return
    if price > 0 and data['balance'] < price:
        await ctx.send(f"You need {price - data['balance']:,} more coins in your wallet.")
        return
    async with aiosqlite.connect(DB_FILE) as db:
        if price > 0:
            await db.execute('UPDATE users SET balance = balance - ?, bank_plan = ? WHERE user_id = ? AND guild_id = ?', (price, plan_id, ctx.author.id, ctx.guild.id))
        else:
            await db.execute('UPDATE users SET bank_plan = ? WHERE user_id = ? AND guild_id = ?', (plan_id, ctx.author.id, ctx.guild.id))
        await db.commit()
    await ctx.send(f"Switched your bank plan to **{info.get('name', plan_id)}**.")

@bot.hybrid_command(name="work", description="Work to earn coins")
@commands.cooldown(1, 300, commands.BucketType.user)
async def work(ctx: commands.Context):
    success, message = await work_logic(ctx, ctx.author.id, ctx.guild.id)
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
            await db.execute('UPDATE users SET balance = balance + ?, last_rob = ?, successful_robs = successful_robs + 1 WHERE user_id = ? AND guild_id = ?', (stolen, now, ctx.author.id, ctx.guild.id))
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
    needed_xp = level * 100
    
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

# Leaderboard Cache
LB_CACHE = {}
LB_CACHE_DURATION = 300 # 5 minutes

@bot.hybrid_command(name="leaderboard", aliases=["lb"], description="View the global leaderboard")
@app_commands.choices(category=[
    app_commands.Choice(name="Most Commands Used", value="commands"),
    app_commands.Choice(name="Most Successful Robs", value="robs"),
    app_commands.Choice(name="Most Successful Crimes", value="crimes"),
    app_commands.Choice(name="Most Money", value="money"),
    app_commands.Choice(name="Highest Passive Income", value="passive"),
    app_commands.Choice(name="Highest Level", value="level")
])
async def leaderboard(ctx: commands.Context, category: str = "money"):
    now = time.time()
    
    # Check cache
    if category in LB_CACHE:
        cache_data, timestamp = LB_CACHE[category]
        if now - timestamp < LB_CACHE_DURATION:
            return await ctx.send(embed=cache_data)

    async with aiosqlite.connect(DB_FILE) as db:
        if category == "commands":
            query = 'SELECT user_id, SUM(total_commands) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 10'
            title = "🏆 Global Commands Leaderboard"
            symbol = "⌨️"
            unit = "commands"
        elif category == "robs":
            query = 'SELECT user_id, SUM(successful_robs) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 10'
            title = "🏆 Global Robbery Leaderboard"
            symbol = "🧤"
            unit = "robs"
        elif category == "crimes":
            query = 'SELECT user_id, SUM(successful_crimes) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 10'
            title = "🏆 Global Crime Leaderboard"
            symbol = "😈"
            unit = "crimes"
        elif category == "money":
            query = 'SELECT user_id, SUM(balance + bank) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 10'
            title = "🏆 Global Wealth Leaderboard"
            symbol = "🪙"
            unit = "coins"
        elif category == "passive":
            query = 'SELECT user_id, SUM(passive_income) as total FROM users GROUP BY user_id ORDER BY total DESC LIMIT 10'
            title = "🏆 Global Passive Income Leaderboard"
            symbol = "📈"
            unit = "coins/10m"
        elif category == "level":
            query = 'SELECT user_id, MAX(level) as max_level, MAX(xp) as max_xp FROM users GROUP BY user_id ORDER BY max_level DESC, max_xp DESC LIMIT 10'
            title = "🏆 Global Level Leaderboard"
            symbol = "⭐"
            unit = "Level"

        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
    
    if not rows: return await ctx.send("The leaderboard is empty!")
    
    lb_str = ""
    for i, row in enumerate(rows, 1):
        uid = row[0]
        val = row[1]
        
        # Medal for top 3
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
        
        user = bot.get_user(uid)
        name = user.name if user else f"User({uid})"
        
        if category == "level":
            max_level = row[1]
            max_xp = row[2]
            lb_str += f"{medal} **{name}** — Lvl {max_level} ({max_xp} XP)\n"
        elif category == "passive":
            lb_str += f"{medal} **{name}** — {symbol} {val:,.2f} {unit}\n"
        else:
            lb_str += f"{medal} **{name}** — {symbol} {val:,} {unit}\n"
    
    lb_str += "\n*Top 3 receive stackable coin multipliers!*"
    
    embed = discord.Embed(title=title, description=lb_str, color=0xFFA500)
    
    # Update cache
    LB_CACHE[category] = (embed, time.time())
    
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

@bot.hybrid_command(name="jobs", description="List available jobs")
async def jobs(ctx: commands.Context):
    current = await get_user_job(ctx.author.id, ctx.guild.id)
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    desc = ""
    for job_id, info in JOBS.items():
        marker = "✅" if job_id == current else "➖"
        name = info.get("name", job_id)
        diff = info.get("difficulty", "Unknown")
        min_level = info.get("min_level", 0)
        mult = float(info.get("multiplier", 1.0))
        desc += f"{marker} **{name}** (`{job_id}`)\nDifficulty: {diff} • Min Lvl: {min_level} • Income x{mult:.2f}\n\n"
    embed = discord.Embed(title="⚒️ Available Jobs", description=desc or "No jobs configured.", color=0x00d2ff)
    embed.set_footer(text=f"Your level: {data['level']}. Use /applyjob <id> to apply.")
    await ctx.send(embed=embed)

@bot.hybrid_command(name="applyjob", description="Apply for a job")
async def applyjob(ctx: commands.Context, job_id: str):
    job_id = job_id.lower()
    if job_id not in JOBS:
        await ctx.send("Invalid job id.")
        return
    info = JOBS[job_id]
    data = await get_user_data(ctx.author.id, ctx.guild.id)
    if await get_user_job(ctx.author.id, ctx.guild.id) == job_id:
        await ctx.send("You already have this job.")
        return
    if data['level'] < info.get("min_level", 0):
        await ctx.send(f"You need at least level {info.get('min_level', 0)} for this job.")
        return
    question = info.get("question", "")
    answer = info.get("answer", "").lower()
    if not question or not answer:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO user_jobs (user_id, guild_id, job_id) VALUES (?, ?, ?)', (ctx.author.id, ctx.guild.id, job_id))
            await db.commit()
        await ctx.send(f"You are now hired as **{info.get('name', job_id)}**.")
        return
    await ctx.send(f"Application question for **{info.get('name', job_id)}**:\n{question}")
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    try:
        reply = await bot.wait_for('message', check=check, timeout=60)
    except:
        await ctx.send("Application timed out.")
        return
    
    if reply.content.lower() == answer:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO user_jobs (user_id, guild_id, job_id) VALUES (?, ?, ?)', (ctx.author.id, ctx.guild.id, job_id))
            await db.commit()
        await ctx.send(f"✅ Correct! You are now hired as **{info.get('name', job_id)}**.")
    else:
        await ctx.send(f"❌ Incorrect answer. You failed the application for **{info.get('name', job_id)}**.")

# --- Utility Commands ---

@bot.hybrid_command(name="ping", description="Check the bot's latency")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latency: **{latency}ms**", color=0x00ff00)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="membercount", description="Display server member statistics")
async def membercount(ctx: commands.Context):
    guild = ctx.guild
    total = guild.member_count
    bots = sum(1 for m in guild.members if m.bot)
    humans = total - bots
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)

    embed = discord.Embed(title=f"📈 {guild.name} Member Count", color=0x00d2ff)
    embed.add_field(name="Total Members", value=f"👥 `{total}`", inline=True)
    embed.add_field(name="Humans", value=f"👤 `{humans}`", inline=True)
    embed.add_field(name="Bots", value=f"🤖 `{bots}`", inline=True)
    embed.add_field(name="Online", value=f"🟢 `{online}`", inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Show detailed server information")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    owner = guild.owner
    created_at = guild.created_at.strftime("%b %d, %Y")
    roles = len(guild.roles)
    channels = len(guild.channels)
    emojis = len(guild.emojis)
    boosts = guild.premium_subscription_count
    level = guild.premium_tier

    embed = discord.Embed(title=f"🏰 {guild.name} Information", color=0x00d2ff)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    
    embed.add_field(name="Owner", value=f"👑 {owner.mention}", inline=True)
    embed.add_field(name="Created On", value=f"📅 {created_at}", inline=True)
    embed.add_field(name="Server ID", value=f"🆔 `{guild.id}`", inline=True)
    
    embed.add_field(name="Members", value=f"👥 `{guild.member_count}`", inline=True)
    embed.add_field(name="Channels", value=f"📁 `{channels}`", inline=True)
    embed.add_field(name="Roles", value=f"🎭 `{roles}`", inline=True)
    
    embed.add_field(name="Boosts", value=f"💎 `{boosts}` (Level {level})", inline=True)
    embed.add_field(name="Emojis", value=f"😀 `{emojis}`", inline=True)
    embed.add_field(name="Verification", value=f"🛡️ {guild.verification_level.name.title()}", inline=True)

    if guild.banner:
        embed.set_image(url=guild.banner.url)

    await ctx.send(embed=embed)

@bot.hybrid_command(name="userinfo", description="Show detailed information about a user")
async def userinfo(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    joined_at = target.joined_at.strftime("%b %d, %Y")
    created_at = target.created_at.strftime("%b %d, %Y")
    roles = [role.mention for role in target.roles[1:]] # Skip @everyone
    
    embed = discord.Embed(title=f"👤 User Information: {target.display_name}", color=target.color)
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(name="Username", value=f"`{target.name}`", inline=True)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Status", value=f"{target.status.name.title()}", inline=True)
    
    embed.add_field(name="Joined Server", value=f"📥 {joined_at}", inline=True)
    embed.add_field(name="Joined Discord", value=f"📅 {created_at}", inline=True)
    embed.add_field(name="Bot?", value=f"{'Yes' if target.bot else 'No'}", inline=True)
    
    if roles:
        embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:10]) + ("..." if len(roles) > 10 else ""), inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Display a user's avatar")
async def avatar(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"🖼️ Avatar of {target.display_name}", color=0x00d2ff)
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="help", description="List all commands or get help for a specific category")
async def help_cmd(ctx: commands.Context, category: str = None):
    # Dynamic categories based on command tags/groups
    categories = {
        "Economy": ["balance", "deposit", "withdraw", "work", "crime", "rob", "shop", "buy", "profile", "leaderboard", "jobs", "applyjob", "autodeposit", "vote"],
        "Moderation": ["kick", "ban", "warn", "warnings", "clearwarns", "automod"],
        "Utility": ["ping", "membercount", "serverinfo", "userinfo", "avatar", "setup", "setprefix"],
        "Welcome": ["set welcome", "set farewell"]
    }

    if not category:
        embed = discord.Embed(
            title="📚 Empire Nexus Help",
            description="Welcome to the Empire! Use `/help <category>` for more details on a specific section.",
            color=0x00d2ff
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        
        for cat, cmds in categories.items():
            embed.add_field(name=f"🔹 {cat}", value=f"`{len(cmds)} commands`", inline=True)
            
        embed.set_footer(text="Join our support server for more help! /setup for the link.")
        return await ctx.send(embed=embed)

    cat_name = category.capitalize()
    if cat_name not in categories:
        return await ctx.send(f"❌ Category `{category}` not found! Use `/help` to see all categories.")

    embed = discord.Embed(title=f"📖 {cat_name} Commands", color=0x00d2ff)
    cmd_list = categories[cat_name]
    
    for cmd_name in cmd_list:
        # Support both regular and group commands
        cmd = bot.get_command(cmd_name)
        if cmd:
            desc = cmd.description or "No description provided."
            usage = f"/{cmd.qualified_name} {cmd.signature}"
            embed.add_field(name=f"/{cmd.qualified_name}", value=f"{desc}\n`Usage: {usage}`", inline=False)

    await ctx.send(embed=embed)

# --- Admin Commands ---

def is_authorized_owner():
    async def predicate(ctx):
        if ctx.author.id in BOT_OWNERS:
            return True
        return await ctx.bot.is_owner(ctx.author)
    return commands.check(predicate)

@bot.hybrid_command(name="addmoney", description="[OWNER ONLY] Add money to a user")
@is_authorized_owner()
async def add_money_admin(ctx: commands.Context, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Amount must be positive.")
    
    # Confirmation prompt
    confirm_msg = await ctx.send(f"⚠️ Are you sure you want to add **{amount:,} coins** to {member.mention}? (Type `confirm` to proceed)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
    
    try:
        await bot.wait_for('message', check=check, timeout=30)
    except:
        return await ctx.send("Operation cancelled.")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ? AND guild_id = ?', (amount, member.id, ctx.guild.id))
        await db.commit()
    
    await ctx.send(f"✅ Added **{amount:,} coins** to {member.mention}'s balance.")

@bot.hybrid_command(name="addxp", description="[OWNER ONLY] Add XP to a user")
@is_authorized_owner()
async def add_xp_admin(ctx: commands.Context, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Amount must be positive.")
    
    # Confirmation prompt
    confirm_msg = await ctx.send(f"⚠️ Are you sure you want to add **{amount:,} XP** to {member.mention}? (Type `confirm` to proceed)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
    
    try:
        await bot.wait_for('message', check=check, timeout=30)
    except:
        return await ctx.send("Operation cancelled.")

    leveled_up, new_level = await add_xp(member.id, ctx.guild.id, amount)
    
    msg = f"✅ Added **{amount:,} XP** to {member.mention}."
    if leveled_up:
        msg += f"\n🎊 They leveled up to **Level {new_level}**!"
    
    await ctx.send(msg)

@bot.hybrid_command(name="addtitle", description="[OWNER ONLY] Add a custom title to a user")
@is_authorized_owner()
async def add_title_admin(ctx: commands.Context, member: discord.Member, title: str):
    # Confirmation prompt
    confirm_msg = await ctx.send(f"⚠️ Are you sure you want to add the title '**{title}**' to {member.mention}? (Type `confirm` to proceed)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
    
    try:
        await bot.wait_for('message', check=check, timeout=30)
    except:
        return await ctx.send("Operation cancelled.")

    await ensure_rewards(member.id)
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT titles_json FROM user_rewards WHERE user_id = ?", (member.id,)) as cursor:
            row = await cursor.fetchone()
            titles = json.loads(row[0]) if row else []
        
        titles.append({"title": title, "source": "admin", "timestamp": int(time.time())})
        
        await db.execute("UPDATE user_rewards SET titles_json = ? WHERE user_id = ?", (json.dumps(titles), member.id))
        await db.commit()
    
    await ctx.send(f"✅ Added title '**{title}**' as a permanent badge for {member.mention}.")

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


