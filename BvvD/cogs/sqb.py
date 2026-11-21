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
    async def sqb_info(self, interaction: discord.Interaction, tag: str):
        embed = build_embed(tag)
        num = 1

#------------------------------------

        url = "https://war-thunder-api.onrender.com/sqb_team/nashi"

        logging.warning("API_TEST: начинаю запрос %s", url)
        
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=20.0),
            ) as client:
                response = await client.get(url)
        
                logging.warning(
                    "API_TEST: статус=%s, тело=%r",
                    response.status_code,
                    response.text[:500],
                )
        
                response.raise_for_status()
        
        except Exception:
            logging.exception("API_TEST: запрос завершился ошибкой")
            raise

#---------------------------------------
            if data:
                for team in data:
                    num += 1
                    embed.add_field(name=f"Команда - {num}", value=format_team(team), inline=False)

            else: 
                embed.description = "Состав не найден"

            

        await interaction.response.send_message(embed=embed)

sqbCog.sqb_info.error(kd_error)

async def setup(bot):
    await bot.add_cog(sqbCog(bot))
