import discord
import re
import time
import validators
import datetime
import asyncio
import emoji as zemoji

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
                await self.stop()
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
                self.stopped = False

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
                               row=1)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.send_message("Stopped configuring settings.", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.stop()
                self.stopped = True

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
                        prefix_embed = gen_embed(name='Prefix Settings',
                                                 content=f"**Prefix:** {server_document['prefix'] or '%'}")
                        prefix_view = PrefixMenu(self.context, self, interaction, self.embed, self.bot)
                        await interaction.edit_original_message(embed=prefix_embed,
                                                                view=prefix_view)
                        timeout = await prefix_view.wait()
                        if timeout:
                            for item in prefix_view.children:
                                item.disabled = True
                            await interaction.edit_original_message(embed=prefix_embed,
                                                                    view=prefix_view)
                    case 'Global Announcements':
                        pass
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

        class PrefixMenu(discord.ui.View):
            def __init__(self, og_context, og_view: SettingsMenu, menu_interaction, main_embed, bot):
                super().__init__()
                self.context = og_context
                self.view = og_view
                self.interaction = menu_interaction
                self.main_embed = main_embed
                self.bot = bot
                self.value = False

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            @discord.ui.button(label='Set Prefix',
                               style=discord.ButtonStyle.primary,
                               row=0)
            async def set_prefix(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def prefix_prompt(listen_channel):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(embed=gen_embed(title='New prefix',
                                                                                content='Please type the new prefix you'
                                                                                        ' would like to use.'))
                    except discord.Forbidden:
                        # TODO: change exception type
                        raise RuntimeError('Forbidden 403 - could not send direct message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(embed=gen_embed(title='Prefix configuration',
                                                                        content=('Prefix configuration has'
                                                                                 ' been cancelled.')),
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
                    sent_message = await interaction.followup.send(embed=gen_embed(title='Confirmation',
                                                                                   content=('Please verify the contents'
                                                                                            ' before confirming:\n'
                                                                                            ' New Prefix: '
                                                                                            f'{new_prefix_content}')),
                                                                   view=view)
                    timeout = await view.wait()
                    if timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        await db.servers.update_one({"server_id": interaction.guild.id},
                                                    {"$set": {'prefix': new_prefix.clean_content}})
                        interaction.message.embeds[0].description = f'**Prefix:** {new_prefix_content}'
                        self.main_embed.set_field_at(0, name='Prefix', value=new_prefix_content, inline=False)
                        await self.interaction.edit_original_message(embed=interaction.message.embeds[0])

            @discord.ui.button(label='Cancel',
                               style=discord.ButtonStyle.danger,
                               row=0)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.interaction.edit_original_message(embed=self.main_embed,
                                                             view=self.view)

        embed = gen_embed(name='Settings',
                          content='You can configure the settings for Kanon Bot using the select dropdown below.')

        embed.add_field(name='Prefix',
                        value=f"{document['prefix'] or '%'}",
                        inline=False)

        announcement_channel = None
        embed_text = ', no configured channel\n(Default public updates OR system channel)'
        if document['announcement_channel']:
            announcement_channel = ctx.guild.get_channel(int(document['announcement_channel']))
            embed_text = f' | Configured channel: #{announcement_channel.mention}'
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
                        value=f"{'Enabled' if document['fun'] else 'Disabled'}")

        main_menu_view = SettingsMenu(ctx, embed, self.bot)
        sent_menu_message = await ctx.interaction.followup.send(embed=embed,
                                            view=main_menu_view)
        timeout = await main_menu_view.wait()
        if timeout or main_menu_view.stopped:
            for item in main_menu_view.children:
                item.disabled = True
            await sent_menu_message.edit(embed=embed,
                                         view=main_menu_view)


def setup(bot):
    bot.add_cog(Administration(bot))
