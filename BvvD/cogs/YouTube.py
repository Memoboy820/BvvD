import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

RUS_CHANNEL_ID = "UCbLGQK0n8cA6oa-W50GTHyQ"
ENG_CHANNEL_ID = "UCPZsNertSS82YCT2qX9-wHA"


class YouTubeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.check_youtube.start()

    def cog_unload(self):
        self.check_youtube.cancel()

    def init_db(self):
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS youtube_settings (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            last_video_id TEXT
        )
        """)

        conn.commit()
        conn.close()

    @app_commands.command(
        name='setyoutubepings',
        description="Bot will make pings on new WT videos in the channel you've written this command"
    )
    async def setyoutubepings(self, interaction: discord.Interaction):
        view = YouTubeCog.ytView(interaction)
        embed = discord.Embed(
            title='Choose one of the WT YouTube channels:',
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    class ytButton(discord.ui.Button):
        def __init__(self, data):
            super().__init__(label=data, style=discord.ButtonStyle.primary)
            self.data = data

        async def callback(self, interaction: discord.Interaction):
            embed = discord.Embed(color=0xFFFFFF)

            conn = sqlite3.connect("bot.db")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO youtube_settings (guild_id, channel_id, language, last_video_id)
                VALUES (?, ?, ?, COALESCE(
                    (SELECT last_video_id FROM youtube_settings WHERE guild_id = ?),
                    NULL
                ))
            """, (interaction.guild_id, interaction.channel.id, self.data, interaction.guild_id))
            conn.commit()
            conn.close()

            embed.add_field(
                name='Done!',
                value=f'{interaction.channel.mention} is now set for **{self.data}** WarThunder YouTube'
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    class ytView(discord.ui.View):
        def __init__(self, interaction: discord.Interaction):
            super().__init__()
            langs = ['Russian', 'English']
            self.time = interaction.created_at

            for lang in langs:
                self.add_item(YouTubeCog.ytButton(lang))

    @tasks.loop(minutes=5)
    async def check_youtube(self):
        url_eng = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&channelId={ENG_CHANNEL_ID}&order=date&type=video&maxResults=1&key={YOUTUBE_API_KEY}"
        )
        url_rus = (
            f"https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&channelId={RUS_CHANNEL_ID}&order=date&type=video&maxResults=1&key={YOUTUBE_API_KEY}"
        )

        av_url_eng = (
            f"https://www.googleapis.com/youtube/v3/channels"
            f"?part=snippet&id={ENG_CHANNEL_ID}&key={YOUTUBE_API_KEY}"
        )
        av_url_rus = (
            f"https://www.googleapis.com/youtube/v3/channels"
            f"?part=snippet&id={RUS_CHANNEL_ID}&key={YOUTUBE_API_KEY}"
        )

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute("SELECT guild_id, channel_id, language, last_video_id FROM youtube_settings")
        rows = cursor.fetchall()
        conn.close()

        for guild_id, channel_id, language, last_video_id in rows:
            if language == 'Russian':
                url_main = url_rus
                av_url = av_url_rus
            elif language == 'English':
                url_main = url_eng
                av_url = av_url_eng
            else:
                continue

            response1 = requests.get(av_url, timeout=10)
            data1 = response1.json()
            avatar_thumbs = data1["items"][0]["snippet"]["thumbnails"]
            avatar_url = avatar_thumbs["high"]["url"]

            response = requests.get(url_main, timeout=10)
            data = response.json()
            print(data)
            item = data['items'][0]

            current_video_id = item["id"]["videoId"]
            channel_title = item["snippet"]["channelTitle"]
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            live = item["snippet"]["liveBroadcastContent"]
            published_at = item["snippet"]["publishedAt"]

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
                conn2 = sqlite3.connect("bot.db")
                cursor2 = conn2.cursor()

                cursor2.execute("""
                UPDATE youtube_settings
                SET last_video_id = ?
                WHERE guild_id = ?
                """, (current_video_id, guild_id))

                conn2.commit()
                conn2.close()

                embed = discord.Embed(
                    title=channel_title,
                    description=description[:120] if description else None,
                    color=0xFFFFFF
                )

                if live != 'none':
                    embed.add_field(name='📹 LIVE', value="\u200b", inline=False)

                embed.set_thumbnail(url=avatar_url)
                embed.add_field(
                    name=title,
                    value=f'https://www.youtube.com/watch?v={current_video_id}',
                    inline=False
                )
                embed.set_image(url=thumb_url)
                embed.set_footer(
                    text=f'📍New video provided by BvvD bot | Published at {published_at} ⏰'
                )

                channel = self.bot.get_channel(channel_id)
                if channel is not None:
                    await channel.send(embed=embed)

    @check_youtube.before_loop
    async def before_check_youtube(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(YouTubeCog(bot))