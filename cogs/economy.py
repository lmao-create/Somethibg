import os
import random
import time
import discord
import asyncpg

from discord.ext import commands
from discord import app_commands

LOG_CHANNEL_ID = 1519659517640446064


class Economy(commands.Cog):
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
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    balance BIGINT DEFAULT 0,
                    bank BIGINT DEFAULT 0,
                    last_rob BIGINT DEFAULT 0,
                    last_crime BIGINT DEFAULT 0
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS shop (
                    item TEXT PRIMARY KEY,
                    price INTEGER NOT NULL
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id BIGINT,
                    item TEXT,
                    quantity INTEGER DEFAULT 1,
                    PRIMARY KEY (user_id, item)
                )
            """)

        print("✅ Economy loaded with PostgreSQL + anti-exploit system")

    async def cog_unload(self):
        if self.pool:
            await self.pool.close()

    # -----------------------------
    # HELPERS
    # -----------------------------
    def now(self):
        return int(time.time())

    async def db_fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def db_fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def db_execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    # -----------------------------
    # LOGGING
    # -----------------------------
    async def log(self, title: str, description: str, color=discord.Color.orange()):
        channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
        )

        await channel.send(embed=embed)

    # -----------------------------
    # GET USER (FAST + ATOMIC)
    # -----------------------------
    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                INSERT INTO users (user_id)
                VALUES ($1)
                ON CONFLICT (user_id)
                DO UPDATE SET user_id = EXCLUDED.user_id
                RETURNING user_id, balance, bank
            """, user_id)

    # -----------------------------
    # BALANCE
    # -----------------------------
    @app_commands.command(name="balance")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):

        member = member or interaction.user
        user = await self.get_user(member.id)

        embed = discord.Embed(title="💰 Balance", color=discord.Color.green())
        embed.add_field(name="Wallet", value=f"{user['balance']:,}")
        embed.add_field(name="Bank", value=f"{user['bank']:,}")

        await interaction.response.send_message(embed=embed)

    # -----------------------------
    # ADD MONEY
    # -----------------------------
    @app_commands.command(name="addmoney")
    @app_commands.checks.has_permissions(administrator=True)
    async def addmoney(self, interaction: discord.Interaction, member: discord.Member, amount: int):

        if amount <= 0:
            return await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)

        await self.db_execute("""
            UPDATE users
            SET balance = balance + $1
            WHERE user_id = $2
        """, amount, member.id)

        await interaction.response.send_message(f"✅ Added {amount:,} coins.")
        await self.log("Money Added", f"{interaction.user} gave {amount:,} to {member}")

    # -----------------------------
    # REMOVE MONEY
    # -----------------------------
    @app_commands.command(name="removemoney")
    @app_commands.checks.has_permissions(administrator=True)
    async def removemoney(self, interaction: discord.Interaction, member: discord.Member, amount: int):

        if amount <= 0:
            return await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)

        await self.db_execute("""
            UPDATE users
            SET balance = GREATEST(balance - $1, 0)
            WHERE user_id = $2
        """, amount, member.id)

        await interaction.response.send_message(f"❌ Removed {amount:,} coins.")
        await self.log("Money Removed", f"{interaction.user} removed {amount:,} from {member}")

    # -----------------------------
    # DEPOSIT
    # -----------------------------
    @app_commands.command(name="deposit")
    async def deposit(self, interaction: discord.Interaction, amount: int):

        if amount <= 0:
            return await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)

        user = await self.get_user(interaction.user.id)

        if user["balance"] < amount:
            return await interaction.response.send_message("❌ Not enough money.", ephemeral=True)

        await self.db_execute("""
            UPDATE users
            SET balance = balance - $1,
                bank = bank + $1
            WHERE user_id = $2
        """, amount, interaction.user.id)

        await interaction.response.send_message(f"🏦 Deposited {amount:,} coins.")

    # -----------------------------
    # WITHDRAW
    # -----------------------------
    @app_commands.command(name="withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: int):

        if amount <= 0:
            return await interaction.response.send_message("❌ Invalid amount.", ephemeral=True)

        user = await self.get_user(interaction.user.id)

        if user["bank"] < amount:
            return await interaction.response.send_message("❌ Not enough bank money.", ephemeral=True)

        await self.db_execute("""
            UPDATE users
            SET bank = bank - $1,
                balance = balance + $1
            WHERE user_id = $2
        """, amount, interaction.user.id)

        await interaction.response.send_message(f"💵 Withdrew {amount:,} coins.")

    # -----------------------------
    # ROB (ANTI-EXPLOIT)
    # -----------------------------
    @app_commands.command(name="rob")
    async def rob(self, interaction: discord.Interaction, member: discord.Member):

        if member.id == interaction.user.id:
            return await interaction.response.send_message("❌ You cannot rob yourself.")

        async with self.pool.acquire() as conn:

            user = await conn.fetchrow("SELECT last_rob FROM users WHERE user_id=$1", interaction.user.id)

            last = user["last_rob"] if user else 0
            if self.now() - last < 60:
                return await interaction.response.send_message("⏳ Cooldown active.", ephemeral=True)

            await conn.execute("""
                UPDATE users SET last_rob=$1 WHERE user_id=$2
            """, self.now(), interaction.user.id)

            target = await conn.fetchrow("SELECT balance FROM users WHERE user_id=$1", member.id)

            if not target or target["balance"] < 100:
                return await interaction.response.send_message("❌ Target too poor.")

            chance = random.randint(1, 100)

            if chance <= 55:
                steal = random.randint(50, min(300, target["balance"]))

                async with conn.transaction():
                    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id=$2", steal, interaction.user.id)
                    await conn.execute("UPDATE users SET balance = balance - $1 WHERE user_id=$2", steal, member.id)

                return await interaction.response.send_message(f"🟢 Stole {steal:,} coins!")

            else:
                fine = random.randint(50, 200)
                await conn.execute("UPDATE users SET balance = GREATEST(balance - $1, 0) WHERE user_id=$2", fine, interaction.user.id)

                return await interaction.response.send_message(f"🔴 Failed and lost {fine:,}")

    # -----------------------------
    # CRIME (ANTI-EXPLOIT)
    # -----------------------------
    @app_commands.command(name="crime")
    async def crime(self, interaction: discord.Interaction):

        async with self.pool.acquire() as conn:

            user = await conn.fetchrow("SELECT last_crime FROM users WHERE user_id=$1", interaction.user.id)

            last = user["last_crime"] if user else 0
            if self.now() - last < 30:
                return await interaction.response.send_message("⏳ Cooldown active.", ephemeral=True)

            await conn.execute("""
                UPDATE users SET last_crime=$1 WHERE user_id=$2
            """, self.now(), interaction.user.id)

            roll = random.randint(1, 100)

            if roll <= 50:
                reward = random.randint(100, 500)
                await conn.execute("UPDATE users SET balance=balance+$1 WHERE user_id=$2", reward, interaction.user.id)
                return await interaction.response.send_message(f"💰 Earned {reward:,}")

            elif roll <= 80:
                return await interaction.response.send_message("🚨 Escaped")

            else:
                loss = random.randint(50, 300)
                await conn.execute("UPDATE users SET balance=GREATEST(balance-$1,0) WHERE user_id=$2", loss, interaction.user.id)
                return await interaction.response.send_message(f"🚔 Lost {loss:,}")

    # -----------------------------
    # SHOP
    # -----------------------------
    @app_commands.command(name="shop")
    async def shop(self, interaction: discord.Interaction):

        items = await self.db_fetch("SELECT item, price FROM shop")

        if not items:
            return await interaction.response.send_message("🛒 Empty shop")

        embed = discord.Embed(title="🛒 Shop", color=discord.Color.green())

        for i in items:
            embed.add_field(name=i["item"], value=f"{i['price']:,}", inline=False)

        await interaction.response.send_message(embed=embed)

    # -----------------------------
    # INVENTORY
    # -----------------------------
    @app_commands.command(name="inventory")
    async def inventory(self, interaction: discord.Interaction):

        items = await self.db_fetch("""
            SELECT item, quantity FROM inventory WHERE user_id=$1
        """, interaction.user.id)

        if not items:
            return await interaction.response.send_message("📦 Empty")

        embed = discord.Embed(title="📦 Inventory")

        for i in items:
            embed.add_field(name=i["item"], value=f"x{i['quantity']}")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))