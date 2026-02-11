import asyncio

class TaskManager:
    def __init__(self):
        self.tasks: list[asyncio.Task] = []

    def register(self, coro):
        try:
            t = asyncio.create_task(coro)
            self.tasks.append(t)
        except:
            pass

    def cancel_all(self):
        for t in self.tasks:
            try:
                t.cancel()
            except:
                pass
