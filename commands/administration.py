import discord
import re
import time
import validators
import datetime
import asyncio

from dateutil.relativedelta import relativedelta
from datetime import timedelta
from typing import Union

from discord.ext import commands

from formatting.constants import UNITS
from formatting.embed import gen_embed
from commands.errorhandler import CheckOwner

from bson.objectid import ObjectId

from __main__ import log, db

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def convert_emoji(argument):
        return zemoji.demojize(argument)

    def is_pubcord(self):
        async def predicate(ctx):
            if isinstance(ctx, discord.ApplicationContext):
                return ctx.interaction.guild_id == 432379300684103699
            else:
                return ctx.guild.id == 432379300684103699

        return commands.check(predicate)

    def has_modrole(self):
        async def predicate(ctx):
            if isinstance(ctx, discord.ApplicationContext):
                document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
                if document['modrole']:
                    role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.interaction.guild.roles)
                    return role in ctx.interaction.user.roles
                else:
                    return False
            else:
                document = await db.servers.find_one({"server_id": ctx.guild.id})
                if document['modrole']:
                    role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                    return role in ctx.author.roles
                else:
                    return False

        return commands.check(predicate)

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


    @commands.command(name='speak',
                      description='For official Bandori discord internal use only')
    @commands.check_any(command.has_guild_permissions(manage_roles=True), has_modrole())
    @commands.check(is_pubcord())
    async def speak(self, ctx, dest: Union[discord.TextChannel, discord.Message], *, msg_content: str):
        if isinstance(dest, discord.Message):
            if ctx.message.attachments:
                for attachment in ctx.message.attachments:
                    attachment_file = await attachment.to_file()
                    await dest.send(file=attachment_file)
            if msg_content:
                await dest.reply(content=f'{msg_content}')
        elif isinstance(dest, discord.TextChannel):
            if ctx.message.attachments:
                for attachment in ctx.message.attachments:
                    attachment_file = await attachment.to_file()
                    await dest.send(file=attachment_file)
            if msg_content:
                await dest.send(content=f'{msg_content}')


    @discord.slash_command(name='settings',
                           description='Configure settings for Kanon Bot')
    async def settings(self,
                       ctx: discord.ApplicationContext):

        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})

        class SettingsMenu(discord.ui.View):
            def __init__(self, context, guild_document):
                super().__init__()
                self.context = context
                self.guild_document = guild_document
                self.value = None

            async def interaction_check(self,
                                        interaction: Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.send_message("Stopped configuring settings.", ephemeral=True)
                for item in self.view.children:
                    item.disabled = True
                self.view.stop()

            @discord.ui.select(placeholder='Choose a setting to configure',
                               min_values=1,
                               max_values=1,
                               options=[
                                   discord.SelectOption(
                                       label='Prefix',
                                       description='Set prefix for the server'
                                   ),
                                   discord.SelectOption(
                                       label='Global Announcements',
                                       description='Enable/disable update announcements from Kanon Bot'
                                   ),
                                   discord.SelectOption(
                                       label='Modmail',
                                       description='Enable/disable modmail on this server'
                                   ),
                                   discord.SelectOption(
                                       label='Chat Feature',
                                       description="Enable Kanon's chat feature!"
                                   ),
                                   discord.SelectOption(
                                       label='Blacklist/Whitelist',
                                       description='Enable/disable blacklist/whitelist for chat feature'
                                   ),
                                   discord.SelectOption(
                                       label='Fun Features',
                                       description='Enable/disable fun commands (i.e. /hug, /headpat, etc.)'
                                   ),
                                   discord.SelectOption(
                                       label='Logging',
                                       description='Configure logging of moderation/user activities'
                                   ),
                                   discord.SelectOption(
                                       label='Auto Assign Role On Join',
                                       description='Set a role to be assigned when a user joins the server'
                                   ),
                                   discord.SelectOption(
                                       label='Moderator Role',
                                       description='Set a moderator role to allow use of Kanon Bot w/o role permissions'
                                   ),
                                   discord.SelectOption(
                                       label='Server Join Verification',
                                       description='Enable/disable user self-verification upon joining the server'
                                   )
                               ])
            async def settings_menu(self, select: discord.ui.Select, interaction: discord.Interaction):
                match select.values[0]:
                    case 'Prefix':
                        await prefix_menu(self.context, interaction)
                    case 'Global Announcements':
                        await announcement_menu(self.context, interaction)
                    case 'Modmail':
                        await modmail_menu(self.context, interaction)
                    case 'Chat Feature':
                        await chat_menu(self.context, interaction)
                    case 'Blacklist/Whitelist':
                        await bw_list_menu(self.context, interaction)
                    case 'Fun Features':
                        await fun_menu(self.context, interaction)
                    case 'Logging':
                        await logging_menu(self.context, interaction)
                    case 'Auto Assign Role On Join':
                        await autorole_menu(self.context, interaction)
                    case 'Moderator Role':
                        await modrole_menu(self.context, interaction)
                    case 'Server Join Verification':
                        await verification_menu(self.context, interaction)

            async def prefix_menu(self,
                                  context: discord.ApplicationContext,
                                  interaction: discord.Interaction):
                pass

            async def announcement_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def modmail_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def chat_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def bw_list_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def fun_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def logging_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def autorole_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def modrole_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

            async def verification_menu(self,
                                        context: discord.ApplicationContext,
                                        interaction: discord.Interaction):
                pass

        # construct message embed here with settings listed and view added

