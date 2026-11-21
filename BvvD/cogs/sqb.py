import httpx
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os

load_dotenv()

api_base_url = os.getenv("BASE_API_URL")

async def kd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            "10 second command cooldown",
            ephemeral=True
        )

def build_embed(tag: str):
    embed = discord.Embed(
        title=f"Комманды полка {tag}",
        description="Результат может быть старым"
    )
    return embed


def format_team(team: dict) -> str:
    players = team["player_vehicle"]
    width = max((len(player) for player in players), default=0)

    lines = [
        f"{player:<{width}} → {vehicle}"
        for player, vehicle in players.items()
    ]

    return "```\n" + "\n".join(lines) + "\n```"


class sqbCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="sqb_team", description="[BETA] get info on sqb teams by their tag")
    async def sqb_info(self, tag: str):
        embed = build_embed(tag)
        async with httpx.AsyncClient(
            base_url=api_base_url
        ) as client:
            response = await client.get(api_base_url + f"/sqb_team/{tag}")
            data = response.json()

            for team in data:
                current_team = []
                team = 1
                for player, vehicle in team["player_vehicle"].items():
                    current_team.append((player, vehicle))
                embed.add_field(name=f"Команда - {team}", value=format_team(data))

sqbCog.sqb_info.error(kd_error)

async def setup(bot):
    await bot.add_cog(sqbCog(bot))
