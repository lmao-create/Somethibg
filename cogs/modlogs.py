import discord
from discord.ext import commands
from discord import app_commands
import json
import os


DATA_FILE = "modlogs.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


class ModLogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = load_data()

    # --------------------
    # SET MODLOG CHANNEL
    # --------------------
    @app_commands.command(
        name="setmodlog",
        description="Set the modlog channel for this server."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setmodlog(self, interaction: discord.Interaction, channel: discord.TextChannel):

        guild_id = str(interaction.guild.id)
        self.data[guild_id] = channel.id
        save_data(self.data)

        await interaction.response.send_message(
            f"✅ Modlog channel set to {channel.mention}",
            ephemeral=True
        )

    # --------------------
    # GET MODLOG CHANNEL
    # --------------------
    def get_modlog_channel(self, guild: discord.Guild):
        guild_id = str(guild.id)
        channel_id = self.data.get(guild_id)

        if not channel_id:
            return None

        return guild.get_channel(channel_id)

    # --------------------
    # CORE LOG FUNCTION
    # --------------------
    async def log(self, guild: discord.Guild, embed: discord.Embed):

        channel = self.get_modlog_channel(guild)
        if channel is None:
            return

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ModLogs(bot))