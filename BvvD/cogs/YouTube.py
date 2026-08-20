import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


class YouTubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.check_youtube.start()

    def cog_unload(self):
        self.check_youtube.cancel()

    def init_db(self):
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/database.db")
        cursor = conn.cursor()

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
        conn.close()

    @app_commands.command(name='setyoutubepings', description="Bot will make pings on new WT videos in the channel you've written this command")
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
            embed = discord.Embed(color=0xFFFFFF)

            conn = sqlite3.connect("/app/data/database.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO youtube_settings (guild_id, channel_id, language, last_video_id, role_id)
                VALUES (?, ?, ?, COALESCE(
                    (SELECT last_video_id FROM youtube_settings 
                    WHERE guild_id = ? AND language = ?
                    ), NULL
                ), ?)
            """, (interaction.guild_id, interaction.channel.id, self.data, interaction.guild_id, self.data, self.view.role_id))
            conn.commit()
            conn.close()

            embed.add_field(
                name='Done!',
                value=f'{interaction.channel.mention} is now **set** for **{self.data}** WarThunder YouTube, and will ping members with {self.view.role} role'
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

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
    async def removeyoutubepings(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        channel_id = interaction.channel.id
        conn = sqlite3.connect("/app/data/database.db")
        cursor = conn.cursor()

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
        conn.close()







    

    @tasks.loop(minutes=1)
    async def check_youtube(self):

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

            conn = sqlite3.connect("/app/data/database.db")
            cursor = conn.cursor()

            cursor.execute("SELECT guild_id, channel_id, language, last_video_id, role_id FROM youtube_settings")
            rows = cursor.fetchall()
            conn.close()

            for guild_id, channel_id, language, last_video_id, role_id in rows:
                try:
                    if language == 'Russian':
                        url_main = url_rus
                        av_url = av_url_rus
                    elif language == 'English':
                        url_main = url_eng
                        av_url = av_url_eng
                    else:
                        continue
                        
                    response1 = requests.get(av_url, timeout=10)
                    response1.raise_for_status()
                    data1 = response1.json()
                    avatar_thumbs = data1["items"][0]["snippet"]["thumbnails"]
                    avatar_url = avatar_thumbs["high"]["url"]

                    response = requests.get(url_main, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    item = data['items'][0]

                    current_video_id = item["snippet"]["resourceId"]["videoId"]
                    channel_title = item["snippet"]["channelTitle"]
                    title = item["snippet"]["title"]
                    description = item["snippet"]["description"]
                    live = item["snippet"].get("liveBroadcastContent", "none")
                    published_at = item["snippet"]["publishedAt"]

                    print(f"[YT] guild={guild_id} language={language} last={last_video_id} current={current_video_id}")

                    thumbs = item["snippet"]["thumbnails"]
                    if "maxres" in thumbs:
                        thumb_url = thumbs["maxres"]["url"]
                    elif "standard" in thumbs:
                        thumb_url = thumbs["standard"]["url"]
                    elif "high" in thumbs:
                        thumb_url = thumbs["high"]["url"]
                    elif "medium" in thumbs:
                        thumb_url = thumbs["medium"]["url"]
                    else:
                        thumb_url = thumbs["default"]["url"]

                    if current_video_id != last_video_id:
                        conn2 = sqlite3.connect("/app/data/database.db")
                        cursor2 = conn2.cursor()

                        cursor2.execute("""
                        UPDATE youtube_settings
                        SET last_video_id = ?
                        WHERE guild_id = ? AND language = ?
                        """, (current_video_id, guild_id, language))

                        conn2.commit()
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



async def setup(bot):
    await bot.add_cog(YouTubeCog(bot))
