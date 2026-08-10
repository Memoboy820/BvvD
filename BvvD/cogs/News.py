import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3
import re
import json

load_dotenv()

def bbcode_to_discord(text: str) -> str:
    text = text.replace('{STEAM_CLAN_IMAGE}', 'https://clan.akamai.steamstatic.com/images')
    text = re.sub(r'\[img\s+src="[^"]+"\]\[/img\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[h2\](.*?)\[/h2\]', r'\n## \1\n', text, flags=re.DOTALL)
    text = re.sub(r'\[b\](.*?)\[/b\]', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'\[quote\](.*?)\[/quote\]', lambda m: '\n' + '\n'.join(
        f'> {line}' for line in m.group(1).splitlines() if line.strip()
    ) + '\n', text, flags=re.DOTALL)
    text = re.sub(r'\[list\]', '\n', text)
    text = re.sub(r'\[/list\]', '\n', text)
    text = re.sub(r'\[/?table.*?\]', '\n', text)
    text = re.sub(r'\[/?tr.*?\]', '\n', text)
    text = re.sub(r'\[/?td.*?\]', '\n', text)
    text = re.sub(r'\[p.*?\]', '', text)
    text = re.sub(r'\[/p\]', '\n', text)
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'(\S)\|', r'\1 |', text)
    text = re.sub(r'\|(\S)', r'| \1', text)
    text = re.sub(r'\[(https?://[^\]]+)\]\(\1\)', r'\1', text)

    return text.strip()

class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.check_news.start()

    def cog_unload(self):
        self.check_news.cancel()

    def init_db(self):
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/databaseNews.db")

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_settings (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            last_news_id TEXT,
            language TEXT NOT NULL,
            PRIMARY KEY (guild_id, language)
            )
        """)

        conn.commit()
        conn.close()

    @app_commands.command(name='setnewspings', description='Sets channel for WT news')
    async def setnews(self, interaction: discord.Interaction, role: discord.Role):
        
        view = NewsCog.NewsView(interaction, role)
        embed = discord.Embed(
            title='Choose one of the WT News languages for this channel:',
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    class NewsButton(discord.ui.Button):
        def __init__(self, language: str):
            super().__init__(label=language)
            self.language = language

        async def callback(self, interaction):
            guild_id = interaction.guild.id
            channel_id = interaction.channel.id
            role_id = self.view.role_id
            language = self.language
            
            conn = sqlite3.connect("/app/data/databaseNews.db")
            cursor = conn.cursor()

            cursor.execute("""
        INSERT OR REPLACE INTO news_settings (guild_id, channel_id, role_id, language)
        VALUES (?, ?, ?, ?)
    """, (guild_id, channel_id, role_id, language))

            conn.commit()
            conn.close()

            embed = discord.Embed(color=0xFFFFFF)
            embed.add_field(name='Done!', value=f'{interaction.channel.mention} is now **set** for **{self.language}** WarThunder News, and will ping members with {self.view.role} role')
            await interaction.response.send_message(embed=embed, ephemeral=True)
                            
            


    class NewsView(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, role: discord.Role):
            super().__init__()
            self.interaction = interaction
            self.role = role.mention
            self.role_id = role.id

            self.add_item(NewsCog.NewsButton("Russian"))
            self.add_item(NewsCog.NewsButton("English"))









    @app_commands.command(name='removenewspings', description='Removes News pings from this channel')
    async def removenewspings(self, interaction: discord.Interaction):
        conn = sqlite3.connect("/app/data/databaseNews.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT channel_id FROM news_settings
            WHERE guild_id = ?;
    """,(interaction.guild.id,))
        rows = cursor.fetchall()
        channel_ids = [row[0] for row in rows]

        if interaction.channel.id in channel_ids:
            cursor.execute("""
                DELETE FROM news_settings
                WHERE channel_id = ?;
            """,(interaction.channel.id,))

            embed1 = discord.Embed(
                title=f'**Removed all** News pings from <#{interaction.channel.id}>',
                color=0xFFFFFF
            )
            await interaction.response.send_message(embed=embed1, ephemeral=True)
        else:
            embed2 = discord.Embed(
                title='This channel is **not** set for any **News** pings',
                color=0xFFFFFF
            )
            await interaction.response.send_message(embed=embed2, ephemeral=True)

        conn.commit()
        conn.close()









    @tasks.loop(minutes=1)
    async def check_news(self):

        RUS_URL = "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/?appid=236390&lang_list=8"
        ENG_URL = "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/?appid=236390&lang_list=0"

        conn = sqlite3.connect("/app/data/databaseNews.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT guild_id, channel_id, role_id, last_news_id, language from news_settings
        """)
        rows = cursor.fetchall()
        conn.commit()
        conn.close()
        print("ROWS FROM DB:", rows)

        for guild_id, channel_id, role_id, last_news_id, language in rows:
            try:
                if language == 'Russian':
                    MAIN_URL = RUS_URL
                elif language == 'English':
                    MAIN_URL = ENG_URL
                else:
                    continue

                response = requests.get(MAIN_URL, timeout=10)
                response.raise_for_status()
                data = response.json()

                event_name = data["events"][0]["event_name"]
                description = data["events"][0]["announcement_body"]["body"]
                clan_id = data["events"][0]["announcement_body"]["clanid"]
                image_id = json.loads(data["events"][0]["jsondata"])["localized_capsule_image"][0]
                current_news_id = data["events"][0]["gid"]
                app_id = data["events"][0]["appid"]



                if last_news_id != current_news_id:
                    conn = sqlite3.connect("/app/data/databaseNews.db")
                    cursor = conn.cursor()

                    cursor.execute("""
                        UPDATE news_settings
                        SET last_news_id = ?
                        WHERE channel_id = ? AND language = ?

                    """, (current_news_id, channel_id, language))
                    conn.commit()
                    conn.close()

                    embed = discord.Embed(
                        title=event_name,
                        url=f"https://steamcommunity.com/games/{app_id}/announcements/detail/{current_news_id}",
                        color=0xFFFFFF
                    )
                    embed.add_field(name="Description:", value=bbcode_to_discord(description)[:1000] + '...')
                    embed.set_image(url=f"https://clan.akamai.steamstatic.com/images/{clan_id}/{image_id}")
                    embed.set_footer(text='📍News provided by BvvD bot')
                    if language == 'Russian':
                        embed.set_author(name='Новости War Thunder')
                    elif language == 'English':
                        embed.set_author(name='War Thunder News')

                    channel = self.bot.get_channel(channel_id)
                    if channel is not None:
                        await channel.send(content=f"<@&{role_id}>", embed=embed)

            except Exception as e:
                print(f"[check_news] guild={guild_id} language={language} error={type(e).__name__}: {e}")

    @check_news.before_loop
    async def before_check_news(self):
        await self.bot.wait_until_ready()
                

            




        





































async def setup(bot):
    await bot.add_cog(NewsCog(bot))