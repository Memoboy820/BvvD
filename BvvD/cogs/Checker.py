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
                title='Notification settings',
                color=0xFFFFFF
            )
            if rowsyt :
                for guild_id, channel_id, role_id, language in rowsyt:
                    embed.add_field(name=f'**{language}** YouTube Pings:', value=f"Channel: <#{channel_id}> \nPing Role: <@&{role_id}>", inline=False)
            if rowsnw:
                for guild_id, channel_id, role_id, language in rowsnw:
                    embed.add_field(name=f'**{language}** News Pings:', value=f"Channel: <#{channel_id}> \nPing Role: <@&{role_id}>", inline=False)
        else:
            embed = discord.Embed(
                title='This server has no pings',
                color=0xFFFFFF
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(CheckerCog(bot))