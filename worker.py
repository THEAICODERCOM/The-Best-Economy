import asyncio

class BossWorker:
    def __init__(self, bot, service):
        self.bot = bot
        self.service = service
        self._task = None
        self._interval = 30

    async def _loop(self):
        while True:
            try:
                if getattr(self.bot, "is_closed", lambda: True)():
                    break
                await self.service.check_and_spawn_for_all_guilds()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except:
                await asyncio.sleep(5)

    def start(self):
        try:
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._loop())
            return self._task
        except:
            return None
