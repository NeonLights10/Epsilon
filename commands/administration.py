import asyncio
import re
import time
import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from typing import Union, Optional, List, SupportsInt

import emoji as zemoji
import validators
import pymongo
from bson.objectid import ObjectId

import discord
from discord.commands.permissions import default_permissions
from discord.ext import commands, pages
from discord.commands import Option, SlashCommandGroup
from discord.ui import InputText

from __main__ import log, db
from commands.errorhandler import CheckOwner
from formatting.embed import gen_embed
from formatting.constants import COLORS, UNITS

TIME_RE_STRING = r"\s?".join(
    [
        r"((?P<weeks>\d+?)\s?(weeks?|w))?",
        r"((?P<days>\d+?)\s?(days?|d))?",
        r"((?P<hours>\d+?)\s?(hours?|hrs|hr?))?",
        r"((?P<minutes>\d+?)\s?(minutes?|mins?|m(?!o)))?",  # prevent matching "months"
        r"((?P<seconds>\d+?)\s?(seconds?|secs?|s))?",
    ]
)

TIME_RE = re.compile(TIME_RE_STRING, re.I)


def parse_timedelta(argument: str, *, maximum: Optional[timedelta] = None, minimum: Optional[timedelta] = None,
                    allowed_units: Optional[List[str]] = None) -> Optional[timedelta]:
    """
    This converts a user provided string into a timedelta
    The units should be in order from largest to smallest.
    This works with or without whitespace.
    Parameters
    ----------
    argument : str
        The user provided input
    maximum : Optional[timedelta]
        If provided, any parsed value higher than this will raise an exception
    minimum : Optional[timedelta]
        If provided, any parsed value lower than this will raise an exception
    allowed_units : Optional[List[str]]
        If provided, you can constrain a user to expressing the amount of time
        in specific units. The units you can chose to provide are the same as the
        parser understands. (``weeks``, ``days``, ``hours``, ``minutes``, ``seconds``)
    Returns
    -------
    Optional[timedelta]
        If matched, the timedelta which was parsed. This can return `None`
    Raises
    ------
    BadArgument
        If the argument passed uses a unit not allowed, but understood
        or if the value is out of bounds.
    """
    matches = TIME_RE.match(argument)
    allowed_unit_list = allowed_units or ["weeks", "days", "hours", "minutes", "seconds"]
    if matches:
        params = {k: int(v) for k, v in matches.groupdict().items() if v is not None}
        for k in params.keys():
            if k not in allowed_unit_list:
                raise discord.ext.commands.BadArgument(
                    "`{unit}` is not a valid unit of time for this command".format(unit=k)
                )
        if params:
            try:
                delta = timedelta(**params)
            except OverflowError:
                raise discord.ext.commands.BadArgument(
                    "The time set is way too high, consider setting something reasonable."
                )
            if maximum and maximum < delta:
                raise discord.ext.commands.BadArgument(
                    "This amount of time is too large for this command. (Maximum: {maximum})".format(
                        maximum=humanize_timedelta(timedelta=maximum))
                )
            if minimum and delta < minimum:
                raise discord.ext.commands.BadArgument(
                    "This amount of time is too small for this command. (Minimum: {minimum})".format(
                        minimum=humanize_timedelta(timedelta=minimum))
                )
            return delta
    return None


def humanize_timedelta(*, timedelta: Optional[datetime.timedelta] = None, seconds: Optional[SupportsInt] = None) -> str:
    """
    Get a locale aware human timedelta representation.
    This works with either a timedelta object or a number of seconds.
    Fractional values will be omitted, and values less than 1 second
    an empty string.
    Parameters
    ----------
    timedelta: Optional[datetime.timedelta]
        A timedelta object
    seconds: Optional[SupportsInt]
        A number of seconds
    Returns
    -------
    str
        A locale aware representation of the timedelta or seconds.
    Raises
    ------
    ValueError
        The function was called with neither a number of seconds nor a timedelta object
    """

    try:
        obj = seconds if seconds is not None else timedelta.total_seconds()
    except AttributeError:
        raise ValueError("You must provide either a timedelta or a number of seconds")

    seconds = int(obj)
    periods = [
        ("year", "years", 60 * 60 * 24 * 365),
        ("month", "months", 60 * 60 * 24 * 30),
        ("day", "days", 60 * 60 * 24),
        ("hour", "hours", 60 * 60),
        ("minute", "minutes", 60),
        ("second", "seconds", 1),
    ]

    strings = []
    for period_name, plural_period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            if period_value == 0:
                continue
            unit = plural_period_name if period_value > 1 else period_name
            strings.append(f"{period_value} {unit}")

    return ", ".join(strings)


async def modmail_enabled(ctx):
    document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
    return document['modmail_channel']


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def is_pubcord():
        async def predicate(ctx):
            if isinstance(ctx, discord.ApplicationContext):
                return ctx.interaction.guild_id == 432379300684103699
            else:
                return ctx.guild.id == 432379300684103699

        return commands.check(predicate)

    @staticmethod
    def has_modrole():
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

    @staticmethod
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
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
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
    @default_permissions(manage_guild=True)
    async def settings(self,
                       ctx: discord.ApplicationContext):
        class Confirm(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.value = None

            # When the confirm button is pressed, set the inner value to `True` and
            # stop the View from listening to more input.
            # We also send the user an ephemeral message that we're confirming their choice.
            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
            async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
                # await interaction.response.send_message("Confirming", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = True
                self.stop()

            # This one is similar to the confirmation button except sets the inner value to `False`
            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                log.info('Workflow cancelled')
                await interaction.response.send_message("Operation cancelled.", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = False
                self.stop()

        class SettingsMenu(discord.ui.View):
            def __init__(self, context, start_embed, bot):
                super().__init__()
                self.context = context
                self.embed = start_embed
                self.bot = bot
                self.currentmessage = None

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.select(placeholder='Choose a setting to configure',
                               min_values=1,
                               max_values=1,
                               row=0,
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
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        prefix_embed = gen_embed(title='Prefix Settings',
                                                 content=f"**Prefix: {server_document['prefix'] or '%'}**")

                        prefix_view = PrefixMenu(self.context, self.bot)
                        self.currentmessage = await interaction.message.edit(embed=prefix_embed,
                                                                             view=prefix_view)
                        await prefix_view.wait()

                        if prefix_view.value:
                            self.embed.set_field_at(0,
                                                    name='Prefix',
                                                    value=prefix_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Global Announcements':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        content = ''
                        if server_document['announcements']:
                            content = 'Enabled'
                        if server_document['announcement_channel']:
                            announce_channel = ctx.guild.get_channel(int(server_document['announcement_channel']))
                            content = content + f' | Configured channel: {announce_channel.mention}'
                        else:
                            content = content + f', no channel set, using default settings.'
                        announcement_embed = gen_embed(title='Global Announcement Settings',
                                                       content=content)
                        announcement_view = AnnouncementMenu(self.context, self.bot)
                        self.currentmessage = await interaction.message.edit(embed=announcement_embed,
                                                                             view=announcement_view)

                        await announcement_view.wait()

                        if announcement_view.value:
                            self.embed.set_field_at(1,
                                                    name='Global Announcements',
                                                    value=announcement_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)

                    case 'Modmail':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        modmail_view = ModmailMenu(self.context, self.bot)
                        if server_document['modmail_channel']:
                            m_modmail_channel = ctx.guild.get_channel(int(server_document['modmail_channel']))
                            m_button_channel = ctx.guild.get_channel(int(server_document['modmail_button_channel']))
                            content = f'**Enabled** \nDestination channel: {m_modmail_channel.mention}'
                            content += f'\nButton channel: {m_button_channel.mention}'
                        else:
                            content = 'Disabled'
                            modmail_view.children[1].disabled = True
                            modmail_view.children[2].disabled = True
                        modmail_embed = gen_embed(title='Modmail Settings',
                                                  content=content)
                        self.currentmessage = await interaction.message.edit(embed=modmail_embed,
                                                                             view=modmail_view)

                        await modmail_view.wait()

                        if modmail_view.value:
                            self.embed.set_field_at(2,
                                                    name='Modmail',
                                                    value=modmail_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)

                    case 'Chat Feature':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        chat_view = ChatMenu(self.context, self.bot)
                        content = f"{'Enabled' if server_document['chat'] else 'Disabled'}"
                        chat_embed = gen_embed(title='Chat Feature Settings',
                                               content=content)
                        self.currentmessage = await interaction.message.edit(embed=chat_embed,
                                                                             view=chat_view)

                        await chat_view.wait()

                        if chat_view.value:
                            self.embed.set_field_at(3,
                                                    name='Chat Feature',
                                                    value=chat_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Blacklist/Whitelist':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        bwlist_view = BWListMenu(self.context, self.bot)
                        content = 'Disabled'
                        if blacklist_channels := server_document['blacklist']:
                            content = 'Blacklist enabled for the following channels:'
                            for c in blacklist_channels:
                                c = interaction.guild.get_channel(c)
                                content += f'\n{c.mention}'
                            content += '\n\nAdd/remove channels using `/blacklist add` or `/blacklist remove`'
                        if whitelist_channels := server_document['whitelist']:
                            content = 'Whitelist enabled for the following channels:'
                            for c in whitelist_channels:
                                c = interaction.guild.get_channel(c)
                                content += f'\n{c.mention}'
                            content += '\n\nAdd/remove channels using `/whitelist add` or `/whitelist remove`'
                        bwlist_embed = gen_embed(title='Blacklist/Whitelist Settings',
                                                 content=content)
                        self.currentmessage = await interaction.message.edit(embed=bwlist_embed,
                                                                             view=bwlist_view)

                        await bwlist_view.wait()

                        if bwlist_view.value:
                            self.embed.set_field_at(4,
                                                    name='Blacklist/Whitelist',
                                                    value=bwlist_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)

                    case 'Fun Features':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        fun_view = FunMenu(self.context, self.bot)
                        content = f"{'Enabled' if server_document['fun'] else 'Disabled'}"
                        fun_embed = gen_embed(title='Fun Features Settings',
                                              content=content)
                        self.currentmessage = await interaction.message.edit(embed=fun_embed,
                                                                             view=fun_view)

                        await fun_view.wait()

                        if fun_view.value:
                            self.embed.set_field_at(5,
                                                    name='Fun Features',
                                                    value=fun_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Logging':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        defaults = {'log_messages': server_document['log_messages'],
                                    'log_joinleaves': server_document['log_joinleaves'],
                                    'log_kbm': server_document['log_kbm'],
                                    'log_strikes': server_document['log_strikes']}
                        if server_document['log_channel']:
                            log_channel = ctx.guild.get_channel(int(server_document['log_channel']))
                            log_view = LogMenu(self.context, self.bot, log_channel, defaults)
                            if (defaults['log_messages']
                                    or defaults['log_joinleaves']
                                    or defaults['log_kbm']
                                    or defaults['log_strikes']):
                                content = f'Enabled | Configured channel: {log_channel.mention}'
                            else:
                                content = f'Disabled | Configured channel: {log_channel.mention}'
                        else:
                            log_view = LogMenu(self.context, self.bot, None, defaults)
                            content = f'Disabled | Configured channel: None'
                        log_embed = gen_embed(title='Logging Settings',
                                              content=content)
                        enabled_content = ''
                        disabled_content = ''
                        if (defaults['log_messages']
                                and defaults['log_joinleaves']
                                and defaults['log_kbm']
                                and defaults['log_strikes']):
                            disabled_content = 'None'
                        if (not defaults['log_messages']
                                and not defaults['log_joinleaves']
                                and not defaults['log_kbm']
                                and not defaults['log_strikes']):
                            enabled_content = 'None'
                        if defaults['log_messages']:
                            enabled_content += '・ Log message edits and deletion\n'
                        else:
                            disabled_content += '・ Log message edits and deletion\n'
                        if defaults['log_joinleaves']:
                            enabled_content += '・ Log member joins & leaves\n'
                        else:
                            disabled_content += '・ Log member joins & leaves\n'
                        if defaults['log_kbm']:
                            enabled_content += '・ Log kicks, bans, and timeouts/mutes\n'
                        else:
                            disabled_content += '・ Log kicks, bans, and timeouts/mutes\n'
                        if defaults['log_strikes']:
                            enabled_content += '・ Log strikes - which moderator assigned strike, message contents, ' \
                                               'etc.\n '
                        else:
                            disabled_content += '・ Log strikes - which moderator assigned strike, message contents, ' \
                                                'etc.\n '

                        log_embed.add_field(name='Enabled Options',
                                            value=enabled_content,
                                            inline=True)
                        log_embed.add_field(name='Disabled Options',
                                            value=disabled_content,
                                            inline=True)
                        self.currentmessage = await interaction.message.edit(embed=log_embed,
                                                                             view=log_view)

                        await log_view.wait()

                        if log_view.value:
                            self.embed.set_field_at(6,
                                                    name='Logging',
                                                    value=log_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Auto Assign Role On Join':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        autorole_view = AutoRoleMenu(self.context, self.bot)
                        if server_document['autorole']:
                            autorole = ctx.guild.get_role(int(server_document['autorole']))
                            content = f'**Enabled** for role {autorole.mention}'
                        else:
                            content = 'Disabled'
                            autorole_view.children[1].disabled = True
                        autorole_embed = gen_embed(title='Auto Assign Role Settings',
                                                   content=content)
                        self.currentmessage = await interaction.message.edit(embed=autorole_embed,
                                                                             view=autorole_view)

                        await autorole_view.wait()

                        if autorole_view.value:
                            self.embed.set_field_at(7,
                                                    name='Auto Assign Role On Join',
                                                    value=autorole_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Moderator Role':
                        await interaction.response.defer()
                        server_document = await db.servers.find_one({"server_id": interaction.guild_id})
                        modrole_view = ModRoleMenu(self.context, self.bot)
                        if server_document['modrole']:
                            modrole = ctx.guild.get_role(int(server_document['modrole']))
                            content = f'**Enabled** for role {modrole.mention}'
                        else:
                            content = 'Disabled'
                            modrole_view.children[1].disabled = True
                        modrole_embed = gen_embed(title='Moderator Role Settings',
                                                  content=content)
                        self.currentmessage = await interaction.message.edit(embed=modrole_embed,
                                                                             view=modrole_view)

                        await modrole_view.wait()

                        if modrole_view.value:
                            self.embed.set_field_at(7,
                                                    name='Auto Assign Role On Join',
                                                    value=modrole_view.value,
                                                    inline=False)
                        await self.currentmessage.edit(embed=self.embed,
                                                       view=self)
                    case 'Server Join Verification':
                        pass

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=1)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.send_message("Stopped configuring settings.", ephemeral=True)
                await self.end_interaction(interaction)

        ##########

        class PrefixMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = False

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            # noinspection PyTypeChecker
            @discord.ui.button(label='Set Prefix',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def set_prefix(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def prefix_prompt(listen_channel):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='New prefix',
                                            content='Please type the new prefix you would like to use.'))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Prefix configuration',
                                            content='Prefix configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    await sent_prompt.delete()
                    return mmsg

                await interaction.response.defer()
                new_prefix = await prefix_prompt(interaction.channel)

                if new_prefix:
                    log.info('New prefix entered, confirm workflow')
                    view = Confirm()
                    new_prefix_content = new_prefix.clean_content
                    await new_prefix.delete()
                    sent_message = await interaction.followup.send(
                        embed=gen_embed(title='Confirmation',
                                        content=('Please verify the contents before confirming:\n'
                                                 f' **New Prefix: {new_prefix_content}**')),
                        view=view)
                    prefix_timeout = await view.wait()
                    if prefix_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'prefix': new_prefix.clean_content}})
                        interaction.message.embeds[0].description = f'**Prefix: {new_prefix_content}**'
                        self.value = new_prefix_content
                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class AnnouncementMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.gray,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Enable/Disable',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def change_announce_state(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                doc = await db.servers.find_one({"server_id": interaction.guild_id})
                if doc['announcements']:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'announcements': False}})
                    interaction.message.embeds[0].description = 'Disabled'
                    self.value = 'Disabled'
                else:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'announcements': True}})
                    interaction.message.embeds[0].description = 'Enabled'
                    self.value = 'Enabled'

                if doc['announcement_channel']:
                    announce_channel = interaction.guild.get_channel(int(doc['announcement_channel']))
                    interaction.message.embeds[0].description = \
                        interaction.message.embeds[
                            0].description + f', configured in channel {announce_channel.mention}'
                    self.value = self.value + f' | Configured channel: #{announcement_channel.mention}'
                else:
                    interaction.message.embeds[0].description = \
                        interaction.message.embeds[0].description + f', no channel set, using default settings.'
                    self.value = self.value + ', no configured channel\n(Default public updates OR system channel)'

                await interaction.message.edit(embed=interaction.message.embeds[0])

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Channel',
                               style=discord.ButtonStyle.gray,
                               row=0)
            async def configure_announcement_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def announcement_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure announcement channel',
                                            content=('Please mention the channel you'
                                                     ' would like to use for announcements.')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Announcement channel configuration',
                                            content='Announcement channel configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    if prev_message:
                        await prev_message.delete()
                    await sent_prompt.delete()
                    if mmsg.channel_mentions:
                        return mmsg
                    else:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='No channel found. Please check that you mentioned the channel.')
                        )
                        await mmsg.delete()
                        attempts += 1
                        return await announcement_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                await interaction.response.defer()
                new_announcement = await announcement_prompt(interaction.channel)

                if new_announcement:
                    log.info('New announcement channel entered, confirm workflow')
                    view = Confirm()
                    new_announcement_channel = new_announcement.channel_mentions[0]
                    await new_announcement.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Announcement Channel: {new_announcement_channel.mention}**')),
                        view=view)
                    announcement_timeout = await view.wait()
                    if announcement_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'announcement_channel': new_announcement_channel.id}})

                        doc = await db.servers.find_one({"server_id": interaction.guild_id})
                        if doc['announcements']:
                            interaction.message.embeds[0].description = ('Enabled, configured in channel '
                                                                         f'{new_announcement_channel.mention}')
                            self.value = f'Disabled | Configured channel: {new_announcement_channel.mention}'
                        else:
                            interaction.message.embeds[0].description = ('Disabled, configured in channel '
                                                                         f'{new_announcement_channel.mention}')
                            self.value = f'Enabled | Configured channel: {new_announcement_channel.mention}'

                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class ModmailMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            async def modmail_channel_prompt(self, interaction, listen_channel, scenario, attempts=1,
                                             prev_message=None):
                def check(m):
                    return m.author == interaction.user and m.channel == listen_channel

                sent_prompt = None
                match scenario:
                    case 1:
                        try:
                            sent_prompt = await listen_channel.send(
                                embed=gen_embed(title='Configure modmail destination channel',
                                                content='Plase mention the channel you would like to use for modmail.')
                            )
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(['Send Messages'],
                                                                 'Forbidden 403 - could not send message to user.')
                    case 2:
                        try:
                            sent_prompt = await listen_channel.send(
                                embed=gen_embed(title='Configure modmail button channel',
                                                content='Plase mention the channel you would like to put the button.')
                            )
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(['Send Messages'],
                                                                 'Forbidden 403 - could not send message to user.')

                try:
                    mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                except asyncio.TimeoutError:
                    await sent_prompt.delete()
                    await interaction.followup.send(
                        embed=gen_embed(title='Modmail channel configuration',
                                        content='Modmail channel configuration has been cancelled.'),
                        ephemeral=True)
                    return None
                if prev_message:
                    await prev_message.delete()
                await sent_prompt.delete()
                if mmsg.channel_mentions:
                    return mmsg
                else:
                    sent_error = await interaction.followup.send(
                        embed=gen_embed(title='Error',
                                        content='No channel found. Please check that you mentioned the channel.')
                    )
                    await mmsg.delete()
                    attempts += 1
                    return await self.modmail_channel_prompt(interaction,
                                                             listen_channel,
                                                             scenario,
                                                             attempts=attempts,
                                                             prev_message=sent_error)

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            # noinspection PyTypeChecker
            @discord.ui.button(label='Enable/Disable',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def change_modmail_state(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()

                doc = await db.servers.find_one({"server_id": interaction.guild_id})
                if doc['modmail_channel']:
                    prev_button_channel = interaction.guild.get_channel(int(doc['modmail_button_channel']))
                    if doc['prev_message_modmail']:
                        try:
                            prev_button = await prev_button_channel.fetch_message(int(doc['prev_message_modmail']))
                            await prev_button.delete()
                        except discord.NotFound:
                            pass
                        except discord.Forbidden:
                            await interaction.followup.send(embed=gen_embed(
                                title='Error while fetching previous button',
                                content='I was unable to fetch the required message. Please check my permissions!'),
                                ephemeral=True)
                            return
                        except discord.HTTPException as error:
                            await interaction.followup.send(embed=gen_embed(
                                title='Error while fetching previous button',
                                content=(f'I was unable to fetch the required message. HTTP Error {error.status}'
                                         "\nThis is likely an error on Discord's end. Please try again later.")),
                                ephemeral=True)
                            return
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'modmail_channel': None,
                                                          'modmail_button_channel': None}})
                    interaction.message.embeds[0].description = '**Disabled**'
                    self.value = 'Disabled'
                    self.children[1].disabled = True
                    self.children[2].disabled = True
                else:
                    setup_phase1_success = False
                    setup_phase2_success = False
                    log.info('Begin modmail configuration workflow')

                    new_destination = await self.modmail_channel_prompt(interaction, interaction.channel, 1)
                    if new_destination:
                        log.info('New modmail dest entered, confirm workflow')
                        view = Confirm()
                        new_destination_channel = new_destination.channel_mentions[0]
                        await new_destination.delete()
                        sent_message = await interaction.followup.send(embed=gen_embed(
                            title='Confirmation',
                            content=('Pleae verify the contents before confirming:\n'
                                     f'**Selected Modmail Destination: {new_destination_channel.mention}**')),
                            view=view)
                        destination_timeout = await view.wait()
                        if destination_timeout:
                            log.info('Confirmation view timed out')
                            await sent_message.delete()
                            return
                        await sent_message.delete()

                        if view.value:
                            log.info('Phase 1 workflow confirm')
                            setup_phase1_success = True
                        else:
                            return

                    new_button = await self.modmail_channel_prompt(interaction, interaction.channel, 2)
                    if new_button:
                        log.info('New modmail button entered, confirm workflow')
                        view = Confirm()
                        new_button_channel = new_button.channel_mentions[0]
                        await new_button.delete()
                        sent_message = await interaction.followup.send(embed=gen_embed(
                            title='Confirmation',
                            content=('Pleae verify the contents before confirming:\n'
                                     f'**Selected Button Channel: {new_button_channel.mention}**')),
                            view=view)
                        button_timeout = await view.wait()
                        if button_timeout:
                            log.info('Confirmation view timed out')
                            await sent_message.delete()
                            return
                        await sent_message.delete()

                        if view.value:
                            log.info('Phase 2 workflow confirm')
                            setup_phase2_success = True
                        else:
                            return

                    if setup_phase1_success and setup_phase2_success:
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'modmail_channel': new_destination_channel.id,
                                                              'modmail_button_channel': new_button_channel.id}})
                        new_description = (f'**Enabled** \n Destination channel: {new_destination_channel.mention}'
                                           f'\n Button channel: {new_button_channel.mention}')
                        interaction.message.embeds[0].description = new_description
                        self.value = 'Enabled'
                        self.children[1].disabled = False
                        self.children[2].disabled = False
                        # TODO: run modmail button initialization

                await interaction.message.edit(embed=interaction.message.embeds[0], view=self)

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Destination Channel',
                               style=discord.ButtonStyle.gray,
                               row=1)
            async def configure_dest_modmail_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()

                new_destination = await self.modmail_channel_prompt(interaction, interaction.channel, 1)
                if new_destination:
                    log.info('New modmail dest entered, confirm workflow')
                    view = Confirm()
                    new_destination_channel = new_destination.channel_mentions[0]
                    await new_destination.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Pleae verify the contents before confirming:\n'
                                 f'**Selected Modmail Destination: {new_destination_channel.mention}**')),
                        view=view)
                    destination_timeout = await view.wait()
                    if destination_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'modmail_channel': new_destination_channel.id}})
                        doc = await db.servers.find_one({"server_id": interaction.guild_id})
                        modmail_button_channel = interaction.guild.get_channel(int(doc['modmail_button_channel']))
                        interaction.message.embeds[0].description = ('**Enabled** \nDestination channel:'
                                                                     f'{new_destination_channel.mention}'
                                                                     f'\nButton channel:'
                                                                     f'{modmail_button_channel.mention}')
                        await interaction.message.edit(embed=interaction.message.embeds[0])

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Button Channel',
                               style=discord.ButtonStyle.gray,
                               row=1)
            async def configure_button_modmail_channel(self, button: discord.ui.Button,
                                                       interaction: discord.Interaction):
                await interaction.response.defer()

                new_button = await self.modmail_channel_prompt(interaction, interaction.channel, 2)
                if new_button:
                    log.info('New modmail button entered, confirm workflow')
                    view = Confirm()
                    new_button_channel = new_button.channel_mentions[0]
                    await new_button.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Modmail Button Channel: {new_button_channel.mention}**')),
                        view=view)
                    button_timeout = await view.wait()
                    if button_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'modmail_button_channel': new_button_channel.id}})
                        doc = await db.servers.find_one({"server_id": interaction.guild_id})
                        m_modmail_channel = interaction.guild.get_channel(int(doc['modmail_channel']))
                        interaction.message.embeds[0].description = ('**Enabled** \nDestination channel:'
                                                                     f'{m_modmail_channel.mention}'
                                                                     f'\nButton channel:'
                                                                     f'{new_button_channel.mention}')
                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class ChatMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Enable/Disable',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def change_chat_state(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                doc = await db.servers.find_one({"server_id": interaction.guild_id})
                if doc['chat']:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'chat': False}})
                    interaction.message.embeds[0].description = 'Disabled'
                    self.value = 'Disabled'
                else:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'chat': True}})
                    interaction.message.embeds[0].description = 'Enabled'
                    self.value = 'Enabled'

                await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class BWListMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Enable/Disable',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def change_list_state(self, button: discord.ui.Button, interaction: discord.Interaction):
                class ListSelect(discord.ui.View):
                    def __init__(self):
                        super().__init__()
                        self.value = None

                    async def interaction_check(self,
                                                s_interaction: discord.Interaction) -> bool:
                        return s_interaction.user == interaction.user

                    async def end_interaction(self,
                                              s_interaction: discord.Interaction):
                        view = discord.ui.View.from_message(s_interaction.message)
                        for child in view.children:
                            child.disabled = True

                        await s_interaction.message.edit(view=view)
                        self.stop()

                    @discord.ui.select(placeholder="Choose the type of list filter for the chat feature...",
                                       min_values=1,
                                       max_values=1,
                                       row=1,
                                       options=[
                                           discord.SelectOption(label="Blacklist",
                                                                description="Choose channels to exclude from chat "
                                                                            "feature",
                                                                emoji="⬛"),
                                           discord.SelectOption(label="Whitelist",
                                                                description="Choose channels to include in chat "
                                                                            "feature",
                                                                emoji="⬜")
                                       ])
                    async def select_menu(self, select: discord.ui.Select, s_interaction: discord.Interaction):
                        await s_interaction.response.defer()
                        self.value = select.values[0]
                        await self.end_interaction(s_interaction)

                await interaction.response.defer()
                doc = await db.servers.find_one({"server_id": interaction.guild_id})
                if doc['blacklist']:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'blacklist': None}})
                    interaction.message.embeds[0].description = 'Disabled'
                    self.value = 'Disabled'
                    await interaction.message.edit(embed=interaction.message.embeds[0])
                elif doc['whitelist']:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'whitelist': None}})
                    interaction.message.embeds[0].description = 'Disabled'
                    self.value = 'Disabled'
                    await interaction.message.edit(embed=interaction.message.embeds[0])
                else:
                    select_view = ListSelect()
                    await interaction.message.edit(view=select_view)
                    await select_view.wait()

                    if select_view.value == 'Blacklist':
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'blacklist': []}})
                        interaction.message.embeds[0].description = 'Blacklist enabled. No active channels.'
                        self.value = 'Blacklist enabled for the following channels: '
                    if select_view.value == 'Whitelist':
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'whitelist': []}})
                        interaction.message.embeds[0].description = 'Whitelist enabled. No active channels.'
                        self.value = 'Whitelist enabled for the following channels: '

                    await interaction.message.edit(embed=interaction.message.embeds[0],
                                                   view=self)

        ##########

        class FunMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Enable/Disable',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def change_fun_state(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                doc = await db.servers.find_one({"server_id": interaction.guild_id})
                if doc['chat']:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'fun': False}})
                    interaction.message.embeds[0].description = 'Disabled'
                    self.value = 'Disabled'
                else:
                    await db.servers.update_one({"server_id": interaction.guild_id},
                                                {"$set": {'fun': True}})
                    interaction.message.embeds[0].description = 'Enabled'
                    self.value = 'Enabled'

                await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class LogSelect(discord.ui.Select):
            def __init__(self, bot, defaults):
                self.bot = bot
                options = []
                if defaults['log_messages']:
                    options.append(
                        discord.SelectOption(label='Messages',
                                             description='Log message edits and deletion',
                                             default=True))
                else:
                    options.append(
                        discord.SelectOption(label='Messages',
                                             description='Log message edits and deletion',
                                             default=False))
                if defaults['log_joinleaves']:
                    options.append(
                        discord.SelectOption(label='Joins/Leaves',
                                             description='Log member joins & leaves',
                                             default=True))
                else:
                    options.append(
                        discord.SelectOption(label='Joins/Leaves',
                                             description='Log member joins & leaves',
                                             default=False))
                if defaults['log_kbm']:
                    options.append(
                        discord.SelectOption(label='KBM',
                                             description='Log kicks, bans, and timeouts/mutes',
                                             default=True))
                else:
                    options.append(
                        discord.SelectOption(label='KBM',
                                             description='Log kicks, bans, and timeouts/mutes',
                                             default=False))
                if defaults['log_strikes']:
                    options.append(
                        discord.SelectOption(label='Strikes',
                                             description='Log strikes',
                                             default=True))
                else:
                    options.append(
                        discord.SelectOption(label='Strikes',
                                             description='Log strikes',
                                             default=False))
                super().__init__(custom_id='logselect',
                                 placeholder='Pick the settings you wish to enable',
                                 min_values=1,
                                 max_values=4,
                                 row=0,
                                 options=options)

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()

        class LogMenu(discord.ui.View):
            def __init__(self, og_context, bot, config_channel, defaults):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.channel = config_channel
                self.value = ''
                self.select_values = None
                self.defaults = defaults

                self.add_item(LogSelect(self.bot, defaults))

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=1)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                post = {'log_messages': False,
                        'log_joinleaves': False,
                        'log_kbm': False,
                        'log_strikes': False}
                for child in self.children:
                    if child.custom_id == 'logselect':
                        self.select_values = child.values
                        if len(self.select_values) == 0:
                            if self.defaults['log_messages']:
                                post['log_messages'] = True
                            if self.defaults['log_joinleaves']:
                                post['log_joinleaves'] = True
                            if self.defaults['log_kbm']:
                                post['log_kbm'] = True
                            if self.defaults['log_strikes']:
                                post['log_strikes'] = True
                for option in self.select_values:
                    match option:
                        case 'Messages':
                            post['log_messages'] = True
                        case 'Joins/Leaves':
                            post['log_joinleaves'] = True
                        case 'KBM':
                            post['log_kbm'] = True
                        case 'Strikes':
                            post['log_strikes'] = True
                await db.servers.update_one({"server_id": interaction.guild_id},
                                            {"$set": post})
                embed_text = 'Configured channel: '
                if self.channel:
                    embed_text += f'{self.channel.mention}\n'
                else:
                    embed_text += 'None\n'
                embed_text += '\nLog messages: ' + f"{'Enabled' if post['log_messages'] else 'Disabled'}"
                embed_text += '\nLog member join/leaves: ' + f"{'Enabled' if post['log_joinleaves'] else 'Disabled'}"
                embed_text += '\nLog kicks/bans/timeouts: ' + f"{'Enabled' if post['log_kbm'] else 'Disabled'}"
                embed_text += '\nLog strikes: ' + f"{'Enabled' if post['log_strikes'] else 'Disabled'}"
                self.value = embed_text
                await self.end_interaction(interaction)

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Channel',
                               style=discord.ButtonStyle.gray,
                               row=1)
            async def configure_log_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def log_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure log channel',
                                            content=('Please mention the channel you'
                                                     ' would like to use for logging.')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Log channel configuration',
                                            content='Log channel configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    if prev_message:
                        await prev_message.delete()
                    await sent_prompt.delete()
                    if mmsg.channel_mentions:
                        return mmsg
                    else:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='No channel found. Please check that you mentioned the channel.')
                        )
                        await mmsg.delete()
                        attempts += 1
                        return await log_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                await interaction.response.defer()
                new_log = await log_prompt(interaction.channel)

                if new_log:
                    log.info('New log channel entered, confirm workflow')
                    view = Confirm()
                    new_log_channel = new_log.channel_mentions[0]
                    await new_log.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Log Channel: {new_log_channel.mention}**')),
                        view=view)
                    log_timeout = await view.wait()
                    if log_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'log_channel': new_log_channel.id}})

                        doc = await db.servers.find_one({"server_id": interaction.guild_id})
                        log_messages = doc['log_messages']
                        log_joinleaves = doc['log_joinleaves']
                        log_kbm = doc['log_kbm']
                        log_strikes = doc['log_strikes']
                        if not log_messages and not log_joinleaves and not log_kbm and not log_strikes:
                            interaction.message.embeds[0].description = ('Disabled | Configured Channel: '
                                                                         f'{new_log_channel.mention}')
                            self.channel = new_log_channel
                        else:
                            interaction.message.embeds[0].description = ('Enabled | Configured Channel: '
                                                                         f'{new_log_channel.mention}')
                            self.channel = new_log_channel
                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class AutoRoleMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Disable',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def disable_autorole(self, button: discord.ui.Button, interaction: discord.Interaction):
                await db.servers.update_one({"server_id": interaction.guild_id},
                                            {"$set": {'autorole': None}})
                interaction.message.embeds[0].description = 'Disabled'
                self.value = 'Disabled'
                await interaction.message.edit(embed=interaction.message.embeds[0])

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Role',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def configure_autorole(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def autorole_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure auto assign role',
                                            content=('Please enter the role you would like to use.\n\n'
                                                     'Accepted inputs: role mention, id, role name (case sensitive)')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Auto assign role configuration',
                                            content='Auto assign role configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    if prev_message:
                        await prev_message.delete()
                    await sent_prompt.delete()
                    try:
                        converter = commands.RoleConverter()
                        msg_content = await converter.convert(self.context, mmsg.content)
                        await mmsg.delete()
                        return msg_content
                    except commands.RoleNotFound:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='Role not found. Please check that you have the correct role.')
                        )
                        await mmsg.delete()
                        attempts += 1
                        return await autorole_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                await interaction.response.defer()
                new_role = await autorole_prompt(interaction.channel)

                if new_role:
                    log.info('New auto role entered, confirm workflow')
                    view = Confirm()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Role: {new_role.mention} (ID: {new_role.id})')),
                        view=view)
                    role_timeout = await view.wait()
                    if role_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'autorole': new_role.id}})
                        interaction.message.embeds[0].description = f'Enabled for role {new_role.mention}'
                        self.value = f'Enabled for role {new_role.mention}'
                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ##########

        class ModRoleMenu(discord.ui.View):
            def __init__(self, og_context, bot):
                super().__init__()
                self.context = og_context
                self.bot = bot
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Disable',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def disable_modrole(self, button: discord.ui.Button, interaction: discord.Interaction):
                await db.servers.update_one({"server_id": interaction.guild_id},
                                            {"$set": {'modrole': None}})
                interaction.message.embeds[0].description = 'Disabled'
                self.value = 'Disabled'
                await interaction.message.edit(embed=interaction.message.embeds[0])

            # noinspection PyTypeChecker
            @discord.ui.button(label='Configure Role',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def configure_modrole(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def modrole_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure moderator role',
                                            content=('Please enter the role you would like to use.\n\n'
                                                     'Accepted inputs: role mention, id, role name (case sensitive)')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Moderator role configuration',
                                            content='Moderator role configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    if prev_message:
                        await prev_message.delete()
                    await sent_prompt.delete()
                    try:
                        converter = commands.RoleConverter()
                        msg_content = await converter.convert(self.context, mmsg.content)
                        await mmsg.delete()
                        return msg_content
                    except commands.RoleNotFound:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='Role not found. Please check that you have the correct role.')
                        )
                        await mmsg.delete()
                        attempts += 1
                        return await modrole_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                await interaction.response.defer()
                new_role = await modrole_prompt(interaction.channel)

                if new_role:
                    log.info('New auto role entered, confirm workflow')
                    view = Confirm()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Role: {new_role.mention} (ID: {new_role.id})')),
                        view=view)
                    role_timeout = await view.wait()
                    if role_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild_id},
                                                    {"$set": {'modrole': new_role.id}})
                        interaction.message.embeds[0].description = f'Enabled for role {new_role.mention}'
                        self.value = f'Enabled for role {new_role.mention}'
                        await interaction.message.edit(embed=interaction.message.embeds[0])

        ####################

        await ctx.interaction.response.defer()
        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})

        embed = gen_embed(name='Settings',
                          content='You can configure the settings for Kanon Bot using the select dropdown below.')

        embed.add_field(name='Prefix',
                        value=f"{document['prefix'] or '%'}",
                        inline=False)

        embed_text = ', no configured channel\n(Default public updates OR system channel)'
        if document['announcement_channel']:
            announcement_channel = ctx.guild.get_channel(int(document['announcement_channel']))
            embed_text = f' | Configured channel: {announcement_channel.mention}'
        embed.add_field(name='Global Announcements',
                        value=f"{'Enabled' if document['announcements'] else 'Disabled'}"
                              f'{embed_text}',
                        inline=False)

        modmail_channel = None
        button_channel = None
        if document['modmail_channel']:
            modmail_channel = ctx.guild.get_channel(int(document['modmail_channel']))
        if document['modmail_button_channel']:
            button_channel = ctx.guild.get_channel(int(document['modmail_button_channel']))
        embed.add_field(name='Modmail',
                        value=f"{'Enabled' if document['modmail_channel'] else 'Disabled'}"
                              f"\n{('Destination channel: ' + modmail_channel.mention) if modmail_channel else ''}"
                              f"\n{('Button channel: ' + button_channel.mention) if button_channel else ''}",
                        inline=False)

        embed.add_field(name='Chat Feature',
                        value=f"{'Enabled' if document['chat'] else 'Disabled'}")

        embed_text = 'Disabled'
        if blacklist := document['blacklist']:
            embed_text = 'Blacklist enabled for the following channels: '
            for channel in blacklist:
                channel = ctx.guild.get_channel(channel)
                embed_text += f'{channel.mention} '
        elif whitelist := document['whitelist']:
            embed_text = 'Whitelist enabled for the following channels: '
            for channel in whitelist:
                channel = ctx.guild.get_channel(channel)
                embed_text += f'{channel.mention} '
        embed.add_field(name='Blacklist/Whitelist',
                        value=f'{embed_text}',
                        inline=False)

        embed.add_field(name='Fun Features',
                        value=f"{'Enabled' if document['fun'] else 'Disabled'}",
                        inline=False)

        embed_text = 'Configured channel: '
        if document['log_channel']:
            logging_channel = ctx.guild.get_channel(int(document['log_channel']))
            embed_text += f'{logging_channel.mention}\n'
        else:
            embed_text += 'None\n'
        embed_text += '\nLog messages: ' + f"{'Enabled' if document['log_messages'] else 'Disabled'}"
        embed_text += '\nLog member join/leaves: ' + f"{'Enabled' if document['log_joinleaves'] else 'Disabled'}"
        embed_text += '\nLog kicks/bans/timeouts: ' + f"{'Enabled' if document['log_kbm'] else 'Disabled'}"
        embed_text += '\nLog strikes: ' + f"{'Enabled' if document['log_strikes'] else 'Disabled'}"
        embed.add_field(name='Logging',
                        value=f'{embed_text}',
                        inline=False)

        if document['autorole']:
            auto_role = ctx.guild.get_role(int(document['autorole']))
            embed_text = f'Enabled for role {auto_role.mention}'
        else:
            embed_text = 'Disabled'
        embed.add_field(name='Auto Assign Role On Join',
                        value=f'{embed_text}',
                        inline=False)

        if document['modrole']:
            mod_role = ctx.guild.get_role(int(document['modrole']))
            embed_text = f'Enabled for role {mod_role.mention}'
        else:
            embed_text = 'Disabled'
        embed.add_field(name='Moderator Role',
                        value=f'{embed_text}',
                        inline=False)

        embed.add_field(name='Server Join Verification',
                        value=f"Not implemented yet",
                        inline=False)

        main_menu_view = SettingsMenu(ctx, embed, self.bot)
        sent_menu_message = await ctx.interaction.followup.send(embed=embed,
                                                                view=main_menu_view,
                                                                ephemeral=True)
        timeout = await main_menu_view.wait()
        if timeout:
            for item in main_menu_view.children:
                item.disabled = True
            await sent_menu_message.edit(embed=embed,
                                         view=main_menu_view)

    blacklist = SlashCommandGroup('blacklist', 'Configure blacklist channels')

    @blacklist.command(name='add',
                       description='Add channel to the blacklist')
    @default_permissions(manage_guild=True)
    async def blacklist_add(self,
                            ctx: discord.ApplicationContext,
                            channel: Option(discord.TextChannel, 'Channel to add to the blacklist')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.servers.find_one({"server_id": ctx.guild_id})
        if blacklist := document['blacklist']:
            if channel.id not in blacklist:
                blacklist.append(channel.id)
                await db.servers.update_one({"server_id": ctx.guild_id},
                                            {"$set": {'blacklist': blacklist}})
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Add Channel to Blacklist',
                                                              content=f'Channel {channel.mention} has been added '
                                                                      f'to the blacklist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Add Channel to Blacklist',
                                                              content=f'Channel has already been added '
                                                                      f'to the blacklist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Add Channel to Blacklist',
                                                          content='Blacklist is not enabled!'),
                                                ephemeral=True)

    @blacklist.command(name='remove',
                       description='Remove channel from the blacklist')
    @default_permissions(manage_guild=True)
    async def blacklist_remove(self,
                               ctx: discord.ApplicationContext,
                               channel: Option(discord.TextChannel, 'Channel to remove from the blacklist')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.servers.find_one({"server_id": ctx.guild_id})
        if blacklist := document['blacklist']:
            if channel.id in blacklist:
                blacklist.remove(channel.id)
                await db.servers.update_one({"server_id": ctx.guild_id},
                                            {"$set": {'blacklist': blacklist}})
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Remove Channel from Blacklist',
                                                              content=f'Channel {channel.mention} has been removed '
                                                                      f'from the blacklist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Remove Channel from Blacklist',
                                                              content=f'Channel is not in the blacklist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Remove Channel from Blacklist',
                                                          content='Blacklist is not enabled!'),
                                                ephemeral=True)

    whitelist = SlashCommandGroup('whitelist', 'Configure whitelist channels')

    @whitelist.command(name='add',
                       description='Add channel to the whitelist')
    @default_permissions(manage_guild=True)
    async def whitelist_add(self,
                            ctx: discord.ApplicationContext,
                            channel: Option(discord.TextChannel, 'Channel to add to the whitelist')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.servers.find_one({"server_id": ctx.guild_id})
        if whitelist := document['whitelist']:
            if channel.id not in whitelist:
                whitelist.append(channel.id)
                await db.servers.update_one({"server_id": ctx.guild_id},
                                            {"$set": {'whitelist': whitelist}})
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Add channel to Whitelist',
                                                              content=f'Channel {channel.mention} has been added '
                                                                      f'to the whitelist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Add channel to Whitelist',
                                                              content=f'Channel has already been added '
                                                                      f'to the whitelist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Add channel to Whitelist',
                                                          content='Whitelist is not enabled!'),
                                                ephemeral=True)

    @whitelist.command(name='remove',
                       description='Remove channel from the whitelist')
    @default_permissions(manage_guild=True)
    async def whitelist_remove(self,
                               ctx: discord.ApplicationContext,
                               channel: Option(discord.TextChannel, 'Channel to remove from the whitelist')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.servers.find_one({"server_id": ctx.guild_id})
        if whitelist := document['whitelist']:
            if channel.id in whitelist:
                whitelist.remove(channel.id)
                await db.servers.update_one({"server_id": ctx.guild_id},
                                            {"$set": {'whitelist': whitelist}})
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Remove Channel from Whitelist',
                                                              content=f'Channel {channel.mention} has been removed '
                                                                      f'from the whitelist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Remove Channel from Whitelist',
                                                              content=f'Channel is not in the whitelist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Remove Channel from Whitelist',
                                                          content='Whitelist is not enabled!'),
                                                ephemeral=True)

    @discord.slash_command(name='purgeid',
                           description='Purge a single message by ID')
    @default_permissions(manage_messages=True)
    async def purgeid(self,
                      ctx: discord.ApplicationContext,
                      message: Option(discord.Message, 'Message to delete')):
        await ctx.interaction.response.defer(ephemeral=True)
        try:
            await message.delete()
            await ctx.interaction.followup.send(embed=gen_embed(title='Purge by ID',
                                                                content=f'Message {message.id} was deleted.'),
                                                ephemeral=True)
        except discord.Forbidden:
            raise commands.BotMissingPermissions(['Manage Messages'])
        except discord.NotFound:
            await ctx.interaction.followup.send('Message not found. It may already have been deleted.',
                                                ephemeral=True)
            return

    @discord.slash_command(name='purge',
                           description='Delete messages from the channel. Various filters exist')
    @default_permissions(manage_messages=True)
    async def purge(self,
                    ctx: discord.ApplicationContext,
                    number: Option(int, 'Specify to choose # of messages to search through',
                                   required=False,
                                   min_value=1,
                                   max_value=1000),
                    member: Option(discord.Member, 'Specify to only delete messages from this member',
                                   required=False),
                    time: Option(str, 'Specify to delete messages sent in the past duration',
                                 required=False)):
        async def delete_messages(limit=None, check=None, before=None, after=None):
            if check:
                deleted = await ctx.interaction.channel.purge(limit=limit, check=check, before=before, after=after)
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Purge Messages',
                                    content=(f'The last {len(deleted)} messages by {member.name}#{member.discriminator}'
                                             ' were deleted.')),
                    ephemeral=True)
            else:
                deleted = await ctx.interaction.channel.purge(limit=limit, before=before, after=after)
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Purge Messages', content=f'The last {len(deleted)} messages were deleted.'),
                    ephemeral=True)

        await ctx.interaction.response.defer(ephemeral=True)

        time_result = None
        if time:
            testing_text = ""
            for chunk in time.split():
                if chunk == "and":
                    continue
                if chunk.isdigit():
                    testing_text += chunk
                    continue
                testing_text += chunk.rstrip(",")
                parsed = parse_timedelta(testing_text, minimum=timedelta(seconds=1), maximum=timedelta(weeks=52))
                if parsed != time_result:
                    time_result = parsed
                else:
                    raise commands.UserInputError('Cannot parse the time entered.')

        # The following combinations are possible:
        # 1. Only number of messages provided
        # 2. # of messages and user is provided
        # 3. # of messages, user, and time is provided
        # 4. # of messages and time is provided
        # 5. User and time is provided
        # 6. Only User is provided (INVALID)
        # 7. Only Time is provided

        if number:
            if member:
                def user_check(m):
                    return m.author == member

                if time:
                    after_value = datetime.datetime.now(datetime.timezone.utc) - time_result
                    await delete_messages(limit=number,
                                          check=user_check,
                                          before=ctx.interaction.message,
                                          after=after_value)
                    return
                else:
                    await delete_messages(limit=number,
                                          check=user_check,
                                          before=ctx.interaction.message)
                    return
            else:
                if time:
                    after_value = datetime.datetime.now(datetime.timezone.utc) - time_result
                    await delete_messages(limit=number,
                                          before=ctx.interaction.message,
                                          after=after_value)
                    return
                else:
                    await delete_messages(limit=number,
                                          before=ctx.interaction.message)
                    return

        if member:
            def user_check(m):
                return m.author == member

            if time:
                after_value = datetime.datetime.now(datetime.timezone.utc) - time_result
                await delete_messages(check=user_check,
                                      before=ctx.interaction.message,
                                      after=after_value)
                return
        else:
            raise commands.UserInputError('lmao bad')

        if time:
            after_value = datetime.datetime.now(datetime.timezone.utc) - time_result
            await delete_messages(before=ctx.interaction.message,
                                  after=after_value)
            return

    @commands.command(name='purge',
                      description=('Deletes the previous # of messages from the channel. '
                                   'Specifying a user will delete the messages for that user. '
                                   'Specifying a time will delete messages from the past x amount of time. '
                                   'You can also reply to a message to delete messages after the one replied to.'),
                      help=('Usage\n\n%purge <user id/user mention/user name + discriminator (ex: name#0000)> '
                            '<num> <time/message id>\n(Optionally, you can reply to a message with the command '
                            'and it will delete ones after that message)'))
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def msgpurge(self, ctx, members: commands.Greedy[discord.Member], num: Optional[int],
                       time: Optional[Union[discord.Message, str]]):
        def convert_to_timedelta(s):
            return timedelta(**{UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val')) for m in
                                re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)})

        async def delete_messages(limit=None, check=None, before=None, after=None):
            if check:
                deleted = await ctx.channel.purge(limit=limit, check=check, before=before, after=after)
                sent = await ctx.send(embed=gen_embed(title='purge',
                                                      content=f'The last {len(deleted)} messages by {member.name}#{member.discriminator} were deleted.'))
                await ctx.message.delete()
                await sent.delete(delay=5)
            else:
                deleted = await ctx.channel.purge(limit=limit, before=before, after=after)
                sent = await ctx.send(
                    embed=gen_embed(title='purge', content=f'The last {len(deleted)} messages were deleted.'))
                await ctx.message.delete()
                await sent.delete(delay=5)

        time = time or ctx.message.reference

        if members:
            for member in members:
                def user_check(m):
                    return m.author == member

                if num:
                    if num < 0:
                        log.warning("Error: Invalid input")
                        await ctx.send(embed=gen_embed(title='Input Error',
                                                       content='That is not a valid option for this parameter. Please pick a number > 0.'))

                    else:
                        if time:
                            after_value = datetime.datetime.now(datetime.timezone.utc)
                            if isinstance(time, str):
                                after_value = after_value - convert_to_timedelta(time)
                            elif isinstance(time, discord.MessageReference):
                                after_value = await ctx.channel.fetch_message(time.message_id)

                            await delete_messages(limit=num, check=user_check, after=after_value)
                        else:
                            await delete_messages(limit=num, check=user_check)
                elif time:
                    after_value = datetime.datetime.now(datetime.timezone.utc)
                    if isinstance(time, str):
                        after_value = after_value - convert_to_timedelta(time)
                    elif isinstance(time, discord.MessageReference):
                        after_value = await ctx.channel.fetch_message(time.message_id)

                    await delete_messages(check=user_check, after=after_value)
            return
        elif num:
            if num < 0:
                log.warning("Error: Invalid input")
                sent = await ctx.send(embed=gen_embed(title='Input Error',
                                                      content='That is not a valid option for this parameter. Please pick a number > 0.'))
                await ctx.message.delete()
                await sent.delete(delay=5)
            else:
                if time:
                    after_value = datetime.datetime.now(datetime.timezone.utc)
                    if isinstance(time, str):
                        after_value = after_value - convert_to_timedelta(time)
                    elif isinstance(time, discord.MessageReference):
                        after_value = await ctx.channel.fetch_message(time.message_id)

                    await delete_messages(limit=num, after=after_value)
                    return

                else:
                    await delete_messages(limit=num, before=ctx.message)
                    return
        elif time:
            after_value = datetime.datetime.now(datetime.timezone.utc)
            if isinstance(time, str):
                after_value = after_value - convert_to_timedelta(time)
            elif isinstance(time, discord.MessageReference):
                after_value = await ctx.channel.fetch_message(time.message_id)

            await delete_messages(before=ctx.message, after=after_value)
            return
        else:
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            sent = await ctx.send(embed=gen_embed(title="Invalid parameter(s) entered",
                                                  content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            await ctx.message.delete()
            await sent.delete(delay=5)

    rolecommand = SlashCommandGroup('role', 'Add/remove roles and users to roles')

    async def role_color_autocomplete(self,
                                      ctx):
        return [color for color in COLORS if color.startswith(ctx.value.lower())]

    @rolecommand.command(name='create',
                         description='Create a new role')
    @default_permissions(manage_roles=True)
    async def createrole(self,
                         ctx: discord.ApplicationContext,
                         name: Option(str, 'Name of the role'),
                         color: Option(str, 'Role color. Accepts hex color codes (#ffffff).',
                                       required=False,
                                       autocomplete=role_color_autocomplete)):
        def hex_to_rgb(value):
            value = value.strip()
            regex = re.compile('^#[0-9a-fA-F]{6}$')
            if regex.match(value):
                value = value.lstrip('#')
                lv = len(value)
                return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
            else:
                raise commands.UserInputError(message='This is not a valid hex code!')

        await ctx.interaction.response.defer(ephemeral=True)
        role_permissions = ctx.guild.default_role.permissions
        if color:
            if color in COLORS:
                role_color = eval('discord.Colour.' + color + "()")
            else:
                role_color = hex_to_rgb(color)
                for num in role_color:
                    if num > 255 or num < 0:
                        raise commands.BadArgument(message='This is not a valid color!')
                role_color = discord.Colour.from_rgb(role_color[0], role_color[1], role_color[2])
        else:
            role_color = discord.Colour.random()

        role = await ctx.guild.create_role(name=name, permissions=role_permissions, colour=role_color)
        await ctx.interaction.followup.send(embed=gen_embed(title='Role Creation',
                                                            content=f'Role {role.mention} has been created!'),
                                            ephemeral=True)

        # Technically optional so we can just ignore errors here
        await role.edit(position=1)

    @rolecommand.command(name='delete',
                         description='Delete a role')
    @default_permissions(manage_roles=True)
    async def deleterole(self,
                         ctx: discord.ApplicationContext,
                         role: Option(discord.Role, 'Role to delete')):
        await ctx.interaction.response.defer(ephemeral=True)
        role_name = role.name
        await role.delete(reason=f'Deleted by {ctx.interaction.user.name}#{ctx.interaction.user.discriminator}')
        await ctx.interaction.followup.send(embed=gen_embed(title='Role Deletion',
                                                            content=f'Role {role_name} has been deleted.'),
                                            ephemeral=True)

    add_user_action = rolecommand.create_subgroup('add', 'Add user actions')
    remove_user_action = rolecommand.create_subgroup('remove', 'Remove user actions')

    @add_user_action.command(name='user',
                             description='Add user to role')
    @default_permissions(manage_roles=True)
    async def adduser(self,
                      ctx: discord.ApplicationContext,
                      user: Option(discord.Member, 'User to add to role'),
                      role: Option(discord.Role, 'Role to add user to')):
        await ctx.interaction.response.defer(ephemeral=True)
        await user.add_roles(role)
        await ctx.interaction.followup.send(embed=gen_embed(title='Add User to Role',
                                                            content=(f'{user.mention} has been added'
                                                                     f' to role {role.mention}')),
                                            ephemeral=True)

    @remove_user_action.command(name='user',
                                description='Remove user from role')
    @default_permissions(manage_roles=True)
    async def removeuser(self,
                         ctx: discord.ApplicationContext,
                         user: Option(discord.Member, 'User to remove from role'),
                         role: Option(discord.Role, 'Role to remove user from')):
        await ctx.interaction.response.defer(ephemeral=True)
        await user.remove_roles(role)
        await ctx.interaction.followup.send(embed=gen_embed(title='Remove User from Role',
                                                            content=(f'{user.mention} has been removed'
                                                                     f' from role {role.mention}')),
                                            ephemeral=True)

    timeout = SlashCommandGroup('timeout', 'Set/remove timeout on a user')

    @timeout.command(name='set',
                     description='Timeout a user')
    @default_permissions(moderate_members=True)
    async def set_timeout(self,
                          ctx: discord.ApplicationContext,
                          user: Option(discord.Member, 'User to timeout'),
                          length: Option(str, 'Amount of time to timeout'),
                          reason: Option(str, 'Reason for timeout',
                                         required=False)):
        await ctx.interaction.response.defer(ephemeral=True)

        time_result = None
        testing_text = ""
        for chunk in length.split():
            if chunk == "and":
                continue
            if chunk.isdigit():
                testing_text += chunk
                continue
            testing_text += chunk.rstrip(",")
            parsed = parse_timedelta(testing_text, minimum=timedelta(seconds=1), maximum=timedelta(days=28))
            log.info(parsed)
            if parsed is not None:
                time_result = parsed
            else:
                raise commands.UserInputError('Cannot parse the time entered.')
        if time_result is None:
            raise commands.UserInputError('Cannot parse the time entered.')

        if reason:
            await user.timeout_for(time_result, reason=reason[:512])
        else:
            await user.timeout_for(time_result)

        dm_channel = user.dm_channel
        if user.dm_channel is None:
            dm_channel = await user.create_dm()

        dm_embed = None
        if m := await modmail_enabled(ctx):
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title=(f'You have been put in timeout. Your timeout will last for'
                                        f' {humanize_timedelta(timedelta=time_result)}'),
                                 content=(f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply'
                                          ' function) to this message and send a modmail.'))
            dm_embed.set_footer(text=ctx.interaction.guild_id)
        else:
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title=(f'You have been put in timeout. Your timeout will last for'
                                        f' {humanize_timedelta(timedelta=time_result)}'),
                                 content=f'Reason: {reason}')
            dm_embed.set_footer(text=time.ctime())

        try:
            await dm_channel.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.interaction.followup.send(embed=gen_embed(title='Warning',
                                                                content=('This user does not accept DMs. I could not'
                                                                         ' send them the message, but I will proceed'
                                                                         ' with putting the user in timeout.')),
                                                ephemeral=True)

        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
        if document['log_channel'] and document['log_kbm']:
            log_channel = ctx.guild.get_channel(int(document['log_channel']))
            await log_channel.send(embed=gen_embed(title='Timeout User',
                                                   content=(f'{user.mention} has been put in timeout for'
                                                            f' {humanize_timedelta(timedelta=time_result)}.'
                                                            f' \n\nReason: {reason}')))
        await ctx.interaction.followup.send(embed=gen_embed(title='Timeout User',
                                                            content=(f'{user.mention} has been put in timeout for'
                                                                     f' {humanize_timedelta(timedelta=time_result)}.'
                                                                     f' \n\nReason: {reason}')),
                                            ephemeral=True)

    @timeout.command(name='remove',
                     description='Remove timeout from a user')
    @default_permissions(moderate_members=True)
    async def remove_timeout(self,
                             ctx: discord.ApplicationContext,
                             user: Option(discord.Member, 'User to remove timeout from')):
        await ctx.interaction.response.defer(ephemeral=True)
        await user.remove_timeout(reason='Invoked by slash command')

        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
        if document['log_channel'] and document['log_kbm']:
            log_channel = ctx.guild.get_channel(int(document['log_channel']))
            await log_channel.send(embed=gen_embed(title='Remove Timeout from User',
                                                   content=(f'{user.mention} has had their timeout removed by'
                                                            f' {ctx.interaction.user.mention}.')))
        await ctx.interaction.followup.send(embed=gen_embed(title='Remove Timeout from User',
                                                            content=f'Removed timeout from {user.mention}.'),
                                            ephemeral=True)

    @discord.slash_command(name='kick',
                           description='Kick a user and send a modmail (if enabled)')
    @default_permissions(kick_members=True)
    async def kick(self,
                   ctx: discord.ApplicationContext,
                   user: Option(discord.User, 'User to kick'),
                   reason: Option(str, 'Reason for kick',
                                  required=False)):
        await ctx.interaction.response.defer(ephemeral=True)

        dm_channel = user.dm_channel
        if user.dm_channel is None:
            dm_channel = await user.create_dm()

        m = await modmail_enabled(ctx)
        dm_embed = None
        if m:
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title='You have been kicked',
                                 content=(f'Reason: {reason}\n\nIf you have any issues, you may reply '
                                          ' (use the reply function) to this message and send a modmail.'))
            dm_embed.set_footer(text=ctx.guild.id)
        else:
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title='You have been kicked',
                                 content=f'Reason: {reason}')
            dm_embed.set_footer(text=time.ctime())

        try:
            await dm_channel.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.interaction.followup.send(embed=gen_embed(title='Warning',
                                                                content=('This user does not accept DMs. I could not'
                                                                         ' send them the message, but I will proceed'
                                                                         ' with kicking the user.')),
                                                ephemeral=True)

        if reason:
            await ctx.guild.kick(user, reason=reason[:512])
        else:
            await ctx.guild.kick(user)

        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
        if document['log_channel'] and document['log_kbm']:
            log_channel = ctx.guild.get_channel(int(document['log_channel']))
            await log_channel.send(embed=
                                   gen_embed(title='Kick User',
                                             content=(f'{user.name}#{user.discriminator} has been kicked by'
                                                      f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator}'
                                                      f'\nReason: {reason if reason else "None"}')))

        await ctx.interaction.followup.send(embed=gen_embed(title='Kick User',
                                                            content=(
                                                                f'{user.name}#{user.discriminator} has been kicked.'
                                                                f'\nReason: {reason if reason else "None"}')),
                                            ephemeral=True)

    @discord.slash_command(name='ban',
                           description='Ban a user and send a modmail (if enabled)')
    @default_permissions(ban_members=True)
    async def ban(self,
                  ctx: discord.ApplicationContext,
                  user: Option(discord.User, 'User to ban'),
                  days: Option(int, 'Number of days worth of messages to delete',
                               min_value=0,
                               max_value=7),
                  reason: Option(str, 'Reason for ban',
                                 required=False)):
        await ctx.interaction.response.defer(ephemeral=True)

        dm_channel = user.dm_channel
        if user.dm_channel is None:
            dm_channel = await user.create_dm()

        m = await modmail_enabled(ctx)
        dm_embed = None
        if m:
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title='You have been Banned',
                                 content=(f'Reason: {reason}\n\nIf you have any issues, you may reply '
                                          ' (use the reply function) to this message and send a modmail.'))
            dm_embed.set_footer(text=ctx.guild.id)
        else:
            dm_embed = gen_embed(name=ctx.guild.name,
                                 icon_url=ctx.guild.icon.url,
                                 title='You have been banned',
                                 content=f'Reason: {reason}')
            dm_embed.set_footer(text=time.ctime())

        try:
            await dm_channel.send(embed=dm_embed)
        except discord.Forbidden:
            await ctx.interaction.followup.send(embed=gen_embed(title='Warning',
                                                                content=('This user does not accept DMs. I could not'
                                                                         ' send them the message, but I will proceed'
                                                                         ' with banning the user.')),
                                                ephemeral=True)

        if reason:
            await ctx.guild.ban(user, reason=reason[:512], delete_message_days=days)
        else:
            await ctx.guild.ban(user, delete_message_days=days)

        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
        if document['log_channel'] and document['log_kbm']:
            log_channel = ctx.guild.get_channel(int(document['log_channel']))
            await log_channel.send(embed=
                                   gen_embed(title='Ban User',
                                             content=(f'{user.name}#{user.discriminator} has been banned by'
                                                      f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator}'
                                                      f'\nReason: {reason if reason else "None"}')))

        await ctx.interaction.followup.send(embed=gen_embed(title='Ban User',
                                                            content=(
                                                                f'{user.name}#{user.discriminator} has been banned.'
                                                                f'\nReason: {reason if reason else "None"}')),
                                            ephemeral=True)

    @discord.slash_command(name='strike',
                           description='Strike a user. After 3 strikes, the user is automatically banned.')
    @default_permissions(ban_members=True)
    async def strike(self,
                     ctx: discord.ApplicationContext,
                     user: Option(discord.Member, 'Member to strike')):
        class Cancel(discord.ui.Button):
            def __init__(self, context):
                super().__init__(label="Cancel", style=discord.ButtonStyle.danger)
                self.value = None
                self.context = context

            async def interaction_check(self, interaction):
                if interaction.user != self.context.author:
                    return False
                return True

            async def callback(self, interaction):
                # await interaction.response.send_message("Cancelled Operation.", ephemeral=True)
                await interaction.response.defer()
                for item in self.view.children:
                    item.disabled = True
                self.value = True
                self.view.stop()

        class Confirm(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.value = None

            # When the confirm button is pressed, set the inner value to `True` and
            # stop the View from listening to more input.
            # We also send the user an ephemeral message that we're confirming their choice.
            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
            async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                # await interaction.response.send_message("Confirming", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = True
                self.stop()

            # This one is similar to the confirmation button except sets the inner value to `False`
            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                log.info('Workflow cancelled')
                await interaction.response.send_message("Operation cancelled.", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = False
                self.stop()

        class StrikeSeverity(discord.ui.Select):
            def __init__(self, context):
                self.context = context
                options = [
                    discord.SelectOption(label='Strike Level 1', value='1', description='This is a warning strike',
                                         emoji='1️⃣'),
                    discord.SelectOption(label='Strike Level 2', value='2',
                                         description='This strike will also mute the user', emoji='2️⃣'),
                    discord.SelectOption(label='Strike Level 3', value='3',
                                         description='This strike will also ban the user', emoji='3️⃣')
                ]
                super().__init__(placeholder="Select the strike severity", min_values=1, max_values=1, options=options)

            async def interaction_check(self, interaction):
                if interaction.user != self.context.author:
                    return False
                return True

            async def callback(self, interaction):
                await interaction.response.defer()
                # await interaction.response.send_message(f'You selected strike level {self.values[0]}', ephemeral=True)
                for item in self.view.children:
                    item.disabled = True
                self.view.stop()

        class StrikeMessageModal(discord.ui.Modal):
            def __init__(self, max_length):
                super().__init__(title='Strike Message')
                self.value = None
                self.add_item(
                    InputText(
                        label='Strike Message',
                        placeholder='Enter your strike message here.',
                        style=discord.InputTextStyle.long,
                        max_length=max_length))

            async def callback(self, interaction: discord.Interaction):
                confirm_view = Confirm()
                await interaction.response.send_message(embed=gen_embed(
                    title='Does the strike message look correct?',
                    content=self.children[0].value),
                    view=confirm_view)
                await confirm_view.wait()
                if confirm_view.value:
                    self.value = self.children[0].value
                    og_msg = await interaction.original_message()
                    await og_msg.delete()
                    self.stop()
                else:
                    og_msg = await interaction.original_message()
                    await og_msg.delete()
                    self.stop()


        class ModalPromptView(discord.ui.View):
            def __init__(self, context, max_length):
                super().__init__(timeout=600)
                self.value = None
                self.context = context
                self.max_length = max_length

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                new_view = discord.ui.View.from_message(interaction.message)
                for child in new_view.children:
                    if isinstance(child, discord.ui.Button):
                        child.disabled = True

                await interaction.message.edit(view=new_view)
                self.stop()

            @discord.ui.button(label='Open Modal',
                               style=discord.ButtonStyle.primary)
            async def open_modal(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = StrikeMessageModal(self.max_length)
                await interaction.response.send_modal(modal)
                await modal.wait()
                self.value = modal.value
                await self.end_interaction(interaction)

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                log.info('Workflow cancelled')
                # await interaction.response.send_message("Operation cancelled.", ephemeral=True)
                await interaction.response.defer()
                self.stop()

        async def input_prompt(attempts=1, scenario: int = None, prev_message=None):
            def check(m):
                return m.author == ctx.interaction.user and m.channel == ctx.interaction.channel

            if prev_message:
                await prev_message.delete()

            match scenario:
                case 1:
                    sent_prompt = await ctx.send(embed=
                                                 gen_embed(title='Timeout Duration',
                                                           content=('How long do you want to timeout the user?'
                                                                    ' Accepted format: # [days/minutes/hrs/mins/etc.],'
                                                                    ' these can be chained together, i.e.'
                                                                    ' `3 days and 6 hours`.')))
                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Timeout cancelled',
                                                                            content='Strike has still been applied'),
                                                            ephemeral=True)
                        return
                    time_result = None
                    testing_text = ""
                    for chunk in mmsg.clean_content.split():
                        if chunk == "and":
                            continue
                        if chunk.isdigit():
                            testing_text += chunk
                            continue
                        testing_text += chunk.rstrip(",")
                        parsed = parse_timedelta(testing_text, minimum=timedelta(seconds=1), maximum=timedelta(days=28))
                        if parsed != time_result:
                            time_result = parsed
                            await mmsg.delete()
                            await sent_prompt.delete()
                            return time_result
                        elif attempts > 3:
                            await mmsg.delete()
                            await sent_prompt.delete()
                            raise discord.ext.commands.BadArgument('Could not parse time 3 times in a row, forced exit')
                        else:
                            await ctx.interaction.followup.send(embed=gen_embed(title='Could not parse time',
                                                                                content='Please try again.'),
                                                                ephemeral=True)
                            await mmsg.delete()
                            attempts += 1
                            return await input_prompt(attempts, scenario=1, prev_message=sent_prompt)

                case 2:
                    sent_prompt = await ctx.send(embed=
                                                 gen_embed(title='Image Mute Duration',
                                                           content=('How long do you want to mute the user?'
                                                                    ' Accepted format: # [days/minutes/hrs/mins/etc.],'
                                                                    ' these can be chained together, i.e.'
                                                                    ' `3 days and 6 hours`.')))
                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Image Mute cancelled',
                                                                            content='Strike has still been applied'),
                                                            ephemeral=True)
                        return

                    time_result = None
                    testing_text = ""
                    for chunk in mmsg.clean_content.split():
                        if chunk == "and":
                            continue
                        if chunk.isdigit():
                            testing_text += chunk
                            continue
                        testing_text += chunk.rstrip(",")
                        parsed = parse_timedelta(testing_text, minimum=timedelta(seconds=1), maximum=timedelta(days=28))
                        if parsed != time_result:
                            time_result = parsed
                            await mmsg.delete()
                            await sent_prompt.delete()
                            return time_result
                        elif attempts > 3:
                            await mmsg.delete()
                            await sent_prompt.delete()
                            raise discord.ext.commands.BadArgument('Could not parse time 3 times in a row, forced exit')
                        else:
                            await ctx.interaction.followup.send(embed=gen_embed(title='Could not parse time',
                                                                                content='Please try again.'),
                                                                ephemeral=True)
                            await mmsg.delete()
                            attempts += 1
                            return await input_prompt(attempts, scenario=2, prev_message=sent_prompt)

                case 3:
                    sent_prompt = await ctx.send(embed=
                                                 gen_embed(title='# of Days Worth of Messages to Delete',
                                                           content=('How many days worth of messages do you want to'
                                                                    ' delete?')))
                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Ban cancelled',
                                                                            content=('Strike has still been applied,'
                                                                                     ' please ban manually.')),
                                                            ephemeral=True)
                        return

                    if re.match(r'^[0-7]{1}$', mmsg.clean_content, flags=re.I):
                        await mmsg.delete()
                        await sent_prompt.delete()
                        return int(mmsg.clean_content)
                    elif attempts > 3:
                        await mmsg.delete()
                        await sent_prompt.delete()
                        raise discord.ext.commands.BadArgument(
                            'Could not parse # of days 3 times in a row, forced exit')
                    else:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Could not parse # of days',
                                                                            content='Please try again.'),
                                                            ephemeral=True)
                        await mmsg.delete()
                        attempts += 1
                        return await input_prompt(attempts, scenario=3, prev_message=sent_prompt)

                case 4:
                    sent_prompt = await ctx.send(embed=gen_embed(title='URL',
                                                                 content=('Please provide the message link/image URL'
                                                                          ' or attach an image for the strike below.'
                                                                          '\nType `cancel` to exit.')))
                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Strike cancelled',
                                                                            content=('Timed out. Please run the command'
                                                                                     ' again.')),
                                                            ephemeral=True)
                        return

                    if validators.url(mmsg.content):
                        await mmsg.delete()
                        await sent_prompt.delete()
                        return mmsg.clean_content
                    elif len(mmsg.attachments) > 0:
                        await sent_prompt.delete()
                        return mmsg.attachments[0].url
                    elif attempts > 3:
                        await mmsg.delete()
                        await sent_prompt.delete()
                        raise discord.ext.commands.BadArgument('Could not parse URL/Attachment 3 times in a row, '
                                                               'forced exit')
                    elif mmsg.clean_content.lower() == 'cancel':
                        await mmsg.delete()
                        await sent_prompt.delete()
                        return
                    else:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Could not parse URL/Attachment',
                                                                            content='Please try again.'),
                                                            ephemeral=True)
                        await mmsg.delete()
                        attempts += 1
                        return await input_prompt(attempts, scenario=4, prev_message=sent_prompt)

        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()

        strike_severity_view = discord.ui.View()
        strike_severity_view.add_item(StrikeSeverity(ctx))
        strike_severity_view.add_item(Cancel(ctx))
        original_sent_message = await ctx.interaction.followup.send(embed=
                                                                    gen_embed(title='Strike Severity',
                                                                              content='Please choose your strike'
                                                                                      ' severity from the'
                                                                                      ' dropdown below.'),
                                                                    view=strike_severity_view)
        await strike_severity_view.wait()
        if strike_severity_view.children[1].value:
            log.info('Cancelled strike operation')
            await ctx.interaction.followup.send(content='Strike has been cancelled.',
                                                ephemeral=True)
            for item in strike_severity_view.children:
                item.disabled = True
            await original_sent_message.edit(view=strike_severity_view)
        elif strike_severity_view.children[0].values:
            await original_sent_message.edit(embed=gen_embed(
                title='Strike User',
                content='Stage 1 complete.\n\nSelected strike severity: '
                        f'{strike_severity_view.children[0].values[0]}'),
                view=None)
            strike_url = await input_prompt(scenario=4)
            if strike_url:
                m = await modmail_enabled(ctx)
                if m:
                    embed_field_length = 1024 - len(f'Reason: \n[Message Link]({strike_url})\n\nIf you have any issues,'
                                                    ' you may reply (use the reply function) to this message and send a'
                                                    ' modmail.')
                else:
                    embed_field_length = 1024 - len(f'Reason: \n[Message Link]({strike_url})')

                await original_sent_message.edit(embed=gen_embed(
                    title='Strike User',
                    content='Stage 2 complete.\n\nSelected strike severity: '
                            f'{strike_severity_view.children[0].values[0]}'
                            f'\n[Message Link/Image URL]({strike_url})'),
                    view=None)

                strike_message_view = ModalPromptView(ctx, embed_field_length)
                sent_button_prompt = await ctx.interaction.followup.send(embed=gen_embed(
                    title='Strike Message Modal',
                    content='Click the button below to open a modal and enter your strike message.'),
                    view=strike_message_view)
                await strike_message_view.wait()
                await sent_button_prompt.delete()
                if strike_message_view.value is None:
                    log.info("View timed out")
                    await original_sent_message.edit(embed=gen_embed(
                        title='Strike User',
                        content=f'Strike for user {user.name}#{user.discriminator} has been cancelled.'),
                        view=None)
                    await ctx.interaction.followup.send(content='Strike has been cancelled.',
                                                        ephemeral=True)
                    return
                elif strike_message_view.value:
                    await original_sent_message.edit(embed=gen_embed(
                        title='Strike User',
                        content='Stage 3 complete. Strike Message Recieved!'),
                        view=None)
                    for s in range(0, int(strike_severity_view.children[0].values[0])):
                        _id = ObjectId()
                        post = {
                            '_id': _id,
                            'time': datetime.datetime.now(datetime.timezone.utc),
                            'server_id': ctx.interaction.guild_id,
                            'user_name': f'{user.name}#{user.discriminator}',
                            'user_id': user.id,
                            'moderator': f'{ctx.author.name}#{ctx.author.discriminator}',
                            'message_link': strike_url,
                            'reason': strike_message_view.value
                        }
                        await db.warns.insert_one(post)

                    timeout_time = None
                    ban_delete_days = 0

                    match strike_severity_view.children[0].values[0]:
                        case '2':
                            timeout_time = await input_prompt(scenario=1)
                        case '3':
                            ban_delete_days = await input_prompt(scenario=3)

                    dm_channel = user.dm_channel
                    if user.dm_channel is None:
                        dm_channel = await user.create_dm()

                    if m:
                        dm_embed = gen_embed(name=ctx.guild.name,
                                             icon_url=ctx.guild.icon.url,
                                             title='You have been given a strike',
                                             content=(f'Reason: {strike_message_view.value}\n'
                                                      f'[Message Link]({strike_url})\n\nIf you have any issues, you may'
                                                      ' reply (use the reply function) to this message and send a'
                                                      ' modmail.'))
                        dm_embed.set_footer(text=ctx.guild.id)
                    else:
                        dm_embed = gen_embed(name=ctx.guild.name,
                                             icon_url=ctx.guild.icon.url,
                                             title='You have been given a strike',
                                             content=(f'Reason: {strike_message_view.value}\n'
                                                      f'[Message Link]({strike_url})'))
                        dm_embed.set_footer(text=time.ctime())

                    try:
                        await dm_channel.send(embed=dm_embed)
                    except discord.Forbidden:
                        await ctx.interaction.followup.send(embed=gen_embed(title='Warning',
                                                                            content='This user does not accept DMs.'
                                                                                    ' I could not send them the message'
                                                                                    ', but I will proceed with striking'
                                                                                    ' the user.'),
                                                            ephemeral=True)

                    embed = gen_embed(name=f'{user.name}#{user.discriminator}',
                                      icon_url=user.display_avatar.url,
                                      title='Strike Recorded',
                                      content=(f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator}'
                                               f' gave a strike to {user.name}#{user.discriminator} | {user.id}'))
                    embed.add_field(name='Severity',
                                    value=f'{strike_severity_view.children[0].values[0]} strike(s)',
                                    inline=False)
                    embed.add_field(name='Reason',
                                    value=f'{strike_message_view.value}\n\n[Message/Image Link]({strike_url})',
                                    inline=False)
                    embed.set_footer(text=time.ctime())
                    await ctx.interaction.followup.send(embed=embed)

                    document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
                    if document['log_channel'] and document['log_strikes']:
                        log_channel = ctx.guild.get_channel(int(document['log_channel']))
                        await log_channel.send(embed=embed)

                    valid_strikes = []  # potentially redundant but added as a safe measure
                    searchtime = datetime.datetime.now(datetime.timezone.utc) + relativedelta(seconds=10)
                    results = await check_strike(ctx, user, current_time=searchtime, valid_strikes=valid_strikes)
                    log.info(results)  # debug

                    # Ban check should always come before timeout check
                    if len(results) >= document['max_strike']:
                        max_strike = document["max_strike"]
                        ban_delete_days = await input_prompt(scenario=3)
                        if m:
                            dm_embed = gen_embed(name=ctx.guild.name,
                                                 icon_url=ctx.guild.icon.url,
                                                 title='You have been banned',
                                                 content=(f'Reason: {strike_message_view.value}\n\n If you have any'
                                                          ' issues, you may reply (use the reply function to this'
                                                          ' message and send a modmail.'))
                            dm_embed.set_footer(text=ctx.interaction.guild_id)
                        else:
                            dm_embed = gen_embed(name=ctx.guild.name,
                                                 icon_url=ctx.guild.icon.url,
                                                 title='You have been banned',
                                                 content=f'Reason: {strike_message_view.value}')
                            dm_embed.set_footer(text=time.ctime())
                        try:
                            await dm_channel.send(embed=dm_embed)
                        except discord.Forbidden:
                            await ctx.interaction.followup.send(embed=
                                                                gen_embed(title='Warning',
                                                                          content='This user does not accept DMs.'
                                                                                  ' I could not send them the message'
                                                                                  ', but I will proceed with striking'
                                                                                  ' the user.'),
                                                                ephemeral=True)
                        await ctx.guild.ban(user,
                                            reason=(f'User has accumulated {max_strike} strikes and therefore is now'
                                                    ' banned from the server.'),
                                            delete_message_days=ban_delete_days)
                        if document['log_channel'] and document['log_kbm']:
                            log_channel = ctx.guild.get_channel(int(document['log_channel']))
                            embed = gen_embed(title='Ban User',
                                              content=(f'{user.name}#{user.discriminator} (ID: {user.id} has been'
                                                       ' banned.\nReason: Accumulated maximum # of strikes'))
                            await log_channel.send(embed=embed)
                        return  # If we ban someone, let's zip out and end.

                    elif len(results) == 2 and strike_severity_view.children[0].values[0] != '2':
                        # Since user has accumulated two strikes, we have to timeout now.
                        timeout_time = await input_prompt(scenario=1)

                    # Special pubcord check
                    elif strike_severity_view.children[0].values[0] != '2' and ctx.guild.id == 432379300684103699:
                        view = Confirm()
                        sent_message = await ctx.interaction.followup.send(embed=gen_embed(
                            title='Image Mute User',
                            content='Do you want to revoke image/external emote privileges?'),
                            view=view)
                        await view.wait()
                        await sent_message.delete()
                        if view.value is None:
                            log.info("View timed out")
                            await ctx.interaction.followup.send(content='Image Mute has been cancelled.',
                                                                ephemeral=True)
                            return
                        elif view.value:
                            log.info("Image Mute Workflow Confirm")
                            image_mute_time: timedelta = await input_prompt(scenario=2)
                            if image_mute_time:
                                image_mute_seconds = int(image_mute_time.total_seconds())
                                muted_role = discord.utils.get(ctx.guild.roles, name='Image Mute')

                                # TODO: CATCH EXCEPTION
                                await user.add_roles(muted_role)

                                if m:
                                    dm_embed = gen_embed(name=ctx.guild.name,
                                                         icon_url=ctx.guild.icon.url,
                                                         title=('You have had your image/external emote privileges'
                                                                ' revoked for'
                                                                f' {humanize_timedelta(timedelta=image_mute_time)}.'),
                                                         content=('If you have any issues, you may reply (use the reply'
                                                                  ' function) to this message and send a modmail.'))
                                    dm_embed.set_footer(text=ctx.guild.id)
                                else:
                                    dm_embed = gen_embed(name=ctx.guild.name,
                                                         icon_url=ctx.guild.icon.url,
                                                         title=('You have had your image/external emote privileges'
                                                                ' revoked for'
                                                                f' {humanize_timedelta(timedelta=image_mute_time)}.'),
                                                         content='This is a result of your strike.')
                                    dm_embed.set_footer(text=time.ctime())
                                try:
                                    await dm_channel.send(embed=dm_embed)
                                except discord.Forbidden:
                                    await ctx.interaction.followup.send(embed=gen_embed(
                                        title='Warning',
                                        content='This user does not accept DMs. I could not send them the message,'
                                                ' but I will proceed with striking and muting the user.'),
                                        ephemeral=True)
                                await ctx.interaction.followup.send(embed=gen_embed(
                                    title='Image Mute User',
                                    content=(f'{user.name}#{user.discriminator} has been image muted for'
                                             f' {humanize_timedelta(timedelta=image_mute_time)}')),
                                    ephemeral=True)
                                if document['log_channel'] and document['log_kbm']:
                                    log_channel = ctx.guild.get_channel(int(document['log_channel']))
                                    embed = gen_embed(
                                        title='Image Mute User',
                                        content=(
                                            f'{user.name}#{user.discriminator} has been image muted by'
                                            f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator} for'
                                            f' {humanize_timedelta(timedelta=image_mute_time)}'
                                            '\nReason: Moderator specified mute'))
                                    await log_channel.send(embed=embed)
                                await asyncio.sleep(image_mute_seconds)  # TODO: store tasks in temporary db
                                await user.remove_roles(muted_role)
                                return
                        else:
                            log.info('Cancelled strike operation')
                            await ctx.interaction.followup.send(content='Image mute has not been applied.',
                                                                ephemeral=True)

                    if timeout_time:
                        # TODO: CATCH EXCEPTION
                        await user.timeout_for(timeout_time,
                                               reason='Automatic timeout due to accumulating 2 strikes')

                        if m:
                            dm_embed = gen_embed(
                                name=ctx.guild.name,
                                icon_url=ctx.guild.icon.url,
                                title=('You have been put in timeout. Your timeout will last for'
                                       f' {humanize_timedelta(timedelta=timeout_time)}'),
                                content=('Strike 2 - automatic timeout\n\nIf you have any issues, you may reply '
                                         '(use the reply function) to this message and send a modmail.'))
                            dm_embed.set_footer(text=ctx.guild.id)
                        else:
                            dm_embed = gen_embed(
                                name=ctx.guild.name,
                                icon_url=ctx.guild.icon.url,
                                title=('You have been put in timeout. Your timeout will last for'
                                       f' {humanize_timedelta(timedelta=timeout_time)}'),
                                content='Strike 2 - automatic timeout')
                            dm_embed.set_footer(text=time.ctime())

                        try:
                            await dm_channel.send(embed=dm_embed)
                        except discord.Forbidden:
                            await ctx.interaction.followup.send(embed=gen_embed(
                                title='Warning',
                                content='This user does not accept DMs. I could not send them the message,'
                                        ' but I will proceed with striking and timing out the user.'),
                                ephemeral=True)
                        await ctx.interaction.followup.send(embed=gen_embed(
                            title='Timeout User',
                            content=(f'{user.name}#{user.discriminator} has been timed out for'
                                     f' {humanize_timedelta(timedelta=timeout_time)}')),
                            ephemeral=True)
                        if document['log_channel'] and document['log_kbm']:
                            log_channel = ctx.guild.get_channel(int(document['log_channel']))
                            embed = gen_embed(title='Timeout User',
                                              content=(f'{user.name}#{user.discriminator} has been timed out for'
                                                       f' {humanize_timedelta(timedelta=timeout_time)}'
                                                       '\nReason: Strike severity 2 or accumulated 2 strikes'))
                            await log_channel.send(embed=embed)
                        return

            else:
                log.info('No message URL')
                await ctx.interaction.followup.send(content='Strike has been cancelled.',
                                                    ephemeral=True)
                return

    @discord.slash_command(name='lookup',
                           description='Lookup user information')
    @default_permissions(ban_members=True)
    async def lookup(self,
                     ctx: discord.ApplicationContext,
                     user: Option(discord.Member, 'User to lookup')):
        class Cancel(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Cancel", style=discord.ButtonStyle.danger)
                self.value = None

            async def interaction_check(self, interaction):
                if interaction.user != ctx.author:
                    return False
                return True

            async def callback(self, interaction):
                await interaction.response.send_message("Cancelled Operation.", ephemeral=True)
                for item in self.view.children:
                    item.disabled = True
                self.value = True
                self.view.stop()

        class StrikeSelect(discord.ui.Select):
            def __init__(self, context, user_options):
                self.context = context
                menu_options = user_options
                super().__init__(placeholder="Select which strike to remove", min_values=1, max_values=len(options),
                                 options=menu_options)

            async def interaction_check(self, interaction: discord.Interaction):
                if interaction.user != self.context.interaction.user:
                    return False
                return True

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message(f'You selected {self.values}', ephemeral=True)
                for item in self.view.children:
                    item.disabled = True
                self.view.stop()

        class LookupMenu(discord.ui.View):
            def __init__(self, pass_ctx):
                super().__init__()
                self.value = None
                self.context = pass_ctx

            async def interaction_check(self, interaction: discord.Interaction):
                return interaction.user == self.context.interaction.user

            @discord.ui.button(label="Send Modmail", style=discord.ButtonStyle.primary)
            async def sendmodmail(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def check_modmail_enabled():
                    doc = await db.servers.find_one({"server_id": self.context.guild.id})
                    if doc['modmail_channel']:
                        return True
                    else:
                        return False

                await interaction.response.defer()

                if modmail := await check_modmail_enabled():
                    # await interaction.response.send_message("Acknowledged Send Modmail", ephemeral=True)
                    for item in self.children:
                        item.disabled = True
                    self.value = 1
                    self.stop()
                else:
                    await interaction.response.send_message("Sorry, modmail is not enabled for this server.",
                                                            ephemeral=True)
                    self.value = 4
                    self.stop()

            @discord.ui.button(label='Strike User', style=discord.ButtonStyle.primary)
            async def strikeuser(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                for item in self.children:
                    item.disabled = True
                self.value = 2
                self.stop()

            @discord.ui.button(label='Delete Strike', style=discord.ButtonStyle.danger)
            async def delstrike(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.send_message("Please choose which strike to delete from the dropdown above.",
                                                        ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = 3
                self.stop()

        def to_relativedelta(tdelta):
            assert isinstance(tdelta, timedelta)

            seconds_in = {
                'year': 365 * 24 * 60 * 60,
                'month': 30 * 24 * 60 * 60,
                'day': 24 * 60 * 60,
                'hour': 60 * 60,
                'minute': 60
            }

            years, rem = divmod(tdelta.total_seconds(), seconds_in['year'])
            months, rem = divmod(rem, seconds_in['month'])
            days, rem = divmod(rem, seconds_in['day'])
            hours, rem = divmod(rem, seconds_in['hour'])
            minutes, rem = divmod(rem, seconds_in['minute'])
            seconds = rem

            return relativedelta(years=years, months=months, days=days, hours=hours, minutes=minutes, seconds=seconds)

        await ctx.interaction.response.defer()

        valid_strikes = []  # probably redundant but doing it anyways to prevent anything stupid
        results = await check_strike(ctx,
                                     user,
                                     current_time=datetime.datetime.now(datetime.timezone.utc) + relativedelta(
                                         minutes=2),
                                     valid_strikes=valid_strikes)
        results = sorted(results, key=lambda d: d['time'])
        num_strikes = len(results)

        strike_pages = []

        expired_query = {'server_id': ctx.guild.id, 'user_id': user.id}
        expired_results = db.warns.find(expired_query).sort('time', pymongo.DESCENDING)
        expired_strikes = []

        active_member = ctx.guild.get_member(user.id)
        if active_member:
            member_duration = abs(active_member.joined_at - datetime.datetime.now(datetime.timezone.utc))
            member_duration = to_relativedelta(member_duration)
            base_embed = gen_embed(name=f'{active_member.name}#{active_member.discriminator}',
                                   icon_url=active_member.display_avatar.url,
                                   title='User Lookup',
                                   content=(f'This user has been a member for **{member_duration.years} years, '
                                            f'{member_duration.months} months, and {int(member_duration.days)} days**.'
                                            f'\nThey joined on **{active_member.joined_at.strftime("%B %d, %Y")}**'))
        else:
            base_embed = gen_embed(name=f'{user.name}#{user.discriminator}', icon_url=user.display_avatar.url,
                                   title='User Lookup', content=f'This user is no longer in the server.')

        async for document in expired_results:
            if document not in results:
                expired_strikes.append(document)
                document_id = str(document['_id'])
                stime = document['time']
                reason = document['reason']
                message_link = document['message_link']
                moderator = document['moderator']
                embed_field = (f'Strike UID: {document_id} | Moderator: {moderator}\nReason: {reason}'
                               f'\n[Go to message/evidence]({message_link})')
                if len(embed_field) > 1024:
                    truncate = len(reason) - (len(embed_field) - 1024) - 4
                    reason = reason[0:truncate] + "..."
                strike_embed = base_embed.copy()
                strike_embed.add_field(name=f'Strike (EXPIRED)| {stime.ctime()}',
                                       value=(f'Strike UID: {document_id} | Moderator: {moderator}\nReason: {reason}'
                                              f'\n[Go to message/evidence]({message_link})'),
                                       inline=False)
                strike_embed.set_footer(text=f'UID: {user.id}')
                strike_pages.append(strike_embed)
        num_expired = len(expired_strikes)

        base_embed.add_field(name='Strikes',
                             value=(f'Found {num_strikes + num_expired} strikes for this user.\n'
                                    f'{num_strikes} are currently active strikes.'),
                             inline=False)

        if results:
            for document in results:
                document_id = str(document['_id'])
                stime = document['time']
                reason = document['reason']
                message_link = document['message_link']
                moderator = document['moderator']
                embed_field = (f'Strike UID: {document_id} | Moderator: {moderator}\nReason: {reason}'
                               f'\n[Go to message/evidence]({message_link})')
                if len(embed_field) > 1024:
                    truncate = len(reason) - (len(embed_field) - 1024) - 4
                    reason = reason[0:truncate] + "..."
                strike_embed = base_embed.copy()
                strike_embed.add_field(name=f'Strike | {stime.ctime()}',
                                       value=(f'Strike UID: {document_id} | Moderator: {moderator}\nReason: {reason}'
                                              f'\n[Go to message/evidence]({message_link})'),
                                       inline=False)
                strike_embed.set_footer(text=f'UID: {user.id}')
                strike_pages.append(strike_embed)

        else:
            strike_embed = base_embed.copy()
            strike_embed.set_footer(text=f'UID: {user.id}')
            strike_pages.append(strike_embed)

        lookup_view = LookupMenu(ctx)
        if num_strikes == 0:
            lookup_view.children[2].disabled = True
        page_buttons = [
            pages.PaginatorButton("first", emoji="⏪", style=discord.ButtonStyle.green),
            pages.PaginatorButton("prev", emoji="⬅", style=discord.ButtonStyle.green),
            pages.PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True),
            pages.PaginatorButton("next", emoji="➡", style=discord.ButtonStyle.green),
            pages.PaginatorButton("last", emoji="⏩", style=discord.ButtonStyle.green),
        ]
        strike_pages.reverse()
        paginator = pages.Paginator(pages=strike_pages,
                                    show_disabled=True,
                                    show_indicator=True,
                                    use_default_buttons=False,
                                    custom_buttons=page_buttons,
                                    custom_view=lookup_view)
        sent_message = await paginator.respond(ctx.interaction, ephemeral=False)
        await lookup_view.wait()
        await paginator.update(custom_buttons=page_buttons, custom_view=lookup_view)
        match lookup_view.value:
            case 1:
                # modmail enabled, send modmail
                modmail_cog = self.bot.get_cog('Modmail')
                if modmail_cog:
                    await modmail_cog.modmail(ctx=ctx, recipient=user)
                else:
                    await ctx.interaction.followup.send(content=('Modmail feature not found.'
                                                                 'Please message Neon#5555 immediately.'),
                                                        ephemeral=True)
            case 2:
                # strike user
                admin_cog = self.bot.get_cog('Administration')
                if admin_cog:
                    await admin_cog.strike(ctx=ctx, user=user)
                else:
                    await ctx.interaction.followup.send(content=('Administrative features not found.'
                                                                 'Please message Neon#5555 immediately.'),
                                                        ephemeral=True)
            case 3:
                # delete strike
                deletestrike_view = discord.ui.View()
                options = []

                deletestrike_query = {'server_id': ctx.interaction.guild_id, 'user_id': user.id}
                deletestrike_results = db.warns.find(deletestrike_query).sort('time', pymongo.DESCENDING)
                strikes = await deletestrike_results.to_list(length=100)
                log.info(strikes)

                for document in strikes:
                    document_id = str(document['_id'])
                    stime = document['time']
                    options.append(discord.SelectOption(label=stime.ctime(),
                                                        value=document_id,
                                                        description=f'Strike ID: {document_id}'))

                deletestrike_view.add_item(StrikeSelect(ctx, options))
                deletestrike_view.add_item(Cancel())
                await paginator.update(custom_buttons=page_buttons, custom_view=deletestrike_view)
                await paginator.wait()
                # TODO: update pages to reflect deleted strikes
                if deletestrike_view.children[1].value:
                    log.info("Cancelled Delete Strike Operation")
                elif deletestrike_view.children[0].values:
                    admin_cog = self.bot.get_cog('Administration')
                    if admin_cog:
                        for strike in deletestrike_view.children[0].values:
                            await admin_cog.removestrike(ctx=ctx, strikeid=str(strike))
                    else:
                        await ctx.interaction.followup.send(content=('Administrative features not found.'
                                                                     'Please message Neon#5555 immediately.'),
                                                            ephemeral=True)
            case 4:
                # modmail disabled, cannot send modmail
                pass
            case None:
                log.info('View timed out')
                await ctx.interaction.followup.send('Action cancelled. Please run /lookup again to do more actions.',
                                                    ephemeral=True)

    @discord.slash_command(name='removestrike',
                           description='Remove a strike from the database')
    @default_permissions(ban_members=True)
    async def removestrike(self,
                           ctx: discord.ApplicationContext,
                           strikeid: Option(str, 'Strike to remove from the database')):
        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()
        deleted = await db.warns.delete_one({"_id": ObjectId(strikeid)})
        if deleted.deleted_count == 1:
            await ctx.interaction.followup.send(embed=gen_embed(title='Strike Deleted',
                                                                content=f'Strike {strikeid} was deleted.'),
                                                ephemeral=True)
        elif deleted.deleted_count == 0:
            log.warning(f'Error while deleting strike')
            await ctx.interaction.followup.send(embed=gen_embed(title='Error',
                                                                content=f'I was unable to delete strike {strikeid}.'
                                                                        'Check your UID. If correct, something may'
                                                                        ' be wrong with the database or the strike'
                                                                        ' does not exist.'),
                                                ephemeral=True)

    @discord.slash_command(name='slowmode',
                           description='Enable slowmode in a channel')
    @default_permissions(manage_channels=True)
    async def slowmode(self,
                       ctx: discord.ApplicationContext,
                       channel: Option(discord.SlashCommandOptionType.channel, 'Channel to enabled slowmode for'),
                       cooldown: Option(int, 'Cooldown time between messages in seconds. Enter 0 to disable',
                                        min_value=0,
                                        max_value=21600)):
        await ctx.interaction.response.defer()
        await channel.edit(slowmode_delay=cooldown)
        if cooldown == 0:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Slowmode',
                                                          content=f'Slowmode disabled for {channel.mention}'))
            return
        await ctx.interaction.followup.send(embed=
                                            gen_embed(title='Slowmode',
                                                      content=f'Slowmode enabled for {channel.mention} ({cooldown}s)'))


# This method will spit out the list of valid strikes. we can cross reference the entire list of strikes to determine
# which ones are expired on the lookup command. We can also check the length of the list when giving out strikes to
# determine if an automatic ban is required.

# Currently, there are 5 scenarios:
#   1. No strikes active (none in past 2 months)
#   2. One strike active (past 2 months)
#   3. Two strikes active (past 2-4 months, timer reset due to accumulation of second strike)
#   4. Two strikes active (past 2 months)
#   5. Three strikes active (proceed to ban the user)
async def check_strike(ctx, member, current_time=datetime.datetime.now(datetime.timezone.utc), valid_strikes=None):
    log.info(current_time)  # this is here for debugging race condition atm

    # Create the search query
    expire_date = current_time + relativedelta(months=-2)
    query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date, '$lt': current_time}}
    results = await db.warns.count_documents(query)

    if results > 0:
        # This case means we have an active strike.
        # Let's check the next strike to see if it's within 2 months of this strike.
        # This sorts our query by date and will return the latest strike
        log.info('found strike, beginning search process')
        results = db.warns.find(query).sort('time', pymongo.DESCENDING).limit(1)
        document = await results.to_list(length=None)
        document = document.pop()
        valid_strikes.append(document)

        if len(valid_strikes) >= 3:
            # Ban time boom boom. stop searching and step out
            log.info('max_strike exceeded, proceed to ban')
            return valid_strikes

        # Else it's time to step in and start the recursion to check the next two months again.
        # If the second strike is found, we will step in one final time to check for the third and final strike.
        newtime = document['time']
        return await check_strike(ctx, member, current_time=newtime, valid_strikes=valid_strikes)

    else:
        # This means we didn't get a hit, so let's step out and spit out our list.
        log.info('all strike cases false')
        return valid_strikes


def setup(bot):
    bot.add_cog(Administration(bot))
