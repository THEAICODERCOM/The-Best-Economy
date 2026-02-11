DB_FILE = 'empire_v2.db'
DISCORD_API_BASE_URL = 'https://discord.com/api/v10'
INVITE_PERMISSIONS = (
    8 | 2 | 4 | 16 | 32 | 128 |
    1024 | 2048 | 8192 | 16384 | 32768 | 65536 | 64 | 262144 |
    1048576 | 2097152 | 4194304 | 8388608 | 16777216 |
    67108864 | 134217728 | 268435456 | 536870912 |
    2147483648
)
DEFAULT_BANK_PLANS = {
    "standard": {
        "name": "Standard Vault",
        "min": 0.01,
        "max": 0.02,
        "price": 0,
        "min_level": 0
    },
    "premium": {
        "name": "Premium Vault",
        "min": 0.02,
        "max": 0.03,
        "price": 25000,
        "min_level": 10
    },
    "royal": {
        "name": "Royal Vault",
        "min": 0.03,
        "max": 0.05,
        "price": 100000,
        "min_level": 25
    }
}
DEFAULT_ASSETS = {
    "lemonade_stand": {"name": "Lemonade Stand", "price": 500, "income": 5},
    "gaming_pc": {"name": "Gaming PC", "price": 2500, "income": 30},
    "coffee_shop": {"name": "Coffee Shop", "price": 10000, "income": 150},
}
DAILY_QUESTS = [
    {"id": "daily_cmd_25", "description": "Use 25 commands today", "target": 25, "reward": 10000},
    {"id": "daily_cmd_50", "description": "Use 50 commands today", "target": 50, "reward": 20000},
    {"id": "daily_cmd_75", "description": "Use 75 commands today", "target": 75, "reward": 35000},
    {"id": "daily_cmd_100", "description": "Use 100 commands today", "target": 100, "reward": 50000},
    {"id": "daily_cmd_150", "description": "Use 150 commands today", "target": 150, "reward": 80000},
    {"id": "daily_cmd_10", "description": "Use 10 commands today", "target": 10, "reward": 5000},
    {"id": "daily_cmd_5", "description": "Use 5 commands today", "target": 5, "reward": 2000},
    {"id": "daily_cmd_200", "description": "Use 200 commands today", "target": 200, "reward": 120000},
    {"id": "daily_work_10", "description": "Work 10 times", "target": 10, "reward": 25000, "kind": "work"},
    {"id": "daily_crime_3", "description": "Succeed 3 crimes", "target": 3, "reward": 30000, "kind": "crime_success"},
    {"id": "daily_blackjack_3", "description": "Win 3 blackjack games", "target": 3, "reward": 35000, "kind": "blackjack_wins"},
    {"id": "daily_rob_2", "description": "Successfully rob 2 users", "target": 2, "reward": 40000, "kind": "rob_success"},
]
WEEKLY_QUESTS = [
    {"id": "weekly_cmd_100", "description": "Use 100 commands this week", "target": 100, "reward": 40000},
    {"id": "weekly_cmd_200", "description": "Use 200 commands this week", "target": 200, "reward": 90000},
    {"id": "weekly_cmd_300", "description": "Use 300 commands this week", "target": 300, "reward": 140000},
    {"id": "weekly_cmd_400", "description": "Use 400 commands this week", "target": 400, "reward": 190000},
    {"id": "weekly_cmd_500", "description": "Use 500 commands this week", "target": 500, "reward": 250000},
    {"id": "weekly_cmd_750", "description": "Use 750 commands this week", "target": 750, "reward": 375000},
    {"id": "weekly_cmd_50", "description": "Use 50 commands this week", "target": 50, "reward": 25000},
    {"id": "weekly_cmd_1000", "description": "Use 1000 commands this week", "target": 1000, "reward": 500000},
    {"id": "weekly_work_50", "description": "Work 50 times", "target": 50, "reward": 150000, "kind": "work"},
    {"id": "weekly_crime_15", "description": "Succeed 15 crimes", "target": 15, "reward": 200000, "kind": "crime_success"},
    {"id": "weekly_blackjack_20", "description": "Win 20 blackjack games", "target": 20, "reward": 220000, "kind": "blackjack_wins"},
    {"id": "weekly_rob_10", "description": "Successfully rob 10 users", "target": 10, "reward": 250000, "kind": "rob_success"},
]
