import re
import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import requests
import json

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True

class MyTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cannot be used in DMs",
                ephemeral=True
            )
            return False

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Administrator only command",
                ephemeral=True
            )
            return False
        return True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    case_insensitive=True,
    tree_cls=MyTree,
    allowed_mentions=discord.AllowedMentions(
        roles=True,
        users=True,
        replied_user=True
    ),
)

async def setup_hook():
    await bot.load_extension("cogs.YouTube")
    await bot.load_extension("cogs.News")
    await bot.load_extension("cogs.Checker")

    guild = discord.Object(id=GUILD_ID)

    global_synced = await bot.tree.sync()
    print("Global:", [cmd.name for cmd in global_synced])

    bot.tree.copy_global_to(guild=guild)
    guild_synced = await bot.tree.sync(guild=guild)
    print("Guild:", [cmd.name for cmd in guild_synced])

bot.setup_hook = setup_hook








@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    for guild in bot.guilds:
        print(guild.name, guild.id)


bot.run(TOKEN)
