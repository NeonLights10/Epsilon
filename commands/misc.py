import asyncio
import psutil
import time
import os
import csv
import dateutil.parser

from io import StringIO

import discord
from discord import app_commands
from discord.ext import commands

from __main__ import log, db
from formatting.constants import NAME, VERSION as BOTVERSION
from commands.errorhandler import CheckOwner


class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner():
        async def predicate(ctx):
            if ctx.interaction.user.id == 133048058756726784:
                return True
            else:
                raise CheckOwner()

        return commands.check(predicate)

    async def generate_invite_link(self, permissions=discord.Permissions(1632444476630)):
        app_info = await self.bot.application_info()
        return discord.utils.oauth_url(app_info.id, permissions=permissions, scopes=['bot', 'applications.commands'])

    @app_commands.command(name='stats',
                          description='Provides statistics about the bot.')
    @app_commands.guilds(911509078038151168)
    async def stats(self,
                    interaction: discord.Interaction):
        content = discord.Embed(colour=0x1abc9c)
        content.set_author(name=f"{NAME} v{BOTVERSION}", icon_url=self.bot.user.display_avatar.url)
        content.set_footer(text="Fueee~")
        content.add_field(name="Author", value="Neon#5555")
        content.add_field(name="BotID", value=self.bot.user.id)
        content.add_field(name="Messages",
                          value=f"{self.bot.message_count} ({(self.bot.message_count / ((time.time() - self.bot.uptime) / 60)):.2f}/min)")
        content.add_field(name="Commands Processed", value=f"{self.bot.command_count}")
        process = psutil.Process(os.getpid())
        mem = process.memory_full_info()
        mem = mem.uss / 1000000
        content.add_field(name="Memory Usage", value=f'{mem:.2f} MB')
        content.add_field(name="Servers", value=f"I am running on {str(len(self.bot.guilds))} servers")
        ctime = float(time.time() - self.bot.uptime)
        day = ctime // (24 * 3600)
        ctime = ctime % (24 * 3600)
        hour = ctime // 3600
        ctime %= 3600
        minutes = ctime // 60
        content.add_field(name="Uptime", value=f"{day:.0f} days\n{hour:.0f} hours\n{minutes:.0f} minutes")
        await interaction.response.send_message(embed=content)


async def setup(bot):
    await bot.add_cog(Miscellaneous(bot))


async def teardown(bot):
    bot.tree.remove('stats', guild=discord.Object(id=911509078038151168))
    await bot.tree.sync(guild=discord.Object(id=911509078038151168))