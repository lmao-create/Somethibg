import discord
from discord.ext import commands
from discord import app_commands

import asyncpg
import random
import time
import io
import os

from PIL import Image, ImageDraw, ImageFont


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pool: asyncpg.Pool | None = None

        self.xp_cooldown = 30  # anti-spam XP system

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
                CREATE TABLE IF NOT EXISTS levels (
                    user_id BIGINT PRIMARY KEY,
                    xp INT DEFAULT 0,
                    level INT DEFAULT 1,
                    last_xp BIGINT DEFAULT 0
                )
            """)

        print("✅ Leveling system loaded (PostgreSQL)")

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    # -----------------------------
    # HELPERS
    # -----------------------------
    def now(self):
        return int(time.time())

    def required_xp(self, level: int) -> int:
        return 100 * level

    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO levels (user_id)
                VALUES ($1)
                ON CONFLICT (user_id)
                DO UPDATE SET user_id = EXCLUDED.user_id
                RETURNING user_id, xp, level, last_xp
            """, user_id)

    # -----------------------------
    # XP SYSTEM (ANTI-EXPLOIT)
    # -----------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):

        if message.author.bot or not message.guild:
            return

        async with self.pool.acquire() as conn:

            data = await conn.fetchrow("""
                SELECT xp, level, last_xp
                FROM levels
                WHERE user_id = $1
            """, message.author.id)

            if not data:
                await conn.execute("""
                    INSERT INTO levels (user_id)
                    VALUES ($1)
                """, message.author.id)
                xp, level, last_xp = 0, 1, 0
            else:
                xp, level, last_xp = data

            # 🔒 anti-spam XP cooldown
            now = self.now()
            if now - last_xp < self.xp_cooldown:
                return

            xp_gain = random.randint(5, 15)
            xp += xp_gain
            last_xp = now

            needed = self.required_xp(level)

            leveled_up = False
            if xp >= needed:
                xp -= needed
                level += 1
                leveled_up = True

            await conn.execute("""
                UPDATE levels
                SET xp=$1, level=$2, last_xp=$3
                WHERE user_id=$4
            """, xp, level, last_xp, message.author.id)

        if leveled_up:
            await message.channel.send(
                f"🎉 {message.author.mention} reached **Level {level}**!"
            )

    # -----------------------------
    # RANK CARD
    # -----------------------------
    def draw_bar(self, draw, x, y, width, height, progress):
        filled = int(width * progress)

        for i in range(filled):
            r = int(0 + (180 - 0) * (i / width))
            g = int(200 + (0 - 200) * (i / width))
            b = int(255 + (255 - 255) * (i / width))

            draw.line([(x + i, y), (x + i, y + height)], fill=(r, g, b))

    async def generate_rank_card(self, member, xp, level):

        width, height = 900, 300
        image = Image.new("RGB", (width, height), (20, 20, 20))
        draw = ImageDraw.Draw(image)

        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

        required = self.required_xp(level)
        progress = min(xp / required, 1)

        draw.rounded_rectangle((20, 20, 880, 280), radius=20, fill=(35, 35, 35))

        bar_x, bar_y = 250, 200
        bar_w, bar_h = 600, 25

        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
            radius=10,
            fill=(60, 60, 60)
        )

        self.draw_bar(draw, bar_x, bar_y, bar_w, bar_h, progress)

        draw.text((250, 50), member.display_name, fill=(255, 255, 255), font=font_big)
        draw.text((250, 110), f"Level: {level}", fill=(200, 200, 200), font=font_small)
        draw.text((250, 140), f"XP: {xp}/{required}", fill=(200, 200, 200), font=font_small)

        avatar_bytes = await member.display_avatar.with_size(128).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((150, 150))

        mask = Image.new("L", (150, 150), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 150, 150), fill=255)

        image.paste(avatar, (50, 75), mask)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    # -----------------------------
    # /RANK
    # -----------------------------
    @app_commands.command(name="rank")
    async def rank(self, interaction: discord.Interaction, member: discord.Member = None):

        member = member or interaction.user

        data = await self.get_user(member.id)

        image = await self.generate_rank_card(member, data["xp"], data["level"])

        await interaction.response.send_message(
            file=discord.File(image, "rank.png")
        )

    # -----------------------------
    # /LEADERBOARD (FAST)
    # -----------------------------
    @app_commands.command(name="leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):

        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, level, xp
                FROM levels
                ORDER BY level DESC, xp DESC
                LIMIT 10
            """)

        embed = discord.Embed(title="🏆 XP Leaderboard")

        medals = ["🥇", "🥈", "🥉"]
        text = ""

        for i, r in enumerate(rows, 1):
            member = interaction.guild.get_member(r["user_id"])
            name = member.display_name if member else f"User {r['user_id']}"

            rank = medals[i - 1] if i <= 3 else f"#{i}"

            text += f"{rank} **{name}** — Level {r['level']} • XP {r['xp']}\n"

        embed.description = text

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))