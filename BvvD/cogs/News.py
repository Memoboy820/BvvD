import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands, tasks
import requests
import sqlite3
import re
import json
import httpx
import asyncio

load_dotenv()

# ------------------------------------------ funcs

async def request(client: httpx.AsyncClient, lang_list: int):
    try:
        response = await client.get("", params={"appid": 236390, "lang_list": lang_list, "count_before": 0, "count_after": 5})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f'[NWS] - {e}')
        return None



async def get_data_news(): # 8 - rus, 0 - eng
    async with httpx.AsyncClient(
        base_url="https://store.steampowered.com/events/ajaxgetadjacentpartnerevents",
        timeout=10,
        follow_redirects=True
    ) as client:

        data = await asyncio.gather(
            request(client=client, lang_list=8),
            request(client=client, lang_list=0)
        )

        return data




def get_sql_data():
    conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT guild_id, channel_id, role_id, last_news_id, sent_news_ids, language from news_settings
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()
    return rows



async def get_all_data():
    data = await asyncio.gather(
        asyncio.to_thread(get_sql_data),
        get_data_news()
    )
    return data



def update_sql(current_news_id, channel_id, language, sent_ids):
    conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
    cursor = conn.cursor()

    try:
        sent_ids.append(current_news_id)
        sent_ids = list(dict.fromkeys(sent_ids))[-20:]

        cursor.execute("""
            UPDATE news_settings
            SET last_news_id = ?, sent_news_ids = ?
            WHERE channel_id = ? AND language = ?
        """, (current_news_id, json.dumps(sent_ids), channel_id, language))
        conn.commit()
    finally:
        conn.close()



def insert_sql(guild_id, channel_id, role_id, language, sent_ids):
    conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO news_settings (guild_id, channel_id, role_id, language, last_news_id, sent_news_ids)
            VALUES (?, ?, ?, ?, NULL, ?)
            ON CONFLICT(guild_id, language) DO UPDATE SET
                channel_id = excluded.channel_id,
                role_id = excluded.role_id
        """, (guild_id, channel_id, role_id, language, json.dumps(sent_ids)))
        conn.commit()
    finally:
        conn.close()



def get_channel_ids_sql(interaction: discord.Interaction):
    conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
                        SELECT channel_id FROM news_settings
                        WHERE guild_id = ?;
                """,(interaction.guild.id,))
        conn.commit()
        rows = cursor.fetchall()
        channel_ids = [row[0] for row in rows]

        return channel_ids
    finally:
        conn.close()



def delete_sql(interaction: discord.Interaction):
    conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            DELETE FROM news_settings
            WHERE channel_id = ?;
        """,(interaction.channel.id,))
        conn.commit()
    finally:
        conn.close()






async def kd_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            "10 second command cooldown",
            ephemeral=True
        )


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


# ---------------------------------- Bot Cog

class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()
        self.check_news.start()

    def cog_unload(self):
        self.check_news.cancel()

    def init_db(self):
        os.makedirs("/app/data", exist_ok=True)
        conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news_settings (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            last_news_id TEXT,
            sent_news_ids TEXT,
            language TEXT NOT NULL,
            PRIMARY KEY (guild_id, language)
            )
        """)
        try:
            cursor.execute("ALTER TABLE news_settings ADD COLUMN sent_news_ids TEXT")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()


# ------------------------------------- Commands


    @app_commands.command(name='setnewspings', description='Sets channel for WT news')
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def setnews(self, interaction: discord.Interaction, role: discord.Role):
        
        view = NewsCog.NewsView(interaction, role)
        embed = discord.Embed(
            title='News Pings / Пинги Новостей',
            description=':flag_us: Choose one of the WT News languages for this channel: \n:flag_ru: Выберите язык Новостей ВарТандера для этого канала:',
            color=0xFFFFFF
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    class NewsButton(discord.ui.Button):
        def __init__(self, language: str):
            super().__init__(label=language)
            self.language = language

        async def callback(self, interaction):
            await interaction.response.defer(ephemeral=True)
            for item in self.view.children:
                item.disabled = True
            await interaction.edit_original_response(view=self.view)


            guild_id = interaction.guild.id
            channel_id = interaction.channel.id
            role_id = self.view.role_id
            language = self.language

            RUS_URL = "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/?appid=236390&lang_list=8&count_before=0&count_after=5"
            ENG_URL = "https://store.steampowered.com/events/ajaxgetadjacentpartnerevents/?appid=236390&lang_list=0&count_before=0&count_after=5"

            if language == 'Russian':
                MAIN_URL = RUS_URL
            elif language == 'English':
                MAIN_URL = ENG_URL
            else:
                return
            
            try:
                response = await asyncio.to_thread(
                    httpx.get,
                    MAIN_URL,
                    timeout=10,
                    follow_redirects=True
                )
                response.raise_for_status()
                data = response.json()

                events_sorted = sorted(
                    data["events"][:5],
                    key=lambda event: event.get("announcement_body", {}).get("posttime", 0),
                    reverse=True
    )
                sent_ids = [str(event["gid"]) for event in events_sorted[1:]]

                await asyncio.to_thread(insert_sql, guild_id=guild_id, channel_id=channel_id, role_id=role_id, language=language, sent_ids=sent_ids)

            except Exception as e:
                print(f'SetNWSPings: {e}')
                await interaction.followup.send("Не удалось сохранить изменения | Couldn't save the changes", ephemeral=True)
                return

            embed = discord.Embed(color=0xFFFFFF)
            embed.add_field(name='Done!', value=f'{interaction.channel.mention} is now **set** for **{self.language}** WarThunder News, and will ping members with {self.view.role} role')
            await interaction.followup.send(embed=embed, ephemeral=True)
                            
            


    class NewsView(discord.ui.View):
        def __init__(self, interaction: discord.Interaction, role: discord.Role):
            super().__init__()
            self.interaction = interaction
            self.role = role.mention
            self.role_id = role.id

            self.add_item(NewsCog.NewsButton("Russian"))
            self.add_item(NewsCog.NewsButton("English"))









    @app_commands.command(name='removenewspings', description='Removes News pings from this channel')
    @app_commands.checks.cooldown(1, 10, key=lambda interaction: interaction.guild_id)
    async def removenewspings(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            channel_ids = await asyncio.to_thread(get_channel_ids_sql, interaction=interaction)

            if interaction.channel.id in channel_ids:
                await asyncio.to_thread(delete_sql, interaction=interaction)

                embed1 = discord.Embed(
                    title=f'**Removed all** News pings from <#{interaction.channel.id}>',
                    color=0xFFFFFF
                )
                await interaction.followup.send(embed=embed1, ephemeral=True)
            else:
                embed2 = discord.Embed(
                    title='This channel is **not** set for any **News** pings',
                    color=0xFFFFFF
                )
                await interaction.followup.send(embed=embed2, ephemeral=True)
        except Exception as e:
            print(f'RemoveNWSPings: {e}')
            await interaction.followup.send("Не удалось сохранить изменения | Couldn't save the changes", ephemeral=True)
            






# ------------------------------------------ Loop


    @tasks.loop(minutes=1)
    async def check_news(self):

        data_rus = None
        data_eng = None

        try:
            rows, data = await get_all_data()
            data_rus, data_eng = data
        except Exception as e:
            print(f"[NWS] Получение данных: {e}")
            return

        for guild_id, channel_id, role_id, last_news_id, sent_news_ids, language in rows:
            try:
                if language == 'Russian':
                    if data_rus is None:
                        continue
                    data = data_rus
                elif language == 'English':
                    if data_eng is None:
                        continue
                    data = data_eng
                else:
                    continue

                if sent_news_ids:
                    sent_ids = json.loads(sent_news_ids)
                else:
                    sent_ids = []
                if not sent_ids and last_news_id:
                    sent_ids = [last_news_id]

                sent_ids = [str(x) for x in sent_ids]

                selected_event = None
                for event in data["events"][:5]:
                    if str(event["gid"]) not in sent_ids:
                        selected_event = event
                        break

                if selected_event is None:
                    continue

                event_name = selected_event["event_name"]
                description = selected_event["announcement_body"]["body"]
                clan_id = selected_event["announcement_body"]["clanid"]
                image_id = json.loads(selected_event["jsondata"])["localized_capsule_image"][0]
                current_news_id = selected_event["gid"]
                app_id = selected_event["appid"]

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

                    await asyncio.to_thread(update_sql, current_news_id=current_news_id, channel_id=channel_id, language=language, sent_ids=sent_ids)

            except Exception as e:
                print(f"[check_news] guild={guild_id} language={language} error={type(e).__name__}: {e}")

    @check_news.before_loop
    async def before_check_news(self):
        await self.bot.wait_until_ready()

NewsCog.setnews.error(kd_error)
NewsCog.removenewspings.error(kd_error)

async def setup(bot):
    await bot.add_cog(NewsCog(bot))
