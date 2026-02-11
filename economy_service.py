import asyncio
import aiosqlite
from shared.constants import DB_FILE
import random
import time
import json
from shared.constants import DAILY_QUESTS, WEEKLY_QUESTS

class EconomyService:
    async def ensure_user(self, user_id: int, guild_id: int):
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)', (user_id, guild_id))
                    await db.commit()
                return
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                raise

    async def add_money(self, user_id: int, guild_id: int, amount: int):
        await self.ensure_user(user_id, guild_id)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ? WHERE user_id = ? AND guild_id = ?', (amount, user_id, guild_id))
                    await db.commit()
                return True
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False
        return False
    async def get_global_money(self, user_id: int):
        await self.ensure_user(user_id, 0)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    db.row_factory = aiosqlite.Row
                    async with db.execute('SELECT user_id, guild_id, balance, bank, bank_plan, last_work, last_crime, last_rob FROM users WHERE user_id = ? AND guild_id = 0', (user_id,)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            return row
                    async with db.execute('SELECT COALESCE(SUM(balance),0), COALESCE(SUM(bank),0) FROM users WHERE user_id = ?', (user_id,)) as cursor:
                        agg = await cursor.fetchone()
                    balance_sum = int((agg[0] or 0))
                    bank_sum = int((agg[1] or 0))
                    await db.execute('INSERT OR REPLACE INTO users (user_id, guild_id, balance, bank, bank_plan) VALUES (?, 0, ?, ?, ?)', (user_id, balance_sum, bank_sum, 'standard'))
                    await db.commit()
                async with aiosqlite.connect(DB_FILE) as db2:
                    await db2.execute('PRAGMA busy_timeout=2000')
                    db2.row_factory = aiosqlite.Row
                    async with db2.execute('SELECT user_id, guild_id, balance, bank, bank_plan, last_work, last_crime, last_rob FROM users WHERE user_id = ? AND guild_id = 0', (user_id,)) as cursor2:
                        return await cursor2.fetchone()
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                raise
    async def move_global_wallet_to_bank(self, user_id: int, amount: int):
        await self.ensure_user(user_id, 0)
        amt = int(amount)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?), bank = COALESCE(bank,0) + ? WHERE user_id = ? AND guild_id = 0', (amt, amt, user_id))
                    await db.commit()
                return True
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False
        return False
    async def move_global_bank_to_wallet(self, user_id: int, amount: int):
        await self.ensure_user(user_id, 0)
        amt = int(amount)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET bank = MAX(0, COALESCE(bank,0) - ?), balance = COALESCE(balance,0) + ? WHERE user_id = ? AND guild_id = 0', (amt, amt, user_id))
                    await db.commit()
                return True
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False
        return False
    async def switch_bank_plan(self, user_id: int, plan_id: str, price: int):
        await self.ensure_user(user_id, 0)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    if price > 0:
                        await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?), bank_plan = ? WHERE user_id = ? AND guild_id = 0', (price, plan_id, user_id))
                    else:
                        await db.execute('UPDATE users SET bank_plan = ? WHERE user_id = ? AND guild_id = 0', (plan_id, user_id))
                    await db.commit()
                return True
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False
        return False
    async def transfer_global_balance(self, sender_id: int, receiver_id: int, amount: int):
        await self.ensure_user(sender_id, 0)
        await self.ensure_user(receiver_id, 0)
        amt = int(amount)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?) WHERE user_id = ? AND guild_id = 0', (amt, sender_id))
                    await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ? WHERE user_id = ? AND guild_id = 0', (amt, receiver_id))
                    await db.commit()
                return True
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False
        return False
    async def rob_user(self, stealer_id: int, victim_id: int):
        stealer = await self.get_global_money(stealer_id)
        victim = await self.get_global_money(victim_id)
        now = int(time.time())
        if victim['balance'] < 500:
            return False, "Target is too poor! They need at least 500 coins."
        if now - int(stealer['last_rob'] or 0) < 1800:
            return False, f"Wait {1800 - (now - int(stealer['last_rob'] or 0))}s."
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    if random.random() < 0.35:
                        stolen = random.randint(50, max(50, int(victim['balance'] * 0.25)))
                        await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ?, last_rob = ?, successful_robs = COALESCE(successful_robs,0) + 1 WHERE user_id = ? AND guild_id = 0', (stolen, now, stealer_id))
                        await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?) WHERE user_id = ? AND guild_id = 0', (stolen, victim_id))
                        await db.commit()
                        return True, stolen
                    else:
                        fine = random.randint(300, 600)
                        await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?), last_rob = ? WHERE user_id = ? AND guild_id = 0', (fine, now, stealer_id))
                        await db.commit()
                        return False, fine
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False, "error"
        return False, "error"
    async def crime_action(self, user_id: int):
        data = await self.get_global_money(user_id)
        now = int(time.time())
        if now - int(data['last_crime'] or 0) < 1800:
            return False, f"🚔 Cops are searching for you! Wait {1800 - (now - int(data['last_crime'] or 0))}s."
        base = random.randint(1000, 3000) * int(data['level'] or 1)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    if random.random() < 0.30:
                        await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ?, last_crime = ?, successful_crimes = COALESCE(successful_crimes,0) + 1 WHERE user_id = ? AND guild_id = 0', (base, now, user_id))
                        await db.commit()
                        return True, base
                    else:
                        loss = random.randint(500, 1000)
                        await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?), last_crime = ? WHERE user_id = ? AND guild_id = 0', (loss, now, user_id))
                        await db.commit()
                        return False, loss
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False, "error"
        return False, "error"
    async def add_xp_and_level(self, user_id: int, guild_id: int, amount: int):
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET xp = COALESCE(xp,0) + ? WHERE user_id = ? AND guild_id = ?', (amount, user_id, guild_id))
                    await db.commit()
                    async with db.execute('SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            current_xp = int(row[0] or 0)
                            current_level = int(row[1] or 1)
                            next_level_xp = max(100, current_level * 100)
                            if current_xp >= next_level_xp:
                                new_level = current_level + 1
                                await db.execute('UPDATE users SET level = ?, xp = xp - ? WHERE user_id = ? AND guild_id = ?', (new_level, next_level_xp, user_id, guild_id))
                                await db.commit()
                                return True, new_level
                break
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                raise
        return False, None
    async def work_action(self, user_id: int, guild_id: int):
        data = await self.get_global_money(user_id)
        now = int(time.time())
        if now - int(data['last_work'] or 0) < 300:
            return False, f"⏳ Your workers are tired! Wait {300 - (now - int(data['last_work'] or 0))}s."
        base = random.randint(100, 300) * int(data['level'] or 1) * (int(data['prestige'] or 0) + 1)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ?, last_work = ? WHERE user_id = ? AND guild_id = 0', (base, now, user_id))
                    await db.commit()
                leveled_up, new_level = await self.add_xp_and_level(user_id, guild_id, 20)
                return True, base, leveled_up, new_level
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False, "error", False, None
        return False, "error", False, None
    def _pick_daily(self, guild_id: int, timestamp: int | None = None):
        ts = int(time.time()) if timestamp is None else int(timestamp)
        day = ts // 86400
        seed = f"{guild_id}-{day}-daily"
        rng = random.Random(seed)
        pool = list(DAILY_QUESTS)
        rng.shuffle(pool)
        return pool[:3]
    def _pick_weekly(self, guild_id: int, timestamp: int | None = None):
        ts = int(time.time()) if timestamp is None else int(timestamp)
        week = ts // 604800
        seed = f"{guild_id}-{week}-weekly"
        rng = random.Random(seed)
        pool = list(WEEKLY_QUESTS)
        rng.shuffle(pool)
        return pool[:3]
    async def ensure_quest_resets(self, user_id: int, guild_id: int):
        await self.ensure_user(user_id, guild_id)
        now = int(time.time())
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    async with db.execute('SELECT daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_quest_completed_json, weekly_quest_completed_json, daily_stats_json, weekly_stats_json FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
                        row = await cursor.fetchone()
                    if not row:
                        await db.execute('INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)', (user_id, guild_id))
                        await db.commit()
                        return
                    daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json = row
                    if daily_reset is None or daily_reset == 0 or now - int(daily_reset or 0) >= 86400:
                        daily_reset = now
                        daily_commands = 0
                        daily_reward_claimed = 0
                        daily_completed_json = '{}'
                        daily_stats_json = '{}'
                    if weekly_reset is None or weekly_reset == 0 or now - int(weekly_reset or 0) >= 604800:
                        weekly_reset = now
                        weekly_commands = 0
                        weekly_reward_claimed = 0
                        weekly_completed_json = '{}'
                        weekly_stats_json = '{}'
                    await db.execute('UPDATE users SET daily_reset = ?, weekly_reset = ?, daily_commands = ?, weekly_commands = ?, daily_reward_claimed = ?, weekly_reward_claimed = ?, daily_quest_completed_json = ?, weekly_quest_completed_json = ?, daily_stats_json = ?, weekly_stats_json = ? WHERE user_id = ? AND guild_id = ?', (daily_reset, weekly_reset, daily_commands, weekly_commands, daily_reward_claimed, weekly_reward_claimed, daily_completed_json, weekly_completed_json, daily_stats_json, weekly_stats_json, user_id, guild_id))
                    await db.commit()
                return
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                raise
    async def get_quest_state(self, user_id: int, guild_id: int):
        await self.ensure_quest_resets(user_id, guild_id)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    async with db.execute('SELECT daily_commands, weekly_commands, daily_quest_completed_json, weekly_quest_completed_json FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
                        row = await cursor.fetchone()
                daily_commands = int((row[0] or 0)) if row else 0
                weekly_commands = int((row[1] or 0)) if row else 0
                try:
                    daily_completed = json.loads(row[2] or '{}') if row else {}
                except:
                    daily_completed = {}
                try:
                    weekly_completed = json.loads(row[3] or '{}') if row else {}
                except:
                    weekly_completed = {}
                return {
                    "daily_commands": daily_commands,
                    "weekly_commands": weekly_commands,
                    "daily_completed": daily_completed,
                    "weekly_completed": weekly_completed
                }
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                raise
    async def claim_daily(self, user_id: int):
        data = await self.get_global_money(user_id)
        now = int(time.time())
        last = int(data['last_login'] or 0)
        streak = int(data['login_streak'] or 0)
        if last and now - last < 86400:
            remaining = 86400 - (now - last)
            return False, remaining, streak, 0
        if last and now - last <= 172800:
            streak += 1
        else:
            streak = 1
        reward = 10000 + (streak * 2000)
        tries = 4
        delay = 0.05
        for i in range(tries):
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    await db.execute('PRAGMA busy_timeout=2000')
                    await db.execute('UPDATE users SET balance = COALESCE(balance,0) + ?, last_login = ?, login_streak = ? WHERE user_id = ? AND guild_id = 0', (reward, now, streak, user_id))
                    await db.commit()
                return True, 0, streak, reward
            except Exception as e:
                if "database is locked" in str(e).lower():
                    await asyncio.sleep(delay * (i + 1))
                    continue
                return False, 0, streak, 0
        return False, 0, streak, 0
