import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime


FILE = "qotd.json"


def load():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r") as f:
        return json.load(f)


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=4)


class QOTD(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load()
        self.task.start()

    # --------------------
    # SET CHANNEL
    # --------------------
    @commands.hybrid_command(name="setqotd", description="Set QOTD channel")
    @commands.has_permissions(administrator=True)
    async def setqotd(self, ctx: commands.Context, channel: discord.TextChannel):

        self.data["channel_id"] = channel.id
        save(self.data)

        await ctx.send(f"✅ QOTD channel set to {channel.mention}")

    # --------------------
    # SET QUESTION
    # --------------------
    @commands.hybrid_command(name="setquestion", description="Set today's QOTD")
    @commands.has_permissions(administrator=True)
    async def setquestion(self, ctx: commands.Context, *, question: str):

        self.data["question"] = question
        save(self.data)

        await ctx.send("✅ QOTD updated for today.")

    # --------------------
    # DAILY TASK
    # --------------------
    @tasks.loop(minutes=60)
    async def task(self):
        await self.bot.wait_until_ready()

        channel_id = self.data.get("channel_id")
        question = self.data.get("question")

        if not channel_id or not question:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        today = datetime.utcnow().strftime("%Y-%m-%d")

        if self.data.get("last_sent") == today:
            return

        embed = discord.Embed(
            title="💬 Question of the Day",
            description=question,
            color=discord.Color.blurple()
        )

        await channel.send(embed=embed)

        self.data["last_sent"] = today
        self.data["question"] = None  # reset after sending
        save(self.data)

    # --------------------
    # SAFELY STOP TASK
    # --------------------
    def cog_unload(self):
        self.task.cancel()


async def setup(bot: commands.Bot):
    await bot.add_cog(QOTD(bot))