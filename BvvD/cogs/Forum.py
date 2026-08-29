import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3
import re
import json
import html

load_dotenv()


#--------------- функции ебучие пока ток чистка текста

def clean_text(text: str) -> str:

    text = re.sub(r'\[quote=.*?\].*?\[/quote\]\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()


#--------------------- ПОДГОТОВКА

class ForumCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.forum_checker.start()

    def cog_unload(self):
        self.forum_checker.cancel()

    def init_db(self):
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/databaseForum.db")

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forum_settings (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            last_forum_id TEXT,
            sent_forum_ids TEXT,
            PRIMARY KEY (guild_id, channel_id)
            )
        """)
        conn.commit()
        conn.close()

#---------------------- КОММАНДЫ 
#-- добавление

    @app_commands.command(name='setforumpings', description='Sets pings for important forum announcments')
    async def setforumpings(self, interaction: discord.Interaction, role: discord.Role):
        role_id = role.id
        channel_id = interaction.channel.id
        guild_id = interaction.guild.id

        conn = sqlite3.connect("/app/data/databaseForum.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO forum_settings (guild_id, channel_id, role_id)
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
            value=f'{interaction.channel.mention} is now **set** for WarThunder Forum, and will ping members on important announcments with {role.mention} role')
        await interaction.response.send_message(embed=embed, ephemeral=True)



# -- удаление

    @app_commands.command(name='removeforumpings', description='Removes Forum pings from this channel')
    async def removeforumpings(self, interaction: discord.Interaction):
        conn = sqlite3.connect("/app/data/databaseForum.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT channel_id FROM forum_settings
            WHERE guild_id = ?;
        """, (interaction.guild.id,))
        rows = cursor.fetchall()
        channel_ids = [row[0] for row in rows]

        if interaction.channel.id in channel_ids:
            cursor.execute("""
                DELETE FROM forum_settings
                WHERE channel_id = ?;
            """, (interaction.channel.id,))

            embed1 = discord.Embed(
                title=f'**Removed all** Forum pings from <#{interaction.channel.id}>',
                color=0xFFFFFF
            )
            await interaction.response.send_message(embed=embed1, ephemeral=True)
        else:
            embed2 = discord.Embed(
                title='This channel is **not** set for any **Forum** pings',
                color=0xFFFFFF
            )
            await interaction.response.send_message(embed=embed2, ephemeral=True)

        conn.commit()
        conn.close()


#----------------------- поиск 


    @tasks.loop(seconds=30)
    async def forum_checker(self):

        conn = sqlite3.connect("/app/data/databaseForum.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT guild_id, channel_id, role_id, last_forum_id, sent_forum_ids
            FROM forum_settings
        """)
        rows = cursor.fetchall()
        conn.close()

#------------------------ филтьрация
#-- первичный запрос
        POSTS_URL = 'https://forum.warthunder.com/posts.json'
        response = requests.get(POSTS_URL, timeout=15)
        response.raise_for_status()
        data = response.json()

        posts = data.get("latest_posts", [])


        for guild_id, channel_id, role_id, last_forum_id, sent_forum_ids in rows:
            try:
#-- поиск                
                sent_forum_ids = json.loads(sent_forum_ids or "[]" )
                
                for posts_data in posts:
                    if posts_data.get("is_important", 0) != 1:
                        continue

                    post_id = posts_data.get("id")

                    if post_id in sent_forum_ids:
                        continue

                    last_forum_id = post_id
                    sent_forum_ids.append(post_id)


                    post_owner = posts_data.get("username")
                    avatar_template = posts_data.get("avatar_template")
                    avatar_url = None
                    if avatar_template:
                        avatar_url = "https://forum.warthunder.com" + avatar_template.replace("{size}", "96")
                    topic_id = posts_data.get("topic_id")     
                    topic_slug = posts_data.get("topic_slug")       
                    topic_title = posts_data.get("topic_title")                
                    post_number = posts_data.get("post_number")
                    raw_text = posts_data.get("raw")
                    text = clean_text(raw_text)

                    post_url = (
                        f"https://forum.warthunder.com/t/"
                        f"{topic_slug}/"
                        f"{topic_id}/"
                        f"{post_number}"
                    )

#-- ембед
                    embed = discord.Embed(
                        title=topic_title,
                        url=post_url,
                        description=text[:1024],
                        color=0xFFFFFF
                    )
                    embed.set_author(name=post_owner, icon_url=avatar_url)
                    embed.set_footer(text='📍New forum announcement provided by BvvD bot')

#-- запись скл
                    conn = sqlite3.connect("/app/data/databaseForum.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE forum_settings
                        SET last_forum_id = ?, sent_forum_ids = ?
                        WHERE channel_id = ? AND guild_id = ?
                    """, (last_forum_id, json.dumps(sent_forum_ids), channel_id, guild_id))
                    conn.commit()
                    conn.close()

#-- отправка
                    channel = self.bot.get_channel(channel_id)
                    if channel is not None:
                        await channel.send(content=f"<@&{role_id}>", embed=embed)


            except requests.RequestException as e:
                print(f"Ошибка запроса: {e}")
            except Exception as e:
                print(e)

    @forum_checker.before_loop
    async def before_check_forum(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ForumCog(bot))