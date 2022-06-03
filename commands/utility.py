import asyncio
import datetime
import random
import re
import emoji as emojize
from datetime import timedelta

import discord
from discord.ext import commands, pages, tasks
from discord.commands import Option, SlashCommandGroup
from discord.commands.permissions import default_permissions
from discord.ui import InputText

from formatting.embed import gen_embed
from formatting.constants import TIMEZONE_DICT
from __main__ import log, db


def find_key(dic, val):
    try:
        # 99% sure there is a less convoluted way to implement this
        key = [k for k, v in TIMEZONE_DICT.items() if v == val][0]
        return True
    except Exception as e:
        return False


class SelfRoleSelect(discord.ui.Select):
    def __init__(self, role_options):
        super().__init__(placeholder="Select your roles here!",
                         min_values=0,
                         max_values=len(role_options) if len(role_options) > 0 else 1,
                         options=role_options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f'Your roles have been modified!', ephemeral=True)
        member = interaction.guild.get_member(interaction.user.id)
        member_roles = member.roles
        for value in self.values:
            selected_role = discord.utils.get(interaction.guild.roles, id=int(value))
            if selected_role not in member_roles:
                member_roles.append(selected_role)
        for option in self.options:
            if option.value not in self.values:
                selected_role = discord.utils.get(interaction.guild.roles, id=int(option.value))
                if selected_role in member_roles:
                    member_roles.remove(selected_role)
        try:
            await member.edit(roles=member_roles)
        except discord.Forbidden:
            await interaction.followup.send('I do not have permission to do this! Check the server settings.',
                                            ephemeral=True)


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.initialize_selfassign.start()

    def cog_unload(self):
        self.initialize_selfassign.cancel()

    @tasks.loop(seconds=1.0, count=1)
    async def initialize_selfassign(self):
        log.info(f'Initializing selfassign routine')
        for guild in self.bot.guilds:
            log.info(f'Checking selfassign for {guild.name}')
            selfrole_documents = db.rolereact.find({"server_id": guild.id})
            async for category_document in selfrole_documents:
                log.info(f'Processing selfassign document for {guild.name}')
                post_channel = guild.get_channel(int(category_document['channel_id']))
                try:
                    post_message = await post_channel.fetch_message(int(category_document['msg_id']))
                except discord.NotFound:
                    post_embed = gen_embed(title=category_document['category_name'],
                                           content=category_document['category_description'])
                    try:
                        post_message = await post_channel.send(embed=post_embed)
                    except discord.Forbidden:
                        log.info(f'Error initializing selfassign for {guild.name}')
                        continue
                    await db.rolereact.update_one({"msg_id": category_document['msg_id']},
                                                  {"$set": {"msg_id": post_message.id}})

                selectrole_view = discord.ui.View(timeout=None)
                options = []

                if len(category_document['roles']) > 0:
                    for role_id, emoji_id in category_document['roles'].items():
                        r = discord.utils.get(guild.roles, id=int(role_id))
                        if re.match(r'\d{17,18}', str(emoji_id)):
                            e = None
                            for _guild in self.bot.guilds:
                                e = discord.utils.get(_guild.emojis, id=int(emoji_id))
                                if e:
                                    break
                                else:
                                    continue
                        else:
                            e = emoji_id
                        options.append(discord.SelectOption(label=r.name,
                                                            value=str(r.id),
                                                            emoji=e))

                    selectrole_view.add_item(SelfRoleSelect(options))
                    await post_message.edit(view=selectrole_view)

    @initialize_selfassign.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)

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

    @discord.slash_command(name='roll',
                           description='Generates a random number unless you specify a maximum.')
    async def roll(self,
                   ctx: discord.ApplicationContext,
                   maximum: Option(int, 'Maximum number to roll (0-maximum)',
                                   min_value=1,
                                   default=100,
                                   required=False)):
        await ctx.interaction.response.defer()
        answer = random.randint(0, maximum)
        embed = gen_embed(name=f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator}',
                          icon_url=ctx.interaction.user.display_avatar.url,
                          title='Roll',
                          content=f'{ctx.interaction.user.mention} rolled a {str(answer)}')
        await ctx.interaction.followup.send(embed=embed)

    @discord.slash_command(name='froll',
                           description='Generates a forced roll - the number specified will be the number rolled')
    async def froll(self,
                    ctx: discord.ApplicationContext,
                    channel: Option(discord.SlashCommandOptionType.channel, 'Channel to send roll in'),
                    number: Option(int, 'Number to force roll',
                                   min_value=1)):
        await ctx.interaction.response.defer(ephemeral=True)
        embed = gen_embed(name=f'{ctx.interaction.user.name}#{ctx.interaction.user.discriminator}',
                          icon_url=ctx.interaction.user.display_avatar.url,
                          title='Roll',
                          content=f'{ctx.interaction.user.mention} rolled a {str(number)}')
        await channel.send(embed=embed)
        await ctx.interaction.followup.send(f'Sent roll in {channel.name}',
                                            ephemeral=True)

    async def time_autocomplete(self, ctx):
        return [timezone for timezone in TIMEZONE_DICT if timezone.startswith(ctx.value.upper())]

    @discord.slash_command(name='time',
                           description='Print current date & time in UTC, or timezone if specified')
    async def time(self,
                   ctx: discord.ApplicationContext,
                   timezone: Option(str, 'Timezone to display date & time',
                                    default='UTC',
                                    required=False,
                                    autocomplete=time_autocomplete)):
        await ctx.interaction.response.defer()

        # Get current time in UTC
        current_time = datetime.datetime.now(datetime.timezone.utc)

        # If a timezone is specified let's convert time into that timezone.
        if not timezone:
            timezone = 'UTC'

        timezone = timezone.upper()
        if re.search(r'(UTC)(\+-)(\d{2})(:\d{2})?', timezone):
            if not find_key(TIMEZONE_DICT, timezone):
                log.warning('Invalid Timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return
        else:
            try:
                timezone = TIMEZONE_DICT[timezone]
            except KeyError:
                log.warning('KeyError: Invalid timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return

        # Take care of the pesky 30/45 minute intervals that some timezones have
        if ":" in timezone:
            timezone_parsed = timezone.split(":")
            timezone_hour = timezone_parsed[0]
            timezone_minute = timezone_parsed[1]
            try:
                hour = int(timezone_hour[3:len(timezone_hour)])
                minute = int(timezone_minute)
            except ValueError:
                log.warning("ValueError: Invalid Timezone")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title="Input Error",
                                                              content="This is not a valid timezone."),
                                                    ephemeral=True)
                return

            current_time = current_time + timedelta(hours=hour, minutes=minute)
        else:
            try:
                hour = int(timezone[3:len(timezone)])
            except ValueError:
                log.warning("ValueError: Invalid Timezone")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title="Input Error",
                                                              content="This is not a valid timezone."),
                                                    ephemeral=True)
                return

            current_time = current_time + timedelta(hours=hour)

        current_time = current_time.strftime('%Y-%m-%d | %H:%M ' + timezone)
        embed = gen_embed(title='time',
                          content=f'The current time is: {current_time}')
        await ctx.interaction.followup.send(embed=embed)

    converttime = SlashCommandGroup('convert', 'Convert time between timezones')

    @converttime.command(name='time',
                         description='Convert a time between two timezones')
    async def tconvert(self,
                       ctx: discord.ApplicationContext,
                       time: Option(str, 'Time to convert'),
                       timezone_from: Option(str, 'Timezone to convert from',
                                             name="timezonefrom"),
                       timezone_to: Option(str, 'Timezone to convert to',
                                           name="timezoneto")):
        await ctx.interaction.response.defer()

        # Parse time first
        time_parsed = time.split(":")
        try:
            hour = int(time_parsed[0])
            minute = int(time_parsed[1])
        except (ValueError, IndexError) as e:
            log.warning("ValueError: Invalid Time")
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title="Input Error",
                                                          content=("This is not a valid time."
                                                                   "Accepted format: **##:##**")),
                                                ephemeral=True)
            return
        if hour > 23 or hour < 0 or minute > 59 or minute < 0:
            log.warning("Error: Invalid Time")
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title="Input Error",
                                                          content=("This is not a valid time. Make sure the hour is"
                                                                   " not negative or greater than 23, and that the"
                                                                   " minutes are between 00 and 59.")),
                                                ephemeral=True)
            return

        # Now parse from timezone and separate into hours and minutes, and get a combined minute version for calc
        timezone_from = timezone_from.upper()
        if re.search(r'(UTC)(\+-)(\d{1,2})(:\d{2})?', timezone_from):
            if not find_key(TIMEZONE_DICT, timezone_from):
                log.warning('Invalid Timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return
        else:
            try:
                timezone_from = TIMEZONE_DICT[timezone_from]
            except KeyError:
                log.warning('KeyError: Invalid timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return
        if ":" in timezone_from:
            timezone_from_parsed = timezone_from.split(":")
            try:
                timezone_from_hour = timezone_from_parsed[0]
                timezone_from_hour = int(timezone_from_hour[3:len(timezone_from_hour)])
                timezone_from_minute = int(timezone_from_parsed[1])
                if timezone_from_hour < 0:
                    timezone_from_combined = timezone_from_hour * 60 - timezone_from_minute
                elif timezone_from_hour > 0:
                    timezone_from_combined = timezone_from_hour * 60 + timezone_from_minute
                elif timezone_from_hour == 0:
                    timezone_from_combined = 0
            except ValueError:
                log.warning("ValueError: Timezone Dictionary Error")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Timezone Dictionary Error',
                                                              content='Error with the timezone dictionary.'),
                                                    ephemeral=True)
                return
        else:
            try:
                timezone_from_hour = int(timezone_from[3:len(timezone_from)])
                timezone_from_combined = timezone_from_hour * 60
            except ValueError:
                log.warning("ValueError: Timezone Parse Error")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Timezone Parse Error',
                                                              content='Could not parse timezone.'),
                                                    ephemeral=True)
                return

        timezone_to = timezone_to.upper()
        if re.search(r'(UTC)(\+-)(\d{1,2})(:\d{2})?', timezone_to):
            if not find_key(TIMEZONE_DICT, timezone_to):
                log.warning('Invalid Timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return
        else:
            try:
                timezone_to = TIMEZONE_DICT[timezone_to]
            except KeyError:
                log.warning('KeyError: Invalid timezone')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Input Error',
                                                              content='This is not a valid timezone.'),
                                                    ephemeral=True)
                return

        timezone_from_combined = 0
        timezone_to_combined = 0

        if ":" in timezone_to:
            timezone_to_parsed = timezone_to.split(":")
            try:
                timezone_to_hour = timezone_to_parsed[0]
                timezone_to_hour = int(timezone_to_hour[3:len(timezone_to_hour)])
                timezone_to_minute = int(timezone_to_parsed[1])
                if timezone_to_hour < 0:
                    timezone_to_combined = timezone_to_hour * 60 - timezone_to_minute
                elif timezone_to_hour > 0:
                    timezone_to_combined = timezone_to_hour * 60 + timezone_to_minute
                elif timezone_to_hour == 0:
                    timezone_to_combined = 0
            except ValueError:
                log.warning("ValueError: Timezone Dictionary Error")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Timezone Dictionary Error',
                                                              content='Error with the timezone dictionary.'),
                                                    ephemeral=True)
                return
        else:
            try:
                timezone_to_hour = int(timezone_to[3:len(timezone_to)])
                timezone_to_combined = timezone_to_hour * 60
            except ValueError:
                log.warning("ValueError: Timezone Parse Error")
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Timezone Parse Error',
                                                              content='Could not parse timezone.'),
                                                    ephemeral=True)
                return

        # Logic time - catch all the different time conversion scenarios that could happen
        difference = 0
        if timezone_from_hour == 0:
            difference = timezone_to_combined
        elif timezone_to_hour == 0:
            if timezone_from_hour < timezone_to_hour:
                difference = abs(timezone_from_combined)
            elif timezone_from_hour > timezone_to_hour:
                difference = -timezone_from_combined
        elif timezone_from_hour < 0 and timezone_to_hour < 0:
            difference = abs(timezone_from_combined) - abs(timezone_to_combined)
        elif timezone_from_hour < 0 and timezone_to_hour > 0:
            difference = abs(timezone_from_combined) + abs(timezone_to_combined)
        elif timezone_from_hour > 0 and timezone_to_hour < 0:
            difference = -(abs(timezone_from_combined) + abs(timezone_to_combined))
        elif timezone_from_hour > 0 and timezone_to_hour > 0:
            difference = abs(timezone_from_combined - timezone_to_combined)

        converted_time = hour * 60 + minute + difference
        hour = int(converted_time / 60)
        if hour < 0:
            hour = 24 + hour
        if hour >= 24:
            hour = abs(24 - hour)
        minute = converted_time % 60

        if minute == 0:
            minute = str(minute) + "0"
        elif minute < 10:
            minute = "0" + str(minute)
        final_time = str(hour) + ":" + str(minute)

        embed = gen_embed(title='Convert Time',
                          content=f'Converted **{time} {timezone_from}** to **{timezone_to}** is **{final_time}**')
        await ctx.interaction.followup.send(embed=embed)

    selfroleassign = SlashCommandGroup('selfassign', 'Setup self-assign role commands')

    @selfroleassign.command(name='settings',
                            description='See active roles & setup')
    @default_permissions(manage_roles=True)
    async def selfassign_settings(self,
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

        class SelfRolePageButton(pages.PaginatorButton):
            def __init__(self, button_type, label=None, emoji=None, style=discord.ButtonStyle.success,
                         disabled=False, row=0):
                super().__init__(button_type,
                                 label=label,
                                 emoji=emoji,
                                 style=style,
                                 disabled=disabled,
                                 row=row)

            async def callback(self, interaction: discord.Interaction):
                if self.button_type == "first":
                    self.paginator.current_page = 0
                elif self.button_type == "prev":
                    if self.paginator.loop_pages and self.paginator.current_page == 0:
                        self.paginator.current_page = self.paginator.page_count
                    else:
                        self.paginator.current_page -= 1
                elif self.button_type == "next":
                    if self.paginator.loop_pages and self.paginator.current_page == self.paginator.page_count:
                        self.paginator.current_page = 0
                    else:
                        self.paginator.current_page += 1
                elif self.button_type == "last":
                    self.paginator.current_page = self.paginator.page_count
                page_num = self.paginator.current_page

                current_page = self.paginator.pages[self.paginator.current_page]
                if re.match(r"\d{17,18}", current_page.footer.text):
                    current_view = self.paginator.custom_view
                    current_view.enable_all_items()
                    category_id = int(current_page.footer.text)
                    doc = await db.rolereact.find_one({"msg_id": category_id})
                    cat_roles = doc['roles']
                    if cat_roles:
                        if len(cat_roles) == 0:
                            current_view.children[6].disabled = True
                            current_view.children[7].disabled = True
                    else:
                        current_view.children[6].disabled = True
                        current_view.children[7].disabled = True
                    self.paginator.update_custom_view(current_view)

                    self.paginator.current_page = page_num
                    await self.paginator.goto_page(page_number=self.paginator.current_page, interaction=interaction)
                else:
                    current_view = self.paginator.custom_view
                    for i in range(1, 8):
                        if i != 2:
                            current_view.children[i].disabled = True
                    self.paginator.update_custom_view(current_view)

                    self.paginator.current_page = page_num
                    await self.paginator.goto_page(page_number=self.paginator.current_page, interaction=interaction)

        class SelfRoleView(discord.ui.View):
            def __init__(self, context, bot, cat_pages, pgntr):
                super().__init__()
                self.context = context
                self.bot = bot
                self.pages = cat_pages
                self.paginator = pgntr
                self.value = ''

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                await self.paginator.disable(include_custom=True, page=self.pages[0])
                self.stop()

            async def get_document(self, interaction: discord.Interaction):
                category_id = interaction.message.embeds[0].footer.text
                return await db.rolereact.find_one({"msg_id": category_id})

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=1)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(label='Set Channel',
                               style=discord.ButtonStyle.primary,
                               row=1)
            async def configure_channel(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def channel_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure channel',
                                            content=('Please mention the channel you'
                                                     ' would like to use for this self-assign role category.')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Self-assign role channel configuration',
                                            content='Self-assign role channel configuration has been cancelled.'),
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
                        return await channel_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                await interaction.response.defer()

                new_channel_msg = await channel_prompt(interaction.channel)
                if new_channel_msg:
                    log.info('New channel entered, confirm workflow')
                    view = Confirm()
                    new_channel = new_channel_msg.channel_mentions[0]
                    await new_channel_msg.delete()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Announcement Channel: {new_channel.mention}**')),
                        view=view)
                    channel_timeout = await view.wait()
                    if channel_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        new_doc = await db.rolereact.find_one({"server_id": interaction.guild_id,
                                                               "msg_id": int(interaction.message.embeds[0].footer.text)})

                        post_embed = gen_embed(title=new_doc['category_name'],
                                               content=new_doc['category_description'])
                        try:
                            post_message = await new_channel.send(embed=post_embed)
                        except discord.Forbidden:
                            await interaction.followup.send(embed=gen_embed(
                                title='Permission Error',
                                content=('I cannot post in the specified channel. '
                                         'Please check your server permissions.')),
                                ephemeral=True)
                            return

                        await db.rolereact.update_one({"server_id": interaction.guild_id,
                                                       "msg_id": interaction.message.embeds[0].footer.text},
                                                      {"$set": {'channel_id': new_channel.id,
                                                                'msg_id': post_message.id}})

                        selectrole_view = discord.ui.View(timeout=None)
                        options = []
                        if len(new_doc['roles']) > 0:
                            for role_id, emoji_id in new_doc['roles'].items():
                                r = discord.utils.get(interaction.guild.roles, id=int(role_id))
                                if re.match(r'\d{17,18}', str(emoji_id)):
                                    e = None
                                    for _guild in self.bot.guilds:
                                        e = discord.utils.get(interaction.guild.emojis, id=int(emoji_id))
                                        if e:
                                            break
                                        else:
                                            continue
                                else:
                                    e = emoji_id
                                options.append(discord.SelectOption(label=r.name,
                                                                    value=str(r.id),
                                                                    emoji=e))

                            selectrole_view.add_item(SelfRoleSelect(options))
                            await post_message.edit(view=selectrole_view)

                        current_page = self.paginator.current_page
                        self.pages[current_page].description = \
                            (f"{category_description}\n\n**Configured Channel:**"
                             f" {new_channel.mention}")
                        await self.paginator.update(pages=self.pages)

            @discord.ui.button(label='New Category',
                               style=discord.ButtonStyle.primary,
                               row=2)
            async def new_category(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def channel_prompt(listen_channel, attempts=1, prev_message=None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    try:
                        sent_prompt = await listen_channel.send(
                            embed=gen_embed(title='Configure channel',
                                            content=('Please mention the channel you'
                                                     ' would like to use for this self-assign role category.')))
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(['Send Messages'],
                                                             'Forbidden 403 - could not send message to user.')

                    try:
                        mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                    except asyncio.TimeoutError:
                        await sent_prompt.delete()
                        await interaction.followup.send(
                            embed=gen_embed(title='Self-assign role channel configuration',
                                            content='Self-assign role channel configuration has been cancelled.'),
                            ephemeral=True)
                        return None
                    if prev_message:
                        await prev_message.delete()
                    await sent_prompt.delete()
                    if mmsg.channel_mentions:
                        return mmsg
                    elif attempts > 3:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='Cancelling operation due to too many failed attempts.'),
                            ephemeral=True)
                        return
                    else:
                        sent_error = await interaction.followup.send(
                            embed=gen_embed(title='Error',
                                            content='No channel found. Please check that you mentioned the channel.')
                        )
                        await mmsg.delete()
                        attempts += 1
                        return await channel_prompt(listen_channel, attempts=attempts, prev_message=sent_error)

                modal_prompt = SelfRoleModal('New Category')
                await interaction.response.send_modal(modal_prompt)
                await modal_prompt.wait()

                if modal_prompt.title_value and modal_prompt.desc_value:
                    new_channel_msg = await channel_prompt(interaction.channel)
                    if new_channel_msg:
                        log.info('New channel entered, confirm workflow')
                        view = Confirm()
                        new_channel = new_channel_msg.channel_mentions[0]
                        await new_channel_msg.delete()
                        sent_message = await interaction.followup.send(embed=gen_embed(
                            title='Confirmation',
                            content=('Please verify the contents before confirming:\n'
                                     f'**Selected Announcement Channel: {new_channel.mention}**')),
                            view=view)
                        channel_timeout = await view.wait()
                        if channel_timeout:
                            log.info('Confirmation view timed out')
                            await sent_message.delete()
                            return
                        await sent_message.delete()

                        if view.value:
                            log.info('Workflow confirm')
                            # Make message first
                            post_embed = gen_embed(title=modal_prompt.title_value,
                                                   content=modal_prompt.desc_value)
                            try:
                                post_message = await new_channel.send(embed=post_embed)
                            except discord.Forbidden:
                                await interaction.followup.send(embed=gen_embed(
                                    title='Permission Error',
                                    content=('I cannot post in the specified channel. '
                                             'Please check your server permissions.')),
                                    ephemeral=True)
                                return
                            post = {"server_id": interaction.guild_id,
                                    "msg_id": post_message.id,
                                    "channel_id": new_channel.id,
                                    "category_name": modal_prompt.title_value,
                                    "category_description": modal_prompt.desc_value,
                                    "roles": {}}
                            await db.rolereact.insert_one(post)
                            new_page_embed = gen_embed(title=modal_prompt.title_value,
                                                       content=(f"{modal_prompt.desc_value}\n\n**Configured Channel:**"
                                                                f" {new_channel.mention}"))
                            new_page_embed.add_field(name='Roles',
                                                     value='No roles added yet! Press "Add Role" to add a role.')
                            new_page_embed.set_footer(text=str(post_message.id))
                            self.pages.append(new_page_embed)
                            current_view = self.paginator.custom_view
                            current_view.enable_all_items()
                            current_view.children[6].disabled = True
                            current_view.children[7].disabled = True
                            await self.paginator.update(pages=self.pages,
                                                        custom_buttons=self.paginator.custom_buttons,
                                                        custom_view=self.paginator.custom_view)
                            self.paginator.current_page = self.paginator.page_count
                            await self.paginator.goto_page(page_number=self.paginator.page_count)

            @discord.ui.button(label='Edit Category',
                               style=discord.ButtonStyle.primary,
                               row=2)
            async def edit_category(self, button: discord.ui.Button, interaction: discord.Interaction):
                current_page = self.paginator.current_page
                category_id = int(self.pages[current_page].footer.text)
                category = await db.rolereact.find_one({"msg_id": category_id})
                category_title = category['category_name']
                category_desc = category['category_description']
                modal_prompt = SelfRoleModal(f'Edit {category_title}',
                                             category_title=category_title,
                                             category_desc=category_desc)
                await interaction.response.send_modal(modal_prompt)
                await modal_prompt.wait()

                if modal_prompt.title_value and modal_prompt.desc_value:
                    await db.rolereact.update_one({"msg_id": category_id},
                                                  {"$set": {'category_name': modal_prompt.title_value,
                                                            'category_description': modal_prompt.desc_value}})

                    cat_channel = ctx.guild.get_channel(int(category['channel_id']))
                    cat_message = await cat_channel.fetch_message(category_id)
                    cat_embed = cat_message.embeds[0]
                    cat_embed.title = modal_prompt.title_value
                    cat_embed.description = modal_prompt.desc_value
                    await cat_message.edit(embed=cat_embed)

                    self.pages[current_page].title = modal_prompt.title_value
                    self.pages[current_page].description = \
                        f"{modal_prompt.desc_value}\n\n**Configured Channel:** {cat_channel.mention}"
                    await self.paginator.update(pages=self.pages,
                                                custom_buttons=self.paginator.custom_buttons,
                                                custom_view=self.paginator.custom_view)
                    await self.paginator.goto_page(page_number=current_page)

            @discord.ui.button(label='Delete Category',
                               style=discord.ButtonStyle.danger,
                               row=2)
            async def delete_category(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                current_page = self.paginator.current_page
                category_id = int(self.pages[current_page].footer.text)
                doc = await db.rolereact.find_one({"msg_id": category_id})
                cat_channel = ctx.guild.get_channel(int(doc['channel_id']))
                await db.rolereact.delete_one({"msg_id": category_id})
                cat_message = await cat_channel.fetch_message(category_id)
                await cat_message.delete()
                self.pages.pop(current_page)
                self.paginator.current_page -= 1
                current_view = self.paginator.custom_view
                if self.paginator.current_page == 0:
                    for i in range(1, 8):
                        if i != 2:
                            current_view.children[i].disabled = True
                    pass
                await self.paginator.update(pages=self.pages,
                                            custom_buttons=self.paginator.custom_buttons,
                                            custom_view=current_view)
                await self.paginator.goto_page(page_number=current_page - 1)

            @discord.ui.button(label='Add Role',
                               style=discord.ButtonStyle.secondary,
                               row=3)
            async def add_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def role_prompt(listen_channel, attempts=1, prev_message=None, scenario: int = None):
                    def check(m):
                        return m.author == interaction.user and m.channel == listen_channel

                    match scenario:
                        # Role prompt scenario
                        case 1:
                            try:
                                sent_prompt = await listen_channel.send(
                                    embed=gen_embed(title='Add Role',
                                                    content=('Please mention the role OR enter the name/ID of the role'
                                                             ' you would like to use for this self-assign role.')))
                            except discord.Forbidden:
                                raise commands.BotMissingPermissions(['Send Messages'],
                                                                     'Forbidden 403 - could not send message to user.')

                            try:
                                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                            except asyncio.TimeoutError:
                                await sent_prompt.delete()
                                await interaction.followup.send(
                                    embed=gen_embed(title='Self-assign role configuration',
                                                    content='Self-assign role configuration has been cancelled.'),
                                    ephemeral=True)
                                return None
                            if prev_message:
                                await prev_message.delete()
                            await sent_prompt.delete()
                            if mmsg.role_mentions:
                                await mmsg.delete()
                                return mmsg.role_mentions[0]
                            elif attempts > 3:
                                sent_error = await interaction.followup.send(
                                    embed=gen_embed(title='Error',
                                                    content='Cancelling operation due to too many failed attempts.'),
                                    ephemeral=True)
                                return
                            else:
                                try:
                                    msg_role = interaction.guild.get_role(int(mmsg.clean_content))
                                    if msg_role:
                                        await mmsg.delete()
                                        return msg_role
                                    else:
                                        raise ValueError
                                except ValueError:
                                    msg_role = discord.utils.find(lambda r: r.name == mmsg.clean_content,
                                                                  interaction.guild.roles)
                                    if not msg_role:
                                        sent_error = await interaction.followup.send(
                                            embed=gen_embed(title='Error',
                                                            content='No role found. Please check that the role exists.'))
                                        await mmsg.delete()
                                        attempts += 1
                                        return await role_prompt(listen_channel,
                                                                 attempts=attempts,
                                                                 prev_message=sent_error,
                                                                 scenario=1)
                                    else:
                                        await mmsg.delete()
                                        return msg_role
                        # Emoji prompt scenario
                        case 2:
                            try:
                                sent_prompt = await listen_channel.send(
                                    embed=gen_embed(title='Add Role',
                                                    content=('Please enter the emoji you would like to use for this'
                                                             ' self-assign role.')))
                            except discord.Forbidden:
                                raise commands.BotMissingPermissions(['Send Messages'],
                                                                     'Forbidden 403 - could not send message to user.')

                            try:
                                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                            except asyncio.TimeoutError:
                                await sent_prompt.delete()
                                await interaction.followup.send(
                                    embed=gen_embed(title='Self-assign role emoji configuration',
                                                    content=('Self-assign role emoji configuration has been'
                                                             ' cancelled.')),
                                    ephemeral=True)
                                return None
                            if prev_message:
                                await prev_message.delete()
                            await sent_prompt.delete()

                            custom_emojis_raw = re.findall(r'<a?:\w*:\d*>', str(mmsg.content))
                            custom_emojis_formatted = [int(e.split(':')[2].replace('>', '')) for e in custom_emojis_raw]

                            formatted_content = emojize.demojize(mmsg.content)
                            unicode_emojis_raw = re.findall(r':\w*:', str(formatted_content))
                            unicode_emojis_formatted = [e.replace(':', '') for e in unicode_emojis_raw]

                            if len(custom_emojis_formatted) > 0:
                                entry = None
                                for g in self.bot.guilds:
                                    entry = discord.utils.get(g.emojis, id=custom_emojis_formatted[0])
                                    if entry:
                                        break
                                    else:
                                        continue
                                if entry:
                                    await mmsg.delete()
                                    return entry
                                else:
                                    sent_error = await interaction.followup.send(
                                        embed=gen_embed(title='Error',
                                                        content='No emoji found. Please enter an emoji.'))
                                    await mmsg.delete()
                                    attempts += 1
                                    return await role_prompt(listen_channel,
                                                             attempts=attempts,
                                                             prev_message=sent_error,
                                                             scenario=2)
                            elif len(unicode_emojis_formatted) > 0:
                                # log.info('unicode emoji!')
                                unicode_emoji = emojize.emojize(f':{unicode_emojis_formatted[0]}:')
                                await mmsg.delete()
                                return unicode_emoji
                            elif attempts > 3:
                                sent_error = await interaction.followup.send(
                                    embed=gen_embed(title='Error',
                                                    content='Cancelling operation due to too many failed attempts.'),
                                    ephemeral=True)
                                return
                            else:
                                sent_error = await interaction.followup.send(
                                    embed=gen_embed(title='Error',
                                                    content='No emoji found. Please enter an emoji.'))
                                await mmsg.delete()
                                attempts += 1
                                return await role_prompt(listen_channel,
                                                         attempts=attempts,
                                                         prev_message=sent_error,
                                                         scenario=2)

                await interaction.response.defer()
                new_role = await role_prompt(interaction.channel, scenario=1)
                if new_role:
                    log.info('New role entered, confirm workflow')
                    view = Confirm()
                    sent_message = await interaction.followup.send(embed=gen_embed(
                        title='Confirmation',
                        content=('Please verify the contents before confirming:\n'
                                 f'**Selected Role: {new_role.mention}**')),
                        view=view)
                    role_timeout = await view.wait()
                    if role_timeout:
                        log.info('Confirmation view timed out')
                        await sent_message.delete()
                        return
                    await sent_message.delete()

                    if view.value:
                        log.info('Workflow confirm')
                        new_emoji = await role_prompt(interaction.channel, scenario=2)
                        if new_emoji:
                            log.info('New emoji entered, confirm workflow')
                            view = Confirm()
                            sent_message = await interaction.followup.send(embed=gen_embed(
                                title='Confirmation',
                                content=('Please verify the contents before confirming:\n'
                                         f'**Selected Emoji: {str(new_emoji)}**')),
                                view=view)
                            emoji_timeout = await view.wait()
                            if emoji_timeout:
                                log.info('Confirmation view timed out')
                                await sent_message.delete()
                                return
                            await sent_message.delete()

                            if view.value:
                                # Confirmed, let's add the role, make a new select and edit the message, and update
                                # the paginator embed
                                cat_id = int(interaction.message.embeds[0].footer.text)
                                doc = await db.rolereact.find_one({"msg_id": cat_id})

                                # Add role to DB document
                                cat_roles = doc['roles']
                                if len(cat_roles) == 25:
                                    interaction.followup.send('Cannot add any more roles to this category!',
                                                              ephemeral=True)
                                    return
                                if isinstance(new_emoji, discord.Emoji):
                                    cat_roles[str(new_role.id)] = new_emoji.id
                                else:
                                    cat_roles[str(new_role.id)] = new_emoji
                                await db.rolereact.update_one({"msg_id": cat_id},
                                                              {"$set": {'roles': cat_roles}})

                                # Retrieve message, create new select, and update
                                post_channel = interaction.guild.get_channel(int(doc['channel_id']))
                                try:
                                    post_message = await post_channel.fetch_message(int(doc['msg_id']))
                                except discord.NotFound:
                                    post_embed = gen_embed(title=doc['category_name'],
                                                           content=doc['category_description'])
                                    post_message = await post_channel.send(embed=post_embed)
                                    await db.rolereact.update_one({"msg_id": doc['msg_id']},
                                                                  {"$set": {"msg_id": post_message.id}})

                                selectrole_view = discord.ui.View(timeout=None)
                                options = []

                                for role_id, emoji_id in cat_roles.items():
                                    r = discord.utils.get(interaction.guild.roles, id=int(role_id))
                                    if re.match(r'\d{17,18}', str(emoji_id)):
                                        e = None
                                        for _guild in self.bot.guilds:
                                            e = discord.utils.get(_guild.emojis, id=int(emoji_id))
                                            if e:
                                                break
                                            else:
                                                continue
                                    else:
                                        e = emoji_id
                                    options.append(discord.SelectOption(label=r.name,
                                                                        value=str(r.id),
                                                                        emoji=e))

                                selectrole_view.add_item(SelfRoleSelect(options))
                                await post_message.edit(view=selectrole_view)

                                # Update paginator embed with new roles list
                                r_content = ''
                                for p_role in cat_roles:
                                    raw_emoji = cat_roles[p_role]
                                    if re.match(r'\d{17,18}', str(raw_emoji)):
                                        r_emoji = None
                                        for g in self.bot.guilds:
                                            r_emoji = discord.utils.get(g.emojis, id=int(raw_emoji))
                                            if r_emoji:
                                                break
                                            else:
                                                continue
                                    else:
                                        r_emoji = f':{raw_emoji}:'
                                    p_role = ctx.guild.get_role(int(p_role))
                                    r_content += f'{str(r_emoji)} {p_role.name}\n'

                                current_page = self.paginator.current_page
                                self.pages[current_page].set_field_at(0,
                                                                      name='Roles',
                                                                      value=r_content,
                                                                      inline=False)
                                await self.paginator.update(pages=self.pages,
                                                            custom_buttons=self.paginator.custom_buttons,
                                                            custom_view=self.paginator.custom_view)
                                self.paginator.current_page = current_page
                                await self.paginator.goto_page(page_number=current_page)

            @discord.ui.button(label='Edit Role',
                               style=discord.ButtonStyle.secondary,
                               row=3)
            async def edit_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()

                cat_id = int(interaction.message.embeds[0].footer.text)
                doc = await db.rolereact.find_one({"msg_id": cat_id})
                cat_roles = doc['roles']

                selectrole_view = discord.ui.View()
                options = []

                # Create select menu to delete roles
                for role_id, emoji_id in cat_roles.items():
                    r = discord.utils.get(interaction.guild.roles, id=int(role_id))
                    if re.match(r'\d{17,18}', str(emoji_id)):
                        e = None
                        for _guild in self.bot.guilds:
                            e = discord.utils.get(_guild.emojis, id=int(emoji_id))
                            if e:
                                break
                            else:
                                continue
                    else:
                        e = emoji_id
                    options.append(discord.SelectOption(label=r.name,
                                                        value=str(r.id),
                                                        emoji=e))

                og_view = self.paginator.custom_view
                current_page = self.paginator.current_page

                class Cancel(discord.ui.Button):
                    def __init__(self, cat_pages, paginator):
                        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)
                        self.value = None
                        self.pages = cat_pages
                        self.paginator = paginator

                    async def interaction_check(self, cancel_interaction):
                        if cancel_interaction.user != ctx.author:
                            return False
                        return True

                    async def callback(self, c_interaction):
                        await c_interaction.response.send_message("Cancelled Operation.", ephemeral=True)
                        await self.paginator.update(pages=self.pages,
                                                    custom_buttons=self.paginator.custom_buttons,
                                                    custom_view=og_view)
                        self.paginator.current_page = current_page
                        await self.paginator.goto_page(page_number=current_page)

                class SelfRoleEdit(discord.ui.Select):
                    def __init__(self, role_options, cat_pages, paginator, bot=self.bot):
                        super().__init__(placeholder="Select your roles here!",
                                         min_values=0,
                                         max_values=len(role_options),
                                         options=role_options)
                        self.bot = bot
                        self.pages = cat_pages
                        self.paginator = paginator

                    async def callback(self, s_interaction: discord.Interaction):
                        async def emoji_prompt(listen_channel, attempts=1, prev_message=None, edit_role=None):
                            def check(m):
                                return m.author == interaction.user and m.channel == listen_channel

                            try:
                                sent_prompt = await listen_channel.send(
                                    embed=gen_embed(title='Add Role',
                                                    content=('Please enter the emoji you would like to use for'
                                                             f' {edit_role.mention}')))
                            except discord.Forbidden:
                                raise commands.BotMissingPermissions(['Send Messages'],
                                                                     'Forbidden 403 - could not send message to user.')
                            try:
                                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
                            except asyncio.TimeoutError:
                                await sent_prompt.delete()
                                await interaction.followup.send(
                                    embed=gen_embed(title='Self-assign role emoji configuration',
                                                    content=('Self-assign role emoji configuration has been'
                                                             ' cancelled.')),
                                    ephemeral=True)
                                return None
                            if prev_message:
                                await prev_message.delete()
                            await sent_prompt.delete()

                            custom_emojis_raw = re.findall(r'<a?:\w*:\d*>', str(mmsg.content))
                            custom_emojis_formatted = [int(e.split(':')[2].replace('>', '')) for e in
                                                       custom_emojis_raw]

                            formatted_content = emojize.demojize(mmsg.content)
                            unicode_emojis_raw = re.findall(r':\w*:', str(formatted_content))
                            unicode_emojis_formatted = [e.replace(':', '') for e in unicode_emojis_raw]

                            if len(custom_emojis_formatted) > 0:
                                entry = None
                                for _g in self.bot.guilds:
                                    entry = discord.utils.get(_g.emojis, id=custom_emojis_formatted[0])
                                    if entry:
                                        break
                                    else:
                                        continue
                                if entry:
                                    await mmsg.delete()
                                    return entry
                                else:
                                    sent_error = await interaction.followup.send(
                                        embed=gen_embed(title='Error',
                                                        content='No emoji found. Please enter an emoji.'))
                                    await mmsg.delete()
                                    attempts += 1
                                    return await emoji_prompt(listen_channel,
                                                              attempts=attempts,
                                                              prev_message=sent_error,
                                                              edit_role=edit_role)
                            elif len(unicode_emojis_formatted) > 0:
                                # log.info('unicode emoji!')
                                unicode_emoji = emojize.emojize(f':{unicode_emojis_formatted[0]}:')
                                await mmsg.delete()
                                return unicode_emoji
                            elif attempts > 3:
                                sent_error = await interaction.followup.send(
                                    embed=gen_embed(title='Error',
                                                    content='Cancelling operation due to too many failed attempts.'),
                                    ephemeral=True)
                                return
                            else:
                                sent_error = await interaction.followup.send(
                                    embed=gen_embed(title='Error',
                                                    content='No emoji found. Please enter an emoji.'))
                                await mmsg.delete()
                                attempts += 1
                                return await emoji_prompt(listen_channel,
                                                          attempts=attempts,
                                                          prev_message=sent_error,
                                                          edit_role=edit_role)

                        await s_interaction.response.send_message(f'You selected {self.values}', ephemeral=True)

                        # Wait for response, delete specified roles, update DB document
                        for value in self.values:
                            erole = discord.utils.get(interaction.guild.roles, id=int(value))
                            new_emoji = await emoji_prompt(interaction.channel, edit_role=erole)

                            if isinstance(new_emoji, discord.Emoji):
                                cat_roles[str(value)] = new_emoji.id
                            else:
                                cat_roles[str(value)] = new_emoji
                            await db.rolereact.update_one({"msg_id": cat_id},
                                                          {"$set": {'roles': cat_roles}})

                            # Retrieve message, create new select, and update
                            post_channel = interaction.guild.get_channel(int(doc['channel_id']))
                            try:
                                post_message = await post_channel.fetch_message(int(doc['msg_id']))
                            except discord.NotFound:
                                post_embed = gen_embed(title=doc['category_name'],
                                                       content=doc['category_description'])
                                post_message = await post_channel.send(embed=post_embed)
                                await db.rolereact.update_one({"msg_id": doc['msg_id']},
                                                              {"$set": {"msg_id": post_message.id}})

                            cat_select_view = discord.ui.View(timeout=None)
                            cat_options = []

                            for r_id, e_id in cat_roles.items():
                                s_role = discord.utils.get(interaction.guild.roles, id=int(r_id))
                                if re.match(r'\d{17,18}', str(e_id)):
                                    s_emoji = None
                                    for g in self.bot.guilds:
                                        s_emoji = discord.utils.get(g.emojis, id=int(e_id))
                                        if s_emoji:
                                            break
                                        else:
                                            continue
                                else:
                                    s_emoji = emoji_id
                                cat_options.append(discord.SelectOption(label=s_role.name,
                                                                        value=str(s_role.id),
                                                                        emoji=s_emoji))

                            cat_select_view.add_item(SelfRoleSelect(cat_options))
                            await post_message.edit(view=cat_select_view)

                            # Update paginator embed with new roles list
                            r_content = ''
                            for p_role in cat_roles:
                                raw_emoji = cat_roles[p_role]
                                if re.match(r'\d{17,18}', str(raw_emoji)):
                                    r_emoji = None
                                    for g in self.bot.guilds:
                                        r_emoji = discord.utils.get(g.emojis, id=int(raw_emoji))
                                        if r_emoji:
                                            break
                                        else:
                                            continue
                                else:
                                    r_emoji = f':{raw_emoji}:'
                                p_role = ctx.guild.get_role(int(p_role))
                                r_content += f'{str(r_emoji)} {p_role.name}\n'

                            self.pages[current_page].set_field_at(0,
                                                                  name='Roles',
                                                                  value=r_content,
                                                                  inline=False)
                            await self.paginator.update(pages=self.pages,
                                                        custom_buttons=self.paginator.custom_buttons,
                                                        custom_view=og_view)
                            self.paginator.current_page = current_page
                            await self.paginator.goto_page(page_number=current_page)

                selectrole_view.add_item(SelfRoleEdit(options, self.pages, self.paginator))
                selectrole_view.add_item(Cancel(self.pages, self.paginator))
                await self.paginator.update(pages=self.pages,
                                            custom_buttons=self.paginator.custom_buttons,
                                            custom_view=selectrole_view)
                self.paginator.current_page = current_page
                await self.paginator.goto_page(page_number=current_page)

            @discord.ui.button(label='Delete Role',
                               style=discord.ButtonStyle.danger,
                               row=3)
            async def delete_role(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()

                cat_id = int(interaction.message.embeds[0].footer.text)
                doc = await db.rolereact.find_one({"msg_id": cat_id})
                cat_roles = doc['roles']

                selectrole_view = discord.ui.View()
                options = []

                # Create select menu to delete roles
                for role_id, emoji_id in cat_roles.items():
                    r = discord.utils.get(interaction.guild.roles, id=int(role_id))
                    if re.match(r'\d{17,18}', str(emoji_id)):
                        e = None
                        for _guild in self.bot.guilds:
                            e = discord.utils.get(_guild.emojis, id=int(emoji_id))
                            if e:
                                break
                            else:
                                continue
                    else:
                        e = emoji_id
                    options.append(discord.SelectOption(label=r.name,
                                                        value=str(r.id),
                                                        emoji=e))

                og_view = self.paginator.custom_view
                current_page = self.paginator.current_page

                class Cancel(discord.ui.Button):
                    def __init__(self, cat_pages, paginator):
                        super().__init__(label="Cancel", style=discord.ButtonStyle.danger)
                        self.value = None
                        self.pages = cat_pages
                        self.paginator = paginator

                    async def interaction_check(self, cancel_interaction):
                        if cancel_interaction.user != ctx.author:
                            return False
                        return True

                    async def callback(self, c_interaction):
                        await c_interaction.response.send_message("Cancelled Operation.", ephemeral=True)
                        await self.paginator.update(pages=self.pages,
                                                    custom_buttons=self.paginator.custom_buttons,
                                                    custom_view=og_view)
                        self.paginator.current_page = current_page
                        await self.paginator.goto_page(page_number=current_page)

                class SelfRoleEdit(discord.ui.Select):
                    def __init__(self, role_options, cat_pages, paginator, bot=self.bot):
                        super().__init__(placeholder="Select your roles here!",
                                         min_values=0,
                                         max_values=len(role_options),
                                         options=role_options)
                        self.bot = bot
                        self.pages = cat_pages
                        self.paginator = paginator

                    async def callback(self, s_interaction: discord.Interaction):
                        await s_interaction.response.send_message(f'You selected {self.values}', ephemeral=True)

                        # Wait for response, delete specified roles, update DB document
                        for value in self.values:
                            del cat_roles[str(value)]
                            await db.rolereact.update_one({"msg_id": cat_id},
                                                          {"$set": {'roles': cat_roles}})

                            # Retrieve message, create new select, and update
                            post_channel = interaction.guild.get_channel(int(doc['channel_id']))
                            try:
                                post_message = await post_channel.fetch_message(int(doc['msg_id']))
                            except discord.NotFound:
                                post_embed = gen_embed(title=doc['category_name'],
                                                       content=doc['category_description'])
                                post_message = await post_channel.send(embed=post_embed)
                                await db.rolereact.update_one({"msg_id": doc['msg_id']},
                                                              {"$set": {"msg_id": post_message.id}})

                            cat_select_view = discord.ui.View(timeout=None)
                            cat_options = []

                            for r_id, e_id in cat_roles.items():
                                s_role = discord.utils.get(interaction.guild.roles, id=int(r_id))
                                if re.match(r'\d{17,18}', str(e_id)):
                                    s_emoji = None
                                    for g in self.bot.guilds:
                                        s_emoji = discord.utils.get(g.emojis, id=int(e_id))
                                        if s_emoji:
                                            break
                                        else:
                                            continue
                                else:
                                    s_emoji = emoji_id
                                cat_options.append(discord.SelectOption(label=s_role.name,
                                                                        value=str(s_role.id),
                                                                        emoji=s_emoji))

                            cat_select_view.add_item(SelfRoleSelect(cat_options))
                            await post_message.edit(view=cat_select_view)

                            # Update paginator embed with new roles list
                            r_content = ''
                            for p_role in cat_roles:
                                raw_emoji = cat_roles[p_role]
                                if re.match(r'\d{17,18}', str(raw_emoji)):
                                    r_emoji = None
                                    for g in self.bot.guilds:
                                        r_emoji = discord.utils.get(g.emojis, id=int(raw_emoji))
                                        if r_emoji:
                                            break
                                        else:
                                            continue
                                else:
                                    r_emoji = f':{raw_emoji}:'
                                p_role = ctx.guild.get_role(int(p_role))
                                r_content += f'{str(r_emoji)} {p_role.name}\n'

                            self.pages[current_page].set_field_at(0,
                                                                  name='Roles',
                                                                  value=r_content,
                                                                  inline=False)
                            await self.paginator.update(pages=self.pages,
                                                        custom_buttons=self.paginator.custom_buttons,
                                                        custom_view=og_view)
                            self.paginator.current_page = current_page
                            await self.paginator.goto_page(page_number=current_page)

                selectrole_view.add_item(SelfRoleEdit(options, self.pages, self.paginator))
                selectrole_view.add_item(Cancel(self.pages, self.paginator))
                await self.paginator.update(pages=self.pages,
                                            custom_buttons=self.paginator.custom_buttons,
                                            custom_view=selectrole_view)
                self.paginator.current_page = current_page
                await self.paginator.goto_page(page_number=current_page)

        class SelfRoleModal(discord.ui.Modal):
            def __init__(self, modal_title, category_title=None, category_desc=None):
                super().__init__(title=modal_title)
                self.title_value = None
                self.desc_value = None
                if category_title or category_desc:
                    self.add_item(
                        InputText(
                            label='Category Title',
                            style=discord.InputTextStyle.short,
                            min_length=1,
                            max_length=256,
                            required=True,
                            value=category_title
                        ))
                    self.add_item(
                        InputText(
                            label='Category Description',
                            style=discord.InputTextStyle.long,
                            min_length=1,
                            max_length=2048,
                            required=True,
                            value=category_desc
                        ))
                else:
                    self.add_item(
                        InputText(
                            label='Category Title',
                            style=discord.InputTextStyle.short,
                            placeholder='Type the category title here',
                            min_length=1,
                            max_length=256,
                            required=True
                        ))
                    self.add_item(
                        InputText(
                            label='Category Description',
                            style=discord.InputTextStyle.long,
                            placeholder='Type the category description here',
                            min_length=1,
                            max_length=2048,
                            required=True
                        ))

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message('Modal info recieved!', ephemeral=True)
                self.title_value = self.children[0].value
                self.desc_value = self.children[1].value
                self.stop()

        categories = db.rolereact.find({"server_id": ctx.guild.id})
        cat_count = await db.rolereact.count_documents({"server_id": ctx.guild.id})
        category_pages = []
        if cat_count == 0:
            default_page = gen_embed(title='Self-Assign Role Settings',
                                     content=('No categories or roles set up! Use the buttons below to setup'
                                              ' self-assign roles.'))
            category_pages.append(default_page)
        else:
            default_page = gen_embed(title='Self-Assign Role Settings',
                                     content=(f'{str(cat_count)} categories found! Use the buttons below'
                                              f' to navigate each category.'))
            category_pages.append(default_page)
            async for document in categories:
                category_description = document['category_description']
                category_channel = ctx.guild.get_channel(int(document['channel_id']))
                page_embed = gen_embed(title=document['category_name'],
                                       content=(f"{category_description}\n\n**Configured Channel:**"
                                                f" {category_channel.mention}"))
                role_content = ''
                roles = document['roles']
                if roles:
                    if len(roles) > 0:
                        for role in roles:
                            r_e = roles[role]
                            if re.match(r'\d{17,18}', str(r_e)):
                                role_emoji = None
                                for sguild in self.bot.guilds:
                                    role_emoji = discord.utils.get(sguild.emojis, id=int(r_e))
                                    if role_emoji:
                                        break
                                    else:
                                        continue
                            else:
                                role_emoji = f':{r_e}:'
                            role = ctx.guild.get_role(int(role))
                            role_content += f'{str(role_emoji)} {role.name}\n'
                    else:
                        role_content = 'No roles added yet! Press "Add Role" to add a role.'
                else:
                    role_content = 'No roles added yet! Press "Add Role" to add a role.'
                page_embed.add_field(name='Roles',
                                     value=role_content)
                page_embed.set_footer(text=str(document['msg_id']))
                category_pages.append(page_embed)

        page_buttons = [
            SelfRolePageButton("first", emoji="⏪", style=discord.ButtonStyle.gray),
            SelfRolePageButton("prev", emoji="⬅", style=discord.ButtonStyle.gray),
            SelfRolePageButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True),
            SelfRolePageButton("next", emoji="➡", style=discord.ButtonStyle.gray),
            SelfRolePageButton("last", emoji="⏩", style=discord.ButtonStyle.gray),
        ]
        selfrole_paginator = pages.Paginator(pages=category_pages,
                                             show_disabled=True,
                                             show_indicator=True,
                                             use_default_buttons=False,
                                             custom_buttons=page_buttons)
        selfrole_view = SelfRoleView(ctx, self.bot, category_pages, selfrole_paginator)
        for index in range(1, 8):
            if index != 2:
                selfrole_view.children[index].disabled = True
        selfrole_paginator.update_custom_view(selfrole_view)
        await selfrole_paginator.respond(ctx.interaction, ephemeral=False)
        await selfrole_paginator.update(custom_buttons=page_buttons, custom_view=selfrole_view)


def setup(bot):
    bot.add_cog(Utility(bot))
