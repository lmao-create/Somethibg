import discord
from discord.ext import commands
from discord import app_commands


class Sync(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------
    # GLOBAL SLASH SYNC COMMAND
    # -----------------------------
    @app_commands.command(name="sync", description="Sync slash commands")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):

        try:
            synced = await self.bot.tree.sync()

            await interaction.response.send_message(
                f"✅ Synced {len(synced)} commands globally!",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Sync failed: {e}",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Sync(bot))