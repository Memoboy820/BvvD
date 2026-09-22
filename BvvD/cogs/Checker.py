import discord
import sqlite3
from discord import app_commands
from discord.ext import commands, tasks

class CheckerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# -------------------------- комманды
# -- настройки сервра

    @app_commands.command(name='checksettings', description='Shows which channels and roles are used for YouTube and News pings')
    async def checksettings(self, interaction: discord.Interaction):
        guildid = interaction.guild.id

# -- поиск в бд ютуба

        conn = sqlite3.connect("/app/data/database.db", timeout=10)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT guild_id, channel_id, role_id, language FROM youtube_settings
                WHERE guild_id = ?
    """, (guildid,))
            rowsyt = cursor.fetchall()
        finally:
            conn.close()

# -- поиск в бд новостей

        conn = sqlite3.connect("/app/data/databaseNews.db", timeout=10)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT guild_id, channel_id, role_id, language FROM news_settings
                WHERE guild_id = ?
    """, (guildid,))
            rowsnw = cursor.fetchall()
        finally:
            conn.close()

# -- поиск в бд датамайн

        conn = sqlite3.connect("/app/data/datamines.db", timeout=10)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT guild_id, channel_id, role_id FROM datamines_settings
                WHERE guild_id = ?
    """, (guildid,))
            rowsdtmns = cursor.fetchall()
        finally:
            conn.close()

# ------------- создание ембеда

        if rowsnw or rowsyt:       
            embed = discord.Embed(
                title='Notification Settings / Настройка Пингов',
                color=0xFFFFFF
            )
            if rowsyt :
                for guild_id, channel_id, role_id, language in rowsyt:
                    if language == 'Russian':
                        languageRu = 'Русскоязычного'
                    else:
                        languageRu = 'Англоязычного'
                    embed.add_field(name=f'**{language}** YouTube Pings / Пинги **{languageRu}** Ютуба:', value=f"Channel / Канал: <#{channel_id}> \nPing Role / Роль: <@&{role_id}>", inline=False)

            if rowsnw:
                for guild_id, channel_id, role_id, language in rowsnw:
                    if language == 'Russian':
                        languageRu = 'Русских'
                    else:
                        languageRu = 'Английских'
                    embed.add_field(name=f'**{language}** News Pings / Пинги **{languageRu}** Новостей:', value=f"Channel / Канал: <#{channel_id}> \nPing Role / Роль: <@&{role_id}>", inline=False)
            
            if rowsdtmns:
                for guild_id, channel_id, role_id in rowsdtmns:
                    embed.add_field(name=f'Datamines Pings / Пинги по изменениям в файлах:', value=f"Channel / Канал: <#{channel_id}> \nPing Role / Роль: <@&{role_id}>", inline=False)

        else:
            embed = discord.Embed(
                title=':flag_us: This server has no pings \n:flag_ru: На данном сервере не установленны пинги',
                color=0xFFFFFF
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# -- инфа о боте

    @app_commands.command(name='info', description='Info about how this bot works')
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='❓ Как использовать бота Bvvd / How to use BvvD bot: ❓',
            color=0xFFFFFF
        )
        embed.add_field(name=':flag_ru: RUS:',value=''
        '- Используйте комманды `"/setyoutubepings"`, `"/setnewspings"` и ``"/setdataminespings" чтобы *задать* данный канал для пингов *Ютуба*, *Новостей* или *Изменений в файлах* игры *соответственно*' 
        '\n- Для удаления пингов используйте комманды `"/removeyoutubepings"`, `"/removenewspings"` и `"/removedataminespings"` чтобы *убрать* пинги с данного канала для *Ютуба*, *Новостей* или *Изменений в файлах*' 
        '\n- Для просмотра заданных каналов используйте комманду `"/checksettings"`')
        embed.add_field(name=':flag_us: ENG:',value=''
        '- Use the `"/setyoutubepings"`, `"/setnewspings"` and `"/setdataminespings"` commands to *set* this channel for *YouTube*, *News* or *Datamines* pings'
        '\n- To remove pings, use the `"/removeyoutubepings"`, `"/removenewspings"` and `"/removedataminespings"` commands to *remove* pings from this channel for *YouTube*, *News* or *Datamines*'
        '\n- To view configured channels, use the `"/checksettings"` command')

        embed.set_footer(text='Thanks for using BvvD bot❤️')
        embed.set_footer(text='Спасибо что пользуетесь ботом BvvD❤️ / Thanks  for using BvvD bot❤️')

        await interaction.response.send_message(embed=embed, ephemeral=True)



async def setup(bot):
    await bot.add_cog(CheckerCog(bot))
