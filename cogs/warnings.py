import discord
from discord.ext import commands
from discord import app_commands
import json
import os


WARN_FILE = "warnings.json"


def load_warns():
    if not os.path.exists(WARN_FILE):
        return {}
    with open(WARN_FILE, "r") as f:
        return json.load(f)


def save_warns(data):
    with open(WARN_FILE, "w") as f:
        json.dump(data, f, indent=4)


class Warnings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warns = load_warns()

    def add_warn(self, guild_id: int, user_id: int, reason: str):
        gid = str(guild_id)
        uid = str(user_id)

        if gid not in self.warns:
            self.warns[gid] = {}

        if uid not in self.warns[gid]:
            self.warns[gid][uid] = []

        self.warns[gid][uid].append(reason)
        save_warns(self.warns)

        return len(self.warns[gid][uid])

    def get_warns(self, guild_id: int, user_id: int):
        return self.warns.get(str(guild_id), {}).get(str(user_id), [])


async def setup(bot: commands.Bot):
    await bot.add_cog(Warnings(bot))