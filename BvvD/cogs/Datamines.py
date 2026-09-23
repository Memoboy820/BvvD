from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
from google import genai
import os
import discord
import requests
import sqlite3
import  json


load_dotenv()

#--------------- функции и нужное

prompt = """
                    You are a neutral War Thunder datamine formatter.

                    Your task is to turn raw GitHub datamine changes into one short,
                    ready-to-send Discord update.

                    IMPORTANT RULES:

                    1. Use only facts explicitly present in the provided data.
                    2. Do not use outside knowledge about War Thunder.
                    3. Do not invent missing values, vehicle names, weapon names,
                    gameplay effects, dates, or conclusions.
                    4. Do not say that a change is a buff, nerf, improvement,
                    deterioration, balance change, or meta change.
                    5. Do not claim that changes are already active on the live server.
                    6. Do not make predictions.
                    7. Do not mention that you are an AI.
                    9. Do not use emoji.
                    10. Do not use a Markdown title with #.
                    11. Return only the final Discord text. No explanations before or after it.
                    11. Never alter, round, calculate, reinterpret, or normalize a numeric value.
                    12. Copy every number, unit, identifier, and old → new value exactly as written in the raw data.
                    13. If a value is unclear, malformed, or cannot be copied exactly, omit that specific field.
                    14. Do not replace 3.0 with 0.3, 0.0, 3, or any other representation unless the raw data explicitly contains that value.
                    15. Do not merge values from different files or objects.

                    IGNORE completely:

                    - localization files;
                    - language files;
                    - sound files;
                    - texture files;
                    - GUI and interface files;
                    - visual effects;
                    - unrelated technical files;
                    - Git line positions such as @@ -15,7 +15,7 @@;
                    - Git metadata such as file SHA, additions, deletions and changes count.

                    PRIORITIZE:

                    - aircraft;
                    - ground vehicles;
                    - helicopters;
                    - naval vehicles;
                    - weapons;
                    - missiles;
                    - bombs;
                    - shells;
                    - rockets;
                    - radar;
                    - RWR;
                    - flight models;
                    - battle rating;
                    - economy;
                    - research cost;
                    - Silver Lions;
                    - Golden Eagles;
                    - vehicle rank;
                    - modifications;
                    - loadouts;
                    - vehicle additions;
                    - vehicle removals.

                    OUTPUT FORMAT:

                    Split the following text into a list of strings for sending with a Discord bot.

                    Requirements:
                    - Return only a valid JSON array of strings, with no Markdown, explanations, or ```json code fences.
                    - Each array element must be a complete, standalone Discord message ready to pass directly to channel.send(...).
                    - Each fragment must be no more than 1900 characters long, including spaces and line breaks.
                    - Prefer splitting at paragraph boundaries.
                    - If a paragraph does not fit, split it at sentence boundaries.
                    - If a sentence exceeds the limit, split it at word boundaries.
                    - Do not leave empty strings as separate array elements.
                    - Avoid splitting Markdown links, inline code enclosed in backticks, and lists whenever possible.
                    - Every fragment must be ready to pass directly to channel.send(...)

                    TEXT FORMAT:

                    Start directly with a concise summary sentence.

                    Then use short sections only when needed:

                    **Weapons**
                    • Object name — old value → new value

                    **Aircraft**
                    • Object name — old value → new value

                    **Ground vehicles**
                    • Object name — old value → new value

                    **Economy / Battle Rating**
                    • Object name — old value → new value

                    Requirements:

                    - Use English.
                    - Return no more than 5 array elements.
                    - Use short bullet points.
                    - Do not show raw file paths unless the object name cannot be determined.
                    - Do not show raw .blkx syntax if it can be simplified.
                    - Preserve exact old and new values whenever they are available.
                    - If an object was added, write: "Added: Object name".
                    - If an object was removed, write: "Removed: Object name".
                    - If no player-relevant changes are present, return exactly:
                    No player-relevant datamine changes detected.

                    Always end with exactly this line only in the last text fragment:

                    Datamine information from client files. Not an official announcement.
                    """

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
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2-flash"
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
            print(f'{model} - {e}')
    return None


async def kd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            "10 second command cooldown",
            ephemeral=True
        )


def get_compare_data(old_sha: str, new_sha: str) -> dict:       #сравнение гитов
    url = (
        f"https://api.github.com/repos/{DATAMINE_REPO}/compare/"
        f"{old_sha}...{new_sha}"
    )

    response = requests.get(
        url,
        headers=GITHUB_HEADERS,
        timeout=30
    )

    response.raise_for_status()
    return response.json()

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
        role_id = role.id
        channel_id = interaction.channel.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO datamines_settings (guild_id, channel_id, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id = excluded.channel_id,
                    role_id = excluded.role_id
            """, (guild_id, channel_id, role_id))
            conn.commit()
        finally:
            conn.close()

        embed = discord.Embed(color=0xFFFFFF)
        embed.add_field(
            name='Done!',
            value=f"{interaction.channel.mention} is now **set** for WarThunder datamines, and will ping members on changes in game's files with {role.mention} role")
        await interaction.response.send_message(embed=embed, ephemeral=True)



# -- удаление

    @app_commands.command(name='removedataminespings', description='Removes datamine pings from this channel')
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def removedataminespings(self, interaction: discord.Interaction):
        conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT channel_id FROM datamines_settings
                WHERE guild_id = ?;
            """, (interaction.guild.id,))
            rows = cursor.fetchall()
            channel_ids = [row[0] for row in rows]

            if interaction.channel.id in channel_ids:
                cursor.execute("""
                    DELETE FROM datamines_settings
                    WHERE channel_id = ?;
                """, (interaction.channel.id,))

                embed1 = discord.Embed(
                    title=f'**Removed all** Datamines pings from <#{interaction.channel.id}>',
                    color=0xFFFFFF
                )
                await interaction.response.send_message(embed=embed1, ephemeral=True)
            else:
                embed2 = discord.Embed(
                    title='This channel is **not** set for any **Datamines** pings',
                    color=0xFFFFFF
                )
                await interaction.response.send_message(embed=embed2, ephemeral=True)
            conn.commit()
        finally:
            conn.close()


#----------------------- поиск 


    @tasks.loop(minutes=15)
    async def datamines_checker(self):
        try:

# -- первичный запрос
            URL = (
                "https://api.github.com/repos/"
                "gszabi99/War-Thunder-Datamine/commits/master" # big thanks to gszabi
            )
            
            response = requests.get(
                URL,
                timeout=20,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                }
            )
            response.raise_for_status()
            data = response.json()

            sha = data["sha"]
            message = data["commit"]["message"]
            author = data["commit"]["author"]["name"]
            date = data["commit"]["author"]["date"] #для будущих обновлений
            html_url = data["html_url"]


# -- сверка

            conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT guild_id, channel_id, role_id, last_datamine_sha
                FROM datamines_settings
            """)
            rows = cursor.fetchall()
            conn.close()

            if not rows:    # на присутствие  
                return

            
            if rows[0][3] is None:                  # на ша
                conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE datamines_settings
                    SET last_datamine_sha = ?
                """, (sha,))

                conn.commit()
                conn.close()
                return

            
            if rows[0][3] == sha: # на новую версию
                return 

            for guild_id, channel_id, role_id, last_datamine_sha in rows:

                if last_datamine_sha is None:  # первый запуск

                    conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE datamines_settings
                        SET last_datamine_sha = ?
                        WHERE guild_id = ? AND channel_id = ?
                    """, (sha, guild_id, channel_id))

                    conn.commit()
                    conn.close()
                    continue
                
## -- запрос на разницу прошлой и новой версии

            compare_data = get_compare_data(last_datamine_sha, sha)
            changed_files = compare_data["files"]

## -- запрос на прогон и фильтрацию инфы через ии

            ai_text_list = get_ai_response(prompt, changed_files)

# -- отправка
            for guild_id, channel_id, role_id, last_datamine_sha in rows:
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    try:
                        if 'No player-relevant datamine changes detected.' not in ai_text_list:
                            await channel.send(content=f'<@&{role_id}>')
                        for text in ai_text_list:
                            await channel.send(content=f"# {message}: \n{text[:1950]}")
                            await channel.send(content=f"**Data sourced from gszabi99's War Thunder Datamine repository** \n*📍Provided by BvvD bot*")
                    except Exception as e:
                        print(f'[SEND] - {e}')

# -- запись
                conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE datamines_settings
                    SET last_datamine_sha = ?
                    WHERE guild_id = ? AND channel_id = ?
""", (sha, guild_id, channel_id))
                conn.commit()
                conn.close()


        except requests.RequestException as e:
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
