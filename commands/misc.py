import asyncio
import psutil
import time
import os
import csv
import dateutil.parser

from io import StringIO

import discord
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup

from __main__ import log, db
from formatting.embed import gen_embed
from formatting.constants import NAME, VERSION as BOTVERSION
from commands.errorhandler import CheckOwner


class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner():
        async def predicate(ctx) -> bool:
            if isinstance(ctx, discord.ApplicationContext):
                if ctx.interaction.user.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()
            else:
                if ctx.author.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()

        return commands.check(predicate)

    async def generate_invite_link(self, permissions=discord.Permissions(1632444476630)):
        app_info = await self.bot.application_info()
        return discord.utils.oauth_url(app_info.id, permissions=permissions, scopes=['bot', 'applications.commands'])

    @discord.slash_command(name='stats',
                           description='Provides statistics about the bot.')
    async def stats(self,
                    ctx: discord.ApplicationContext):
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
        await ctx.respond(embed=content)

    @discord.slash_command(name='invite',
                           description='Create a link to invite the bot to your server.')
    async def invite(self,
                     ctx: discord.ApplicationContext):
        url = await self.generate_invite_link()
        content = discord.Embed(colour=0x1abc9c)
        content.set_author(name=f"{NAME} v{BOTVERSION}", icon_url=self.bot.user.display_avatar.url)
        content.set_footer(text="Fueee~")
        content.add_field(name="Invite Link:", value=url)
        await ctx.respond(embed=content)

    @discord.slash_command(name='support',
                           description='Support the bot by donating for server costs!')
    async def support(self,
                      ctx: discord.ApplicationContext):
        await ctx.respond(embed=gen_embed(title='Support Kanon Bot',
                                          content='Kanon costs money to run. I pay for her server costs out of pocket, '
                                                  'so any donation helps!\nSupport: https://www.patreon.com/kanonbot '
                                                  'or https://ko-fi.com/neonlights'))

    # TODO: make shoutout command pull from list of discord members with role

    datadeletion = SlashCommandGroup('delete', 'Delete guild/user data')

    @datadeletion.command(name='guild',
                          description='Delete all data for specified guild')
    @is_owner()
    async def del_guild(self,
                        ctx: discord.ApplicationContext,
                        guild: Option(discord.Guild, 'Guild ID of the guild you wish to delete data for')):
        await ctx.interaction.response.defer()
        await db.msgid.delete_many({'server_id': guild.id})
        await db.warns.delete_many({'server_id': guild.id})
        await db.rolereact.delete_many({'server_id': guild.id})
        await db.servers.delete_one({'server_id': guild.id})
        await db.emoji.delete_many({'server_id': guild.id})
        await db.reminders.delete_many({'server_id': guild.id})
        await guild.leave()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='delete guild', content=f'Guild {guild.name} (ID: {server_id} data has been deleted.')
        )

    @datadeletion.command(name='user',
                          description='Delete all data for specified user')
    @is_owner()
    async def del_user(self,
                       ctx: discord.ApplicationContext,
                       user: Option(discord.User, 'User you wish to delete data for')):
        await ctx.interaction.response.defer()
        await db.msgid.delete_many({'author_id': user.id})
        await db.warns.delete_many({'user_id': user.id})
        await db.reminders.delete_many({'user_id': user.id})
        await ctx.interaction.followup.send(
            embed=gen_embed(title='delete user', content=f'User {user.name}#{user.discriminator} (ID: {user.id}) data '
                                                         f'has been deleted.')
        )


def setup(bot):
    bot.add_cog(Miscellaneous(bot))
