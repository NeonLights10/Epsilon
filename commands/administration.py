import asyncio
from __main__ import log, db
from typing import Union

import discord
import emoji as zemoji
from discord.ext import commands

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
    async def settings(self,
                       ctx: discord.ApplicationContext):

        await ctx.interaction.response.defer()
        document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})

        class Cancel(discord.ui.View):
            def __init__(self, og_interaction, og_view, og_embed):
                super().__init__()
                self.og_interaction = og_interaction
                self.og_view = og_view
                self.og_embed = og_embed

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.og_interaction.edit_original_message(embed=self.og_embed,
                                                                view=self.og_view)
                self.stop()
                await interaction.message.delete()

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
                            self.embed.set_field_at(0, name='Prefix', value=prefix_view.value, inline=False)
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
                            content = content + f' in channel {announce_channel.mention}'
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
                        pass
                    case 'Chat Feature':
                        pass
                    case 'Blacklist/Whitelist':
                        pass
                    case 'Fun Features':
                        pass
                    case 'Logging':
                        pass
                    case 'Auto Assign Role On Join':
                        pass
                    case 'Moderator Role':
                        pass
                    case 'Server Join Verification':
                        pass

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
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
                        # TODO: change exception type
                        raise RuntimeError('Forbidden 403 - could not send direct message to user.')

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
                        await db.servers.update_one({"server_id": interaction.guild.id},
                                                    {"$set": {'prefix': new_prefix.clean_content}})
                        interaction.message.embeds[0].description = f'**Prefix: {new_prefix_content}**'
                        self.value = new_prefix_content
                        await interaction.message.edit(embed=interaction.message.embeds[0])

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

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
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def configure_announcement_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def announcement_prompt(listen_channel):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure announcement channel',
                                            content='Please mention the channel you would like to use for modmail.'))
                    except discord.Forbidden:
                        # TODO: change exception type
                        raise RuntimeError('Forbidden 403 - could not send direct message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Announcement channel configuration',
                                            content='Announcement channel configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    await sent_prompt.delete()
                    return mmsg

                await interaction.response.defer()
                new_announcement = await announcement_prompt(interaction.channel)

                if new_announcement:
                    log.info('New prefix entered, confirm workflow')
                    view = Confirm()
                    new_announcement_channel = new_announcement.channel_mentions[0]
                    await new_announcement.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f' **Selected Announcement Channel: {new_announcement_channel.mention}**')),
                        view=view)
                    announcement_timeout = await view.wait()
                    if announcement_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild.id},
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

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

        embed = gen_embed(name='Settings',
                          content='You can configure the settings for Kanon Bot using the select dropdown below.')

        embed.add_field(name='Prefix',
                        value=f"{document['prefix'] or '%'}",
                        inline=False)

        announcement_channel = None
        embed_text = ', no configured channel\n(Default public updates OR system channel)'
        if document['announcement_channel']:
            announcement_channel = ctx.guild.get_channel(int(document['announcement_channel']))
            embed_text = f' | Configured channel: {announcement_channel.mention}'
        embed.add_field(name='Global Announcements',
                        value=f"{'Enabled' if document['announcements'] else 'Disabled'}"
                              f'{embed_text}',
                        inline=False)

        modmail_channel = None
        if document['modmail_channel']:
            modmail_channel = ctx.guild.get_channel(int(document['modmail_channel']))
        embed.add_field(name='Modmail',
                        value=f"{'Enabled' if document['modmail_channel'] else 'Disabled'}"
                              f"{(' | Configured channel: ' + modmail_channel.mention) if modmail_channel else ''}",
                        inline=False)

        embed.add_field(name='Chat Feature',
                        value=f"{'Enabled' if document['chat'] else 'Disabled'}")

        embed_text = 'Disabled'
        if document['blacklist']:
            blacklist = document['blacklist']
            embed_text = 'Blacklist enabled for the following channels: '
            for channel in blacklist:
                channel = ctx.guild.get_channel(channel)
                embed_text = embed_text + f'{channel.mention} '
        elif document['whitelist']:
            whitelist = document['whitelist']
            embed_text = 'Whitelist enabled for the following channels: '
            for channel in whitelist:
                channel = ctx.guild.get_channel(channel)
                embed_text = embed_text + f'{channel.mention} '
        embed.add_field(name='Blacklist/Whitelist',
                        value=f'{embed_text}',
                        inline=False)

        embed.add_field(name='Fun Features',
                        value=f"{'Enabled' if document['fun'] else 'Disabled'}",
                        inline=False)

        embed.add_field(name='Logging',
                        value=f"Not implemented yet",
                        inline=False)

        embed.add_field(name='Auto Assign Role On Join',
                        value=f"Not implemented yet",
                        inline=False)

        embed.add_field(name='Moderator Role',
                        value=f"Not implemented yet",
                        inline=False)

        embed.add_field(name='Server Join Verification',
                        value=f"Not implemented yet",
                        inline=False)

        main_menu_view = SettingsMenu(ctx, embed, self.bot)
        sent_menu_message = await ctx.interaction.followup.send(embed=embed,
                                                                view=main_menu_view)
        timeout = await main_menu_view.wait()
        if timeout:
            for item in main_menu_view.children:
                item.disabled = True
            await sent_menu_message.edit(embed=embed,
                                         view=main_menu_view)


def setup(bot):
    bot.add_cog(Administration(bot))
