import aiosqlite
import json
from shared.constants import DB_FILE, DEFAULT_ASSETS

class AssetsService:
    async def ensure_user(self, user_id: int, guild_id: int):
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)', (user_id, guild_id))
            await db.commit()

    async def get_guild_assets(self, guild_id: int):
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

    async def buy_asset(self, user_id: int, guild_id: int, asset_id: str, count: int):
        await self.ensure_user(user_id, guild_id)
        if count <= 0:
            return False, "Count must be positive."
        assets = await self.get_guild_assets(guild_id)
        if asset_id not in assets:
            return False, "Invalid asset ID!"
        asset = assets[asset_id]
        total_price = asset['price'] * count
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute('SELECT balance FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                balance = int((row[0] or 0)) if row else 0
            if balance < total_price:
                return False, f"You need **{total_price - balance:,} more coins**!"
            await db.execute('UPDATE users SET balance = MAX(0, COALESCE(balance,0) - ?) WHERE user_id = ? AND guild_id = ?', (total_price, user_id, guild_id))
            await db.execute('INSERT INTO user_assets (user_id, guild_id, asset_id, count) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, guild_id, asset_id) DO UPDATE SET count = count + ?', (user_id, guild_id, asset_id, count, count))
            await db.commit()
        return True, f"✅ Bought **{count}x {asset['name']}** for **{total_price:,} coins**!"
