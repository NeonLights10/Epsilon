import asyncio
from __main__ import log, db
from typing import Union

import discord
import emoji as zemoji
from discord.commands.permissions import default_permissions
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup

from commands.errorhandler import CheckOwner
from formatting.embed import gen_embed


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def convert_emoji(argument):
        return zemoji.demojize(argument)

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

        await ctx.interaction.response.defer()
        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})

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
                            self.embed.set_field_at(3,
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
                            self.embed.set_field_at(5,
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
                            self.embed.set_field_at(6,
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
                            self.embed.set_field_at(6,
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
                for child in self.children:
                    if child.custom_id == 'logselect':
                        self.select_values = child.values
                post = {'log_messages': False,
                        'log_joinleaves': False,
                        'log_kbm': False,
                        'log_strikes': False}
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
                                                    {"$set": {'announcement_channel': new_log_channel.id}})

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
                                                    gen_embed(title='blacklist add',
                                                              content=f'Channel {channel.mention} has been added '
                                                                      f'to the blacklist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='blacklist add',
                                                              content=f'Channel has already been added '
                                                                      f'to the blacklist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='blacklist add',
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
                                                    gen_embed(title='blacklist remove',
                                                              content=f'Channel {channel.mention} has been removed '
                                                                      f'from the blacklist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='blacklist remove',
                                                              content=f'Channel is not in the blacklist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='blacklist remove',
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
                                                    gen_embed(title='whitelist add',
                                                              content=f'Channel {channel.mention} has been added '
                                                                      f'to the whitelist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='whitelist add',
                                                              content=f'Channel has already been added '
                                                                      f'to the whitelist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='whitelist add',
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
                                                    gen_embed(title='whitelist remove',
                                                              content=f'Channel {channel.mention} has been removed '
                                                                      f'from the whitelist.'),
                                                    ephemeral=True)
            else:
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='whitelist remove',
                                                              content=f'Channel is not in the whitelist!'),
                                                    ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='whitelist remove',
                                                          content='Whitelist is not enabled!'),
                                                ephemeral=True)


def setup(bot):
    bot.add_cog(Administration(bot))
