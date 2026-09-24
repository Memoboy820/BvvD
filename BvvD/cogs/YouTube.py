import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


async def kd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            "10 second command cooldown",
            ephemeral=True
        )



class YouTubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.check_youtube.start()

    def cog_unload(self):
        self.check_youtube.cancel()

    def init_db(self):
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/database.db", timeout=10)
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS youtube_settings (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                last_video_id TEXT,
                role_id INTEGER,
                PRIMARY KEY (guild_id, language)
            )
            """)

            conn.commit()
        finally:
            conn.close()

    @app_commands.command(name='setyoutubepings', description="Bot will make pings on new WT videos in the channel you've written this command")
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def setyoutubepings(self, interaction: discord.Interaction, role: discord.Role):

        view = YouTubeCog.ytView(interaction, role)
        embed = discord.Embed(
            title='YouTube Pings / Пинги Ютуба',
            description=':flag_us: Choose one of the WT YouTube languages for this channel: \n:flag_ru: Выберите язык Ютуб канала ВарТандера для этого канала:',
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    class ytButton(discord.ui.Button):
        def __init__(self, data):
            super().__init__(label=data, style=discord.ButtonStyle.primary)
            self.data = data

        async def callback(self, interaction: discord.Interaction):
            for item in self.view.children:
                item.disabled = True
            await interaction.response.edit_message(view=self.view)


            embed = discord.Embed(color=0xFFFFFF)

            conn = sqlite3.connect("/app/data/database.db", timeout=10)
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO youtube_settings (guild_id, channel_id, language, last_video_id, role_id)
                    VALUES (?, ?, ?, COALESCE(
                        (SELECT last_video_id FROM youtube_settings 
                        WHERE guild_id = ? AND language = ?
                        ), NULL
                    ), ?)
                """, (interaction.guild_id, interaction.channel.id, self.data, interaction.guild_id, self.data, self.view.role_id))
                conn.commit()
            finally:
                conn.close()

            embed.add_field(
                name='Done!',
                value=f'{interaction.channel.mention} is now **set** for **{self.data}** WarThunder YouTube, and will ping members with {self.view.role} role'
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    class ytView(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, role: discord.Role):
            super().__init__()
            langs = ['Russian', 'English']
            self.time = interaction.created_at
            self.role = role
            self.role_id = role.id

            for lang in langs:
                self.add_item(YouTubeCog.ytButton(lang))

    
    @app_commands.command(name='removeyoutubepings', description='Bot will stop making pings on new WT videos in the channel command was written in')
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def removeyoutubepings(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        conn = sqlite3.connect("/app/data/database.db", timeout=10)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT channel_id FROM youtube_settings
                WHERE guild_id = ?;
                """,(guild_id,))
            rows = cursor.fetchall()
            channel_ids = [row[0] for row in rows]

            if channel_id in channel_ids:
                embed1 = discord.Embed(
                    title=f'**Removed all** YouTube pings from <#{channel_id}>',
                    color=0xFFFFFF
                )
                cursor.execute("""
                    DELETE FROM youtube_settings
                    WHERE guild_id = ? AND channel_id = ?
                    """,(guild_id, channel_id))
                await interaction.response.send_message(embed=embed1, ephemeral=True)
            else:
                embed1 = discord.Embed(
                    title='This channel is **not** set for any **YouTube** pings',
                    color=0xFFFFFF
                )
                await interaction.response.send_message(embed=embed1, ephemeral=True)




            conn.commit()
        finally:
            conn.close()




@tasks.loop(minutes=1)
async def check_youtube(self):
    # -- нужное
    RUS_UPL_ID = "UUbLGQK0n8cA6oa-W50GTHyQ"
    ENG_UPL_ID = "UUPZsNertSS82YCT2qX9-wHA"

    RUS_CHANNEL_ID = "UCbLGQK0n8cA6oa-W50GTHyQ"
    ENG_CHANNEL_ID = "UCPZsNertSS82YCT2qX9-wHA"

    url_eng = (
        f"https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet&playlistId={ENG_UPL_ID}&maxResults=1&key={YOUTUBE_API_KEY}"
    )
    url_rus = (
        f"https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet&playlistId={RUS_UPL_ID}&maxResults=1&key={YOUTUBE_API_KEY}"
    )

    av_url_eng = (
        f"https://www.googleapis.com/youtube/v3/channels"
        f"?part=snippet&id={ENG_CHANNEL_ID}&key={YOUTUBE_API_KEY}"
    )
    av_url_rus = (
        f"https://www.googleapis.com/youtube/v3/channels"
        f"?part=snippet&id={RUS_CHANNEL_ID}&key={YOUTUBE_API_KEY}"
    )
# -- все запросы
    conn = sqlite3.connect("/app/data/database.db", timeout=10)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT guild_id, channel_id, language, last_video_id, role_id FROM youtube_settings")
        rows = cursor.fetchall()
    finally:
        conn.close()

    response1_eng = requests.get(av_url_eng, timeout=10)
    response1_eng.raise_for_status()
    data1_eng = response1_eng.json()
    avatar_thumbs_eng = data1_eng["items"][0]["snippet"]["thumbnails"]
    avatar_url_eng = avatar_thumbs_eng["high"]["url"]

    response_eng = requests.get(url_eng, timeout=10)
    response_eng.raise_for_status()
    data_eng = response_eng.json()
    item_eng = data_eng["items"][0]

    thumbs_eng = item_eng["snippet"]["thumbnails"]
    if "maxres" in thumbs_eng:
        thumb_url_eng = thumbs_eng["maxres"]["url"]
    elif "standard" in thumbs_eng:
        thumb_url_eng = thumbs_eng["standard"]["url"]
    elif "high" in thumbs_eng:
        thumb_url_eng = thumbs_eng["high"]["url"]
    elif "medium" in thumbs_eng:
        thumb_url_eng = thumbs_eng["medium"]["url"]
    else:
        thumb_url_eng = thumbs_eng["default"]["url"]

    response1_rus = requests.get(av_url_rus, timeout=10)
    response1_rus.raise_for_status()
    data1_rus = response1_rus.json()
    avatar_thumbs_rus = data1_rus["items"][0]["snippet"]["thumbnails"]
    avatar_url_rus = avatar_thumbs_rus["high"]["url"]

    response_rus = requests.get(url_rus, timeout=10)
    response_rus.raise_for_status()
    data_rus = response_rus.json()
    item_rus = data_rus["items"][0]

    thumbs_rus = item_rus["snippet"]["thumbnails"]
    if "maxres" in thumbs_rus:
        thumb_url_rus = thumbs_rus["maxres"]["url"]
    elif "standard" in thumbs_rus:
        thumb_url_rus = thumbs_rus["standard"]["url"]
    elif "high" in thumbs_rus:
        thumb_url_rus = thumbs_rus["high"]["url"]
    elif "medium" in thumbs_rus:
        thumb_url_rus = thumbs_rus["medium"]["url"]
    else:
        thumb_url_rus = thumbs_rus["default"]["url"]
# -- рассылка
    for guild_id, channel_id, language, last_video_id, role_id in rows:
        try:
            if language == 'Russian':
                item = item_rus
                avatar_url = avatar_url_rus
                thumb_url = thumb_url_rus
            elif language == 'English':
                item = item_eng
                avatar_url = avatar_url_eng
                thumb_url = thumb_url_eng
            else:
                continue

            current_video_id = item["snippet"]["resourceId"]["videoId"]
            channel_title = item["snippet"]["channelTitle"]
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            live = item["snippet"].get("liveBroadcastContent", "none")
            published_at = item["snippet"]["publishedAt"]

# -- создание ембеда
            if current_video_id != last_video_id:
                conn2 = sqlite3.connect("/app/data/database.db", timeout=10)
                cursor2 = conn2.cursor()

                try:
                    cursor2.execute("""
                    UPDATE youtube_settings
                    SET last_video_id = ?
                    WHERE guild_id = ? AND language = ?
                    """, (current_video_id, guild_id, language))

                    conn2.commit()
                finally:
                    conn2.close()

                embed = discord.Embed(
                    title=title,
                    url=f'https://www.youtube.com/watch?v={current_video_id}',
                    color=0xFFFFFF
                )

                if live != 'none':
                    embed.add_field(name='📹 LIVE', value="\u200b", inline=False)

                embed.set_thumbnail(url=avatar_url)
                embed.add_field(
                    name='Description:',
                    value=description[:120] if description else "\u200b",
                    inline=False
                )
                embed.set_image(url=thumb_url)
                embed.set_footer(
                    text=f'📍New video provided by BvvD bot'
                )
                embed.set_author(name=channel_title)

                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    await channel.send(content=f"<@&{role_id}>", embed=embed)

        except Exception as e:
            import traceback
            print(f"[check_youtube] guild={guild_id} language={language}")
            traceback.print_exc()

@check_youtube.before_loop
async def before_check_youtube(self):
    await self.bot.wait_until_ready()

YouTubeCog.setyoutubepings.error(kd_error)
YouTubeCog.removeyoutubepings.error(kd_error)

async def setup(bot):
    await bot.add_cog(YouTubeCog(bot))
