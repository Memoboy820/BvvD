import discord
import sqlite3
from discord import app_commands
from discord.ext import commands, tasks

class CheckerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='checksettings', description='Shows which channels and roles are used for YouTube and News pings')
    async def checksettings(self, interaction: discord.Interaction):
        guildid = interaction.guild.id
        conn = sqlite3.connect("/app/data/database.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT guild_id, channel_id, role_id, language FROM youtube_settings
            WHERE guild_id = ?
""", (guildid,))
        rowsyt = cursor.fetchall()
        conn.commit()
        conn.close()

        conn = sqlite3.connect("/app/data/databaseNews.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT guild_id, channel_id, role_id, language FROM news_settings
            WHERE guild_id = ?
""", (guildid,))
        rowsnw = cursor.fetchall()
        conn.commit()
        conn.close()
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
        else:
            embed = discord.Embed(
                title=':flag_us: This server has no pings \n:flag_ru: На данном сервере не установленны пинги',
                color=0xFFFFFF
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='info', description='Info about how this bot works')
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='❓ Как использовать бота Bvvd / How to use BvvD bot: ❓',
            color=0xFFFFFF
        )
        embed.add_field(name=':flag_ru: RUS:',value='- Используйте комманды `"/setyoutubepings"` и `"/setnewspings"` чтобы *задать* данный канал для пингов *Ютуба* или *Новостей* игры *соответственно*' \
        '\n- Для удаления пингов используйте комманды `"/removeyoutubepings"` и `"/removenewspings"` чтобы *убрать* пинги с данного канала для *Ютуба* или *Новостей*' \
        '\n- Для просмотра заданных каналов используйте комманду `"/checksettings"`')

        embed.add_field(name=':flag_us: ENG:',value='- Use the `"/setyoutubepings"` and `"/setnewspings"` commands to *set* this channel for *YouTube* or *News* pings'
        '\n- To remove pings, use the `"/removeyoutubepings"` and `"/removenewspings"` commands to *remove* pings from this channel for *YouTube* or *News*'
        '\n- To view configured channels, use the `"/checksettings"` command')
        embed.set_footer(text='Thanks for using BvvD bot❤️')

        embed.set_footer(text='Спасибо что пользуетесь ботом BvvD❤️ / Thanks  for using BvvD bot❤️')

        

        await interaction.response.send_message(embed=embed, ephemeral=True)








async def setup(bot):
    await bot.add_cog(CheckerCog(bot))
