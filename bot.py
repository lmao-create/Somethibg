import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("TEST_GUILD_ID")


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        print("🚀 Loading cogs...\n")

        cogs = [
            "cogs.moderation",
            "cogs.modlogs",
            "cogs.warnings",
            "cogs.fun",
            "cogs.leveling",
            "cogs.economy",
            "cogs.qotd"
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ Loaded: {cog}")
            except Exception as e:
                print(f"❌ Failed to load: {cog}")
                print(e)

        print("\n=== SYNCING COMMANDS ===")

        try:
            if GUILD_ID:
                guild = discord.Object(id=int(GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)

                print(f"✅ Synced {len(synced)} guild commands")

            else:
                synced = await self.tree.sync()
                print(f"✅ Synced {len(synced)} global commands")

        except Exception as e:
            print(f"❌ Command sync failed: {e}")

    async def on_ready(self):
        print(f"\n🤖 Logged in as {self.user} (ID: {self.user.id})")
        print("✅ Bot is ready and online.")


bot = MyBot()


if __name__ == "__main__":

    if not TOKEN:
        raise RuntimeError("❌ DISCORD_TOKEN is missing in environment variables")

    print("🚀 Starting bot...")

    bot.run(TOKEN)