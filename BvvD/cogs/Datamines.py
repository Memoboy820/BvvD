from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
from google import genai
import os
import discord
import requests
import sqlite3


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
                    8. Do not output JSON.
                    9. Do not use emoji.
                    10. Do not use a Markdown title with #.
                    11. Return only the final Discord text. No explanations before
                        or after it.

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
                    - Maximum total length: 3500 characters.
                    - Maximum 8 sections.
                    - Maximum 5 bullet points per section.
                    - Use short bullet points.
                    - Do not show raw file paths unless the object name cannot be determined.
                    - Do not show raw .blkx syntax if it can be simplified.
                    - Preserve exact old and new values whenever they are available.
                    - If an object was added, write: "Added: Object name".
                    - If an object was removed, write: "Removed: Object name".
                    - If no player-relevant changes are present, return exactly:
                    No player-relevant datamine changes detected.

                    Always end with exactly this line:

                    Datamine information from client files. Not an official announcement.
                    """

AI_API_KEY = os.getenv("AI_API_KEY")

DATAMINE_REPO = "gszabi99/War-Thunder-Datamine"

GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2026-03-10",
    "User-Agent": "BvvD-Datamine-Tracker",
}



ai_client = genai.Client(
    api_key=AI_API_KEY
)

def short_file_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]



def get_compare_data(old_sha: str, new_sha: str) -> dict:
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
        conn = sqlite3.connect("/app/data/datamines.db")

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS datamines_settings (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            last_datamine_sha TEXT,
            previous_datamine_sha TEXT,
            PRIMARY KEY (guild_id, channel_id)
            )
        """)
        conn.commit()
        conn.close()

#---------------------- КОММАНДЫ 
#-- добавление

    @app_commands.command(name='setdataminespings', description="Sets pings for changes in game's files")
    async def setdataminepings(self, interaction: discord.Interaction, role: discord.Role):
        role_id = role.id
        channel_id = interaction.channel.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect("/app/data/datamines.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO datamines_settings (guild_id, channel_id, role_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                role_id = excluded.role_id
        """, (guild_id, channel_id, role_id))
        conn.commit()
        conn.close()

        embed = discord.Embed(color=0xFFFFFF)
        embed.add_field(
            name='Done!',
            value=f"{interaction.channel.mention} is now **set** for WarThunder datamines, and will ping members on changes in game's files with {role.mention} role")
        await interaction.response.send_message(embed=embed, ephemeral=True)



# -- удаление

    @app_commands.command(name='removedataminespings', description='Removes datamine pings from this channel')
    async def removedataminespings(self, interaction: discord.Interaction):
        conn = sqlite3.connect("/app/data/datamines.db")
        cursor = conn.cursor()
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
        conn.close()


#----------------------- поиск 


    @tasks.loop(minutes=10)
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
            date = data["commit"]["author"]["date"]
            html_url = data["html_url"]
            parent_sha = data["parents"][0]["sha"]

# -- сверка

            conn = sqlite3.connect("/app/data/datamines.db")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT guild_id, channel_id, role_id, last_datamine_sha, previous_datamine_sha
                FROM datamines_settings
            """)
            rows = cursor.fetchall()
            conn.close()

            for guild_id, channel_id, role_id, last_datamine_sha, previous_datamine_sha in rows:

                if last_datamine_sha is None:  # первый запуск

                    conn = sqlite3.connect("/app/data/datamines.db")
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE datamines_settings
                        SET last_datamine_sha = ?
                        WHERE guild_id = ? AND channel_id = ?
                    """, (sha, guild_id, channel_id))

                    conn.commit()
                    conn.close()
                    continue


                #if last_datamine_sha == sha:
                    #continue             # ес ниче не изменилось - едем дальше
                
## -- запрос на разницу прошлой и новой версии

                compare_data = get_compare_data(parent_sha, sha)
                changed_files = compare_data["files"]

## -- запрос на прогон и фильтрацию инфы через ии
                print('[AI] отправляем запрос')
                response = ai_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f'{prompt}\nRaw Datamine Changes:\n{changed_files}'
                )
                ai_text = response.text

                print(ai_text[:3800])
                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    await channel.send(content=ai_text[:3800])

# -- отправка



        except requests.RequestException as e:
            print(f"Ошибка запроса: {e}")
        except Exception as e:
            print(e)

    @datamines_checker.before_loop
    async def before_check_datamines(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DataminesCog(bot))
