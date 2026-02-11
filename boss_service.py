import random
import time
import aiosqlite
import discord
from shared.constants import DB_FILE

class BossService:
    def __init__(self, bot, loot_items: dict, bosses: list[dict]):
        self.bot = bot
        self.loot_items = loot_items
        self.bosses = bosses

    def hp_bar(self, hp: int, max_hp: int, length: int = 20) -> str:
        pct = 0 if max_hp <= 0 else max(0, min(1, hp / max_hp))
        filled = int(length * pct)
        return "█" * filled + "░" * (length - filled)

    async def get_interval(self, guild_id: int) -> int:
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute('SELECT boss_spawn_interval FROM guild_config WHERE guild_id = ?', (guild_id,)) as c:
                row = await c.fetchone()
                return int(row[0]) if row and row[0] else 3600

    async def get_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        try:
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute('SELECT boss_channel_id FROM guild_config WHERE guild_id = ?', (guild.id,)) as c:
                    row = await c.fetchone()
            if row and row[0]:
                ch = guild.get_channel(int(row[0]))
                if ch:
                    me = guild.me or guild.get_member(self.bot.user.id)
                    if me and ch.permissions_for(me).send_messages:
                        return ch
        except:
            pass
        return None

    def pick_text_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        for ch in getattr(guild, "text_channels", []):
            me = guild.me or guild.get_member(self.bot.user.id)
            if not me:
                return ch
            try:
                if ch.permissions_for(me).send_messages:
                    return ch
            except:
                continue
        return None

    async def spawn_boss(self, guild: discord.Guild):
        if not guild:
            return
        boss = random.choice(self.bosses)
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO boss_state (guild_id, boss_name, difficulty, max_hp, hp, spawned_at, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)',
                             (guild.id, boss["name"], boss["difficulty"], boss["hp"], boss["hp"], int(time.time())))
            await db.execute('DELETE FROM boss_damage WHERE guild_id = ?', (guild.id,))
            await db.commit()
        ch = await self.get_channel(guild) or self.pick_text_channel(guild)
        if ch:
            embed = discord.Embed(title=f"👹 Boss Spawned — {boss['name']}", color=discord.Color.red(), timestamp=discord.utils.utcnow())
            embed.add_field(name="Difficulty", value=boss["difficulty"], inline=True)
            embed.add_field(name="HP", value=f"{boss['hp']:,}\n{self.hp_bar(boss['hp'], boss['hp'])}", inline=True)
            try:
                await ch.send(embed=embed)
            except:
                pass

    async def get_boss(self, guild_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM boss_state WHERE guild_id = ?', (guild_id,)) as c:
                return await c.fetchone()

    async def set_boss_hp(self, guild_id: int, new_hp: int):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('UPDATE boss_state SET hp = ?, is_active = CASE WHEN ? <= 0 THEN 0 ELSE 1 END WHERE guild_id = ?', (max(0, new_hp), new_hp, guild_id))
            await db.commit()

    async def add_damage(self, guild_id: int, user_id: int, dmg: int):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT INTO boss_damage (guild_id, user_id, damage) VALUES (?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET damage = damage + ?', (guild_id, user_id, dmg, dmg))
            await db.commit()

    def rarity_chance(self, rarity: str) -> float:
        return {"common": 0.6, "uncommon": 0.4, "rare": 0.25, "epic": 0.10, "legendary": 0.04}.get(rarity, 0.2)

    async def distribute_loot(self, guild: discord.Guild):
        boss = await self.get_boss(guild.id)
        if not boss:
            return
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute('SELECT SUM(damage) FROM boss_damage WHERE guild_id = ?', (guild.id,)) as c:
                total = (await c.fetchone())[0] or 0
            async with db.execute('SELECT user_id, damage FROM boss_damage WHERE guild_id = ?', (guild.id,)) as c:
                rows = await c.fetchall()
        if total <= 0 or not rows:
            return
        lootable_ids = next((b["loot"] for b in self.bosses if b["name"] == boss["boss_name"]), [])
        for uid, dmg in rows:
            share = (dmg or 0) / (total or 1)
            drop_pool = []
            for iid in lootable_ids:
                item = self.loot_items[iid]
                chance = self.rarity_chance(item["rarity"]) * share
                if chance >= 0.9 or random.random() < chance:
                    drop_pool.append(iid)
            awarded = drop_pool or ([random.choice(lootable_ids)] if lootable_ids else [])
            for iid in awarded:
                item = self.loot_items[iid]
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('INSERT INTO boss_items (user_id, item_id, count) VALUES (?, ?, 1) ON CONFLICT(user_id, item_id) DO UPDATE SET count = count + 1', (uid, iid))
                    await db.commit()
            member = guild.get_member(uid)
            if member:
                try:
                    await member.send(f"🎁 Boss defeated in {guild.name}! You received: " + ", ".join([self.loot_items[i]['name'] for i in awarded]))
                except:
                    pass

    async def check_and_spawn_for_all_guilds(self):
        try:
            now = int(time.time())
            for g in self.bot.guilds:
                boss = await self.get_boss(g.id)
                interval = await self.get_interval(g.id)
                if not boss or not boss["is_active"] or (boss["spawned_at"] or 0) + interval <= now:
                    await self.spawn_boss(g)
        except:
            pass
