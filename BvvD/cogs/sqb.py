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


    @app_commands.command(
    name="sqb_team",
    description="[BETA] get info on sqb teams by their tag",
)
    async def sqb_info(self, interaction: discord.Interaction, tag: str):
        print("SQB 1: вход в команду", flush=True)
    
        try:
            await interaction.response.defer(ephemeral=True)
            print("SQB 2: defer выполнен", flush=True)
    
            url = (
                "https://wtapi-production-5ad4c2b0.up.railway.app"
                f"/sqb_team/{tag}"
            )
            print("SQB 3: начинаю запрос", url, flush=True)
    
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
    
            print("SQB 4: статус", response.status_code, flush=True)
            print("SQB 5: тело", response.text[:1000], flush=True)
    
            response.raise_for_status()
            data = response.json()
    
            embed = build_embed(tag)
    
            if data:
                for num, team in enumerate(data, start=1):
                    embed.add_field(
                        name=f"Команда — {num}",
                        value=format_team(team),
                        inline=False,
                    )
            else:
                embed.description = "Состав не найден"
    
            print("SQB 6: отправляю embed", flush=True)
            await interaction.followup.send(embed=embed, ephemeral=True)
            print("SQB 7: ответ отправлен", flush=True)
    
        except Exception:
            import traceback
            traceback.print_exc()



async def setup(bot):
    await bot.add_cog(sqbCog(bot))
