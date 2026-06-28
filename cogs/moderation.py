import discord
from discord.ext import commands
from discord import app_commands

import asyncpg
import time
from datetime import timedelta
import os


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool: asyncpg.Pool | None = None

    # -----------------------------
    # STARTUP
    # -----------------------------
    async def cog_load(self):
        self.pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10
        )

        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT,
                    user_id BIGINT,
                    moderator_id BIGINT,
                    reason TEXT,
                    created_at BIGINT
                )
            """)

        print("✅ Moderation system loaded (PostgreSQL)")

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    # -----------------------------
    # EMBED HELPER
    # -----------------------------
    def create_embed(self, title: str, color: discord.Color, **fields):
        embed = discord.Embed(title=title, color=color)
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=False)
        return embed

    # -----------------------------
    # ADD WARNING
    # -----------------------------
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):

        async with self.pool.acquire() as conn:

            await conn.execute("""
                INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at)
                VALUES ($1, $2, $3, $4, $5)
            """, guild_id, user_id, moderator_id, reason, int(time.time()))

            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM warnings
                WHERE guild_id=$1 AND user_id=$2
            """, guild_id, user_id)

        return count

    # -----------------------------
    # WARN COMMAND
    # -----------------------------
    @app_commands.command(name="warn")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str | None = None
    ):

        reason_text = reason or "No reason provided"

        count = await self.add_warning(
            interaction.guild.id,
            member.id,
            interaction.user.id,
            reason_text
        )

        # 🔥 DM USER IF REASON EXISTS
        if reason:
            try:
                await member.send(
                    f"⚠️ You were warned in **{interaction.guild.name}**\n"
                    f"Reason: {reason_text}"
                )
            except discord.Forbidden:
                pass

        embed = self.create_embed(
            "Member Warned",
            discord.Color.yellow(),
            User=f"{member} ({member.id})",
            Moderator=interaction.user.mention,
            Reason=reason_text,
            Total_Warnings=str(count)
        )

        await interaction.response.send_message(
            f"⚠️ {member.mention} warned. Total: {count}"
        )

    # -----------------------------
    # VIEW WARNINGS
    # -----------------------------
    @app_commands.command(name="warnings")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, reason, moderator_id, created_at
                FROM warnings
                WHERE guild_id=$1 AND user_id=$2
                ORDER BY created_at DESC
            """, interaction.guild.id, member.id)

        if not rows:
            return await interaction.response.send_message("No warnings found.")

        text = ""

        for r in rows:
            mod = interaction.guild.get_member(r["moderator_id"])
            mod_name = mod.mention if mod else "Unknown"

            text += f"⚠️ ID `{r['id']}` — {r['reason']} — by {mod_name}\n"

        embed = discord.Embed(
            title=f"Warnings for {member}",
            description=text,
            color=discord.Color.yellow()
        )

        await interaction.response.send_message(embed=embed)

    # -----------------------------
    # REMOVE WARNING
    # -----------------------------
    @app_commands.command(name="warnings_remove")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings_remove(
        self,
        interaction: discord.Interaction,
        warn_id: int
    ):

        async with self.pool.acquire() as conn:

            result = await conn.execute("""
                DELETE FROM warnings
                WHERE id=$1 AND guild_id=$2
            """, warn_id, interaction.guild.id)

        if result == "DELETE 0":
            return await interaction.response.send_message(
                "❌ Warning not found.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"🗑️ Warning `{warn_id}` removed."
        )

    # -----------------------------
    # CLEAR WARNINGS
    # -----------------------------
    @app_commands.command(name="warnings_clear")
    @app_commands.checks.has_permissions(administrator=True)
    async def warnings_clear(self, interaction: discord.Interaction, member: discord.Member):

        async with self.pool.acquire() as conn:

            await conn.execute("""
                DELETE FROM warnings
                WHERE guild_id=$1 AND user_id=$2
            """, interaction.guild.id, member.id)

        await interaction.response.send_message(
            f"🧹 Cleared all warnings for {member.mention}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))