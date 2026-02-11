import asyncio

class ResponseBuilder:
    async def send_progress(self, ctx, text: str):
        try:
            if ctx.interaction:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.defer(ephemeral=False)
                await ctx.followup.send(text)
            else:
                await ctx.send(text)
        except:
            pass

    async def send_dm_or_channel(self, ctx, message: str):
        try:
            await ctx.author.send(message)
            try:
                if ctx.interaction:
                    await ctx.followup.send("Sent you a DM.")
                else:
                    await ctx.send("Sent you a DM.")
            except:
                pass
            return
        except:
            pass
        try:
            chunks = []
            s = message
            while len(s) > 0:
                chunks.append(s[:1800])
                s = s[1800:]
            if ctx.interaction:
                for part in chunks:
                    try:
                        await ctx.followup.send(part)
                    except:
                        pass
            else:
                for part in chunks:
                    try:
                        await ctx.send(part)
                    except:
                        pass
        except:
            try:
                await ctx.send("Could not DM or post here.")
            except:
                pass
