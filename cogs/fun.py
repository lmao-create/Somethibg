import random
import discord
from discord.ext import commands
from discord import app_commands


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Check bot latency"
    )
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! {latency}ms"
        )

    @app_commands.command(
        name="coinflip",
        description="Flip a coin"
    )
    async def coinflip(self, interaction: discord.Interaction):
        result = random.choice(["Heads", "Tails"])
        await interaction.response.send_message(
            f"🪙 {result}"
        )

    @app_commands.command(
        name="8ball",
        description="Ask the magic 8-ball"
    )
    async def eightball(
        self,
        interaction: discord.Interaction,
        question: str
    ):
        responses = [
            "Yes",
            "No",
            "Maybe",
            "Definitely",
            "Absolutely",
            "Ask again later",
            "I don't think so"
        ]

        await interaction.response.send_message(
            f"🎱 Question: {question}\n"
            f"Answer: {random.choice(responses)}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))