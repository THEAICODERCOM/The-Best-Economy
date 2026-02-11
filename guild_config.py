from dataclasses import dataclass
from typing import Optional

@dataclass
class GuildConfig:
    guild_id: int
    marketplace_enabled: int = 1
    marketplace_tax: int = 0
    vassal_max_percent: int = 15
    alliances_enabled: int = 1
    mod_message_point: int = 1
    mod_warn_point: int = 5
    mod_kick_point: int = 10
    mod_ban_point: int = 15
    mod_timeout_point: int = 4
