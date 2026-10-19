from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
from google import genai
import os
import discord
import requests
import sqlite3
import  json
import asyncio
import httpx

load_dotenv()

#--------------- функции и нужное

prompt = os.getenv("PROMPT")

AI_API_KEY = os.getenv("AI_API_KEY")

DATAMINE_REPO = "gszabi99/War-Thunder-Datamine"

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2026-03-10",
    "User-Agent": "BvvD-Datamine-Tracker",
}

models = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it"
)


ai_client = genai.Client(
    api_key=AI_API_KEY
)

def short_file_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]

def get_ai_response(prompt: str, changed_files: str):
    for model in models:
        try:
            response = ai_client.models.generate_content(
            model=model,
            contents=f'{prompt}\nRaw Datamine Changes:\n{changed_files}',
            config={"response_mime_type": "application/json"}
        )
            ai_text_list = json.loads(response.text)
            return ai_text_list
        except Exception as e:
            print(f'{model} - {str(e)[:100]}')
    return None


async def kd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            "10 second command cooldown",
            ephemeral=True
        )


async def get_compare_data(old_sha: str, new_sha: str) -> dict:       #сравнение гитов
    url = (
        f"https://api.github.com/repos/{DATAMINE_REPO}/compare/"
        f"{old_sha}...{new_sha}"
    )
    async with httpx.AsyncClient(
        headers=GITHUB_HEADERS,
        timeout=30,
        follow_redirects=True
    ) as client:

        response = await client.get(url)
        response.raise_for_status()
        return response.json()

def insert_sql(interaction: discord.Interaction, role_id: int):
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO datamines_settings (guild_id, channel_id, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                role_id = excluded.role_id
        """, (interaction.guild.id, interaction.channel.id, role_id))
        conn.commit()
    finally:
        conn.close()


def get_channel_ids(interaction: discord.Interaction):
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT channel_id FROM datamines_settings
            WHERE guild_id = ?;
        """, (interaction.guild.id,))
        rows = cursor.fetchall()
        channel_ids = [row[0] for row in rows]
        return channel_ids
    finally:
        conn.close()



def delete_sql(interaction: discord.Interaction):
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM datamines_settings
            WHERE channel_id = ?;
        """, (interaction.channel.id,))
        conn.commit()
    finally:
        conn.close()



def get_sql_data():
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT guild_id, channel_id, role_id, last_datamine_sha
            FROM datamines_settings
        """)
        rows = cursor.fetchall()
        return rows
    finally:
        conn.close()


def update_sha_sql(sha):
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE datamines_settings
            SET last_datamine_sha = ?
        """, (sha,))

        conn.commit()
    finally:
        conn.close()



def update_sql(sha, guild_id, channel_id):
    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE datamines_settings
            SET last_datamine_sha = ?
            WHERE guild_id = ? AND channel_id = ?
        """, (sha, guild_id, channel_id))

        conn.commit()
    finally:
        conn.close()

#--------------------- ПОДГОТОВКА

class DataminesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.datamines_checker.start()

    def cog_unload(self):
        self.datamines_checker.cancel()

    def init_db(self):
        
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/datamines.db", timeout=10)

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datamines_settings (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            last_datamine_sha TEXT,
            previous_datamine_sha TEXT,
            PRIMARY KEY (guild_id)
            )
        """)
        conn.commit()
        conn.close()

#---------------------- КОМАНДЫ 
#-- добавление

    @app_commands.command(name='setdataminespings', description="Sets pings for changes in game's files")
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def setdataminepings(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            role_id = role.id

            await asyncio.to_thread(insert_sql, interaction=interaction, role_id=role_id)

            embed = discord.Embed(color=0xFFFFFF)
            embed.add_field(
                name='Done!',
                value=f"{interaction.channel.mention} is now **set** for WarThunder datamines, and will ping members on changes in game's files with {role.mention} role")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f'SetDTMNSPings: {e}')
            await interaction.followup.send("Не удалось сохранить изменения | Couldn't save the changes", ephemeral=True)



# -- удаление

    @app_commands.command(name='removedataminespings', description='Removes datamine pings from this channel')
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def removedataminespings(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            channel_ids = await asyncio.to_thread(get_channel_ids, interaction=interaction)

            if interaction.channel.id in channel_ids:
                await asyncio.to_thread(delete_sql, interaction=interaction)
                embed1 = discord.Embed(
                    title=f'**Removed all** Datamines pings from <#{interaction.channel.id}>',
                    color=0xFFFFFF
                )
                await interaction.followup.send(embed=embed1, ephemeral=True)
            else:
                embed2 = discord.Embed(
                    title='This channel is **not** set for any **Datamines** pings',
                    color=0xFFFFFF
                )
                await interaction.followup.send(embed=embed2, ephemeral=True)
        except Exception as e:
            print(f'RemoveDTMNS: {e}')
            await interaction.followup.send("Не удалось сохранить изменения | Couldn't save the changes", ephemeral=True)


#----------------------- поиск 


    @tasks.loop(minutes=15)
    async def datamines_checker(self):
        try:

# -- первичный запрос
            URL = (
                "https://api.github.com/repos/"
                "gszabi99/War-Thunder-Datamine/commits/master" # big thanks to gszabi
            )
            
            response = await asyncio.to_thread(
                httpx.get,
                URL,
                timeout=20,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
                follow_redirects=True
            )
            response.raise_for_status()
            data = response.json()

            sha = data["sha"]
            message = data["commit"]["message"]



# -- сверка
            rows = await asyncio.to_thread(get_sql_data)

            if not rows:    # на присутствие  
                return

            
            if rows[0][3] is None:                  # на ша
                await asyncio.to_thread(update_sha_sql, sha=sha)
                return

            
            if rows[0][3] == sha: # на новую версию
                return 

            for guild_id, channel_id, role_id, last_datamine_sha in rows:
                
                if last_datamine_sha is None:  # первый запуск
                    await asyncio.to_thread(update_sql, sha=sha, guild_id=guild_id, channel_id=channel_id)
                    continue
                
## -- запрос на разницу прошлой и новой версии

            compare_data = await get_compare_data(last_datamine_sha, sha)
            if compare_data == None:
                return
            changed_files = compare_data["files"]

## -- запрос на прогон и фильтрацию инфы через ии

            ai_text_list = await asyncio.to_thread(get_ai_response, prompt, changed_files)
            if ai_text_list is None:
                return

# -- отправка
            for guild_id, channel_id, role_id, last_datamine_sha in rows:
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    try:
                        if 'No player-relevant datamine changes detected.' not in ai_text_list:
                            await channel.send(content=f'<@&{role_id}>')
                        await channel.send(content=f'# {message}:')
                        for text in ai_text_list:
                            await channel.send(content=f"{text[:1950]}")
                        await channel.send(content=f"**Data sourced from gszabi99's War Thunder Datamine repository** \n*📍Provided by BvvD bot*")
                        await asyncio.to_thread(update_sql, sha=sha, guild_id=guild_id, channel_id=channel_id)
                    except Exception as e:
                        print(f'[SEND] - {e}')

        except httpx.HTTPError as e:
            print(f"Ошибка запроса: {e}")
        except Exception as e:
            print(e)

    @datamines_checker.before_loop
    async def before_check_datamines(self):
        await self.bot.wait_until_ready()

DataminesCog.setdataminepings.error(kd_error)
DataminesCog.removedataminespings.error(kd_error)

async def setup(bot):
    await bot.add_cog(DataminesCog(bot))
