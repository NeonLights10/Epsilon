import asyncio
import time
import re
import datetime
from datetime import timedelta
from timeit import default_timer as timer

import pymongo

import discord
from discord.ext import commands, tasks
from discord.commands import Option, OptionChoice, SlashCommandGroup
from discord.ui import InputText

from formatting.embed import gen_embed, embed_splitter
from typing import Optional, List, SupportsInt
from __main__ import log, db

# Reminder system ported over for discord.py base and modified from PhasecoreX's Cogs for Red-DiscordBot
# https://github.com/PhasecoreX/PCXCogs

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


class Reminder(commands.Cog):
    SEND_DELAY_SECONDS = 30

    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()
        optional_in_every = r"(in\s+|every\s+)?"
        amount_and_time = r"\d+\s*(weeks?|w|days?|d|hours?|hrs|hr?|minutes?|mins?|m(?!o)|seconds?|secs?|s)"
        optional_comma_space_and = r"[\s,]*(and)?\s*"

        self.timedelta_begin = re.compile(
            r"^"
            + optional_in_every
            + r"("
            + amount_and_time
            + r"("
            + optional_comma_space_and
            + amount_and_time
            + r")*"
            + r")"
            + r"\b"
        )
        self.timedelta_end = re.compile(
            r"\b"
            + optional_in_every
            + r"("
            + amount_and_time
            + r"("
            + optional_comma_space_and
            + amount_and_time
            + r")*"
            + r")"
            + r"$"
        )
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    async def _do_check_reminders(self):
        # log.info('starting check for reminders')
        stime = int(time.time())
        to_remove = []
        group_send = []

        count = await db.reminders.estimated_document_count()

        if count > 0:
            query = {'future_time': {'$lt': stime}}
            reminders = db.reminders.find(query)

            async for reminder in reminders:
                user = await self.bot.get_or_fetch_user(reminder['user_id'])
                if user is None:
                    to_remove.append(reminder)
                else:
                    delay = int(stime) - int(reminder['future_time'])
                    embed = discord.Embed(
                        title=f":bell:{' (Delayed)' if delay > self.SEND_DELAY_SECONDS else ''} Reminder! :bell:",
                        colour=0x1abc9c
                    )
                    if delay > self.SEND_DELAY_SECONDS:
                        embed.set_footer(
                            text=(f"This was supposed to send {humanize_timedelta(seconds=delay)} ago."
                                  " I might be having network or server issues, or perhaps I just started up."
                                  " Sorry about that!"))
                    embed_name = f"From {reminder['future_timestamp']} ago:"
                    if reminder['repeat']:
                        embed_name = f"Repeating reminder every {humanize_timedelta(seconds=reminder['repeat'])}:"
                    reminder_text = reminder['reminder']
                    if len(reminder_text) > 900:
                        reminder_text = reminder_text[:897] + "..."
                    embed.add_field(
                        name=embed_name,
                        value=reminder_text,
                    )

                    if reminder['location'] == 'channel':
                        group_send.append(reminder)
                    elif reminder['location'] == 'dm':
                        try:
                            await user.send(embed=embed)
                        except discord.Forbidden:
                            # Can't send DMs to user, delete it
                            log.error('Could not send reminder dm to user, deleting reminder')
                            to_remove.append(reminder)
                        except discord.HTTPException:
                            # Something weird happened: retry next time
                            pass
                to_remove.append(reminder)

        if group_send:
            # take first reminder in list - check every other. if match, pop and save user id
            # send message with mentions first - then send embed
            # repeat until list is empty
            def group_reminder_exists(current_reminder, new_reminder):
                if (
                        current_reminder['reminder'] == new_reminder['reminder']
                        and current_reminder['future_time'] == new_reminder['future_time']
                        and current_reminder['future_timestamp'] == new_reminder['future_timestamp']
                ):
                    return True
                return False

            async def send_group_reminders(group_send_list):
                while len(group_send_list) != 0:
                    base_reminder = group_send_list.pop(0)
                    user_mentions = []
                    buser = await self.bot.get_or_fetch_user(base_reminder['user_id'])
                    user_mentions.append(buser.mention)
                    for greminder in group_send_list[:]:
                        if group_reminder_exists(base_reminder, greminder):
                            guser = self.bot.get_user(greminder['user_id'])
                            if guser is None:
                                pass
                            user_mentions.append(guser.mention)
                            group_send_list.remove(greminder)

                    gdelay = int(stime) - int(base_reminder['future_time'])
                    gembed = discord.Embed(
                        title=f":bell:{' (Delayed)' if delay > self.SEND_DELAY_SECONDS else ''} Reminder! :bell:",
                        colour=0x1abc9c
                    )
                    if gdelay > self.SEND_DELAY_SECONDS:
                        gembed.set_footer(
                            text=(f"This was supposed to send {humanize_timedelta(seconds=delay)} ago."
                                  " I might be having network or server issues, or perhaps I just started up."
                                  " Sorry about that!"))
                    gembed_name = f"From {base_reminder['future_timestamp']} ago:"
                    if base_reminder['repeat']:
                        gembed_name = f"Repeating reminder every {humanize_timedelta(seconds=base_reminder['repeat'])}:"
                    greminder_text = base_reminder['reminder']
                    if len(greminder_text) > 900:
                        greminder_text = greminder_text[:897] + "..."
                    gembed.add_field(
                        name=gembed_name,
                        value=greminder_text,
                    )
                    channel = self.bot.get_channel(base_reminder['channel_id'])
                    await channel.send(f"{''.join(user_mentions)}")
                    await channel.send(embed=embed)

            await send_group_reminders(group_send)

        if to_remove:
            for reminder in to_remove:
                if reminder['repeat']:
                    while reminder['future_time'] <= int(time.time()):
                        reminder['future_time'] += reminder['repeat']
                    reminder['future_timestamp'] = humanize_timedelta(seconds=reminder['repeat'])
                    reminder['creation_time'] = time.time()
                    await db.reminders.replace_one({'user_id': reminder['user_id'], 'nid': reminder['nid']},
                                                   reminder)
                else:
                    await db.reminders.delete_one({'user_id': reminder['user_id'], 'nid': reminder['nid']})

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        # start = timer()
        async with self.lock:
            await self._do_check_reminders()
        # end = timer()
        # log.info(f'{end - start}') (timing purposes)

    @check_reminders.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    remind = SlashCommandGroup('remind', 'Manage your reminders.')
    edit = remind.create_subgroup(name='edit', description='Edit your reminders')

    @remind.command(name='help',
                    description='Help and examples for reminders')
    async def remind_help(self,
                          ctx: discord.ApplicationContext):
        embed = gen_embed(title='Reminder Guide',
                          content=('\nEither of the following formats are allowed:'
                                   '\n`/remind me [in] <time> [to] [reminder_text]`'
                                   '\n`/remind me [to] [reminder_text] [in] <time>`'
                                   '\n\n`<time>` supports commas, spaces, and "and":'
                                   '\n`12h30m`, `6 hours 15 minutes`, `2 weeks, 4 days, and 10 seconds`'
                                   '\nAccepts seconds, minutes, hours, days, and weeks.'
                                   '\n\nYou can also add `every <repeat_time>` to the command for repeating reminders.'
                                   '\n`<repeat_time>` accepts days and weeks only, but otherwise is the same as '
                                   '`<time>`.')
                          )
        embed.add_field(name='Examples',
                        value=('\n`/remindme in 8min45sec to do that thing`'
                               '\n`/remindme to water my plants in 2 hours`'
                               '\n`/remindme in 3 days`'
                               '\n`/remindme 8h`'
                               '\n`/remindme every 1 week to take out the trash`'
                               '\n`/remindme in 1 hour to drink some water every 1 day`'))
        await ctx.respond(embed=embed, ephemeral=True)

    @remind.command(name='me',
                    description="Create a reminder with optional reminder text.")
    async def remindme(self,
                       ctx: discord.ApplicationContext,
                       reminder: Option(str, 'Reminder text',
                                        default='',
                                        required=False)):
        await ctx.interaction.response.defer()
        await self._create_reminder(ctx, reminder)

    @remind.command(name='list',
                    description='Show a list of all your reminders')
    async def list(self,
                   ctx: discord.ApplicationContext,
                   sort: Option(str, 'Can be sorted by reminder time or by time created.',
                                required=False,
                                choices=[OptionChoice('reminder'), OptionChoice('created')])):
        await ctx.interaction.response.defer(ephemeral=True)

        reminders = None
        reminder_exist = await db.reminders.count_documents({'user_id': ctx.author.id})
        if sort:
            if sort == 'reminder':
                reminders = db.reminders.find({'user_id': ctx.author.id}).sort('future_time', pymongo.DESCENDING)
            elif sort == 'created':
                reminders = db.reminders.find({'user_id': ctx.author.id}).sort('creation_time', pymongo.ASCENDING)
            else:
                log.warning('Invalid reminder sort option')
                await ctx.interaction.followup.send(embed=gen_embed(title="Invalid Sort Option Entered",
                                                                    content=f"Sort can be `reminder` or `added`."),
                                                    ephemeral=True)
                return
        else:
            reminders = db.reminders.find({'user_id': ctx.author.id})

        if reminder_exist == 0:
            await ctx.interaction.followup.send(embed=gen_embed(title="No Upcoming Reminders",
                                                                content=f"You don't have any upcoming reminders."),
                                                ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Reminders for {ctx.author.display_name}",
            color=0x1abc9c,
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        current_time = int(time.time())
        async for reminder in reminders:
            delta = reminder['future_time'] - current_time
            reminder_title = "ID# {} — {}".format(
                reminder['nid'],
                "In {}".format(humanize_timedelta(seconds=delta))
                if delta > 0
                else "Now!",
            )
            if reminder['repeat']:
                reminder_title = (
                    f"{reminder_title.rstrip('!')}, "
                    f"repeating every {humanize_timedelta(seconds=reminder['repeat'])}"
                )
            reminder_text = reminder['reminder']
            reminder_text = reminder_text or "(no reminder text)"
            embed.add_field(
                name=reminder_title,
                value=reminder_text,
                inline=False,
            )

        await embed_splitter(embed, ctx.channel, ctx.interaction.followup)

    @remind.command(name='delete',
                    description='Delete a reminder.')
    async def remove(self,
                     ctx: discord.ApplicationContext,
                     index: Option(str, 'Can either be the ID of a reminder, [all], or [last]')):
        await ctx.interaction.response.defer(ephemeral=True)
        await self._delete_reminder(ctx, index)

    @edit.command(name='text',
                  description="Change/modify the text of an existing reminder")
    async def text(self,
                   ctx: discord.ApplicationContext,
                   reminder_id: Option(int, 'Unique ID of the reminder to change',
                                       min_value=1)):
        class ReminderModal(discord.ui.Modal):
            def __init__(self, modal_title, reminder_text=None):
                super().__init__(title=modal_title)
                self.reminder_text_value = None
                self.add_item(
                    InputText(
                        label='Reminder Text',
                        style=discord.InputTextStyle.long,
                        min_length=1,
                        max_length=900,
                        required=True,
                        value=reminder_text
                    ))

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.send_message('Modal info recieved!', ephemeral=True)
                self.reminder_text_value = self.children[0].value
                self.stop()

        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.respond(embed=gen_embed(title="Could Not Find Reminder",
                                              content=(f"I couldn't find any reminder with id {reminder_id}.'"
                                                       f" Check the id again to ensure it is correct.")),
                              ephemeral=True)
            return
        reminder_edit_modal = ReminderModal(f'Reminder {reminder_id}', reminder['reminder'])
        await ctx.interaction.response.send_modal(reminder_edit_modal)
        await reminder_edit_modal.wait()

        if reminder_edit_modal.reminder_text_value:
            await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id},
                                          {"$set": {'reminder': reminder_edit_modal.reminder_text_value}})
            await ctx.respond(embed=gen_embed(title="Reminder Edited Successfuly",
                                              content=(f'Your reminder text for reminder {reminder_id}'
                                                       ' has been changed successfuly.')))

    @edit.command(name='repeat',
                  description="Change/modify the repeating time of an existing reminder.")
    async def repeat(self,
                     ctx,
                     reminder_id: Option(int, 'Unique ID of the reminder to change',
                                         min_value=1),
                     repeat: Option(str,
                                    'New repeating time. Enter [0, stop, none, cancel, false] to stop repeating.')):
        await ctx.interaction.response.defer(ephemeral=True)
        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.respond(embed=gen_embed(
                title="Could Not Find Reminder",
                content=(f"I couldn't find any reminder with id {reminder_id}."
                         f" Check the id again to ensure it is correct.")),
                ephemeral=True)
            return
        if repeat.lower() in ["0", "stop", "none", "false", "no", "cancel", "n"]:
            await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id}, {"$set": {'repeat': None}})
            await ctx.respond(embed=gen_embed(
                title="Repeating Reminder Disabled",
                content=(f"Reminder {reminder_id} will no longer repeat. The final reminder will be sent in"
                         f" {humanize_timedelta(seconds=int(reminder['future_time'] - time.time()))}.")),
                ephemeral=True)
        else:
            try:
                time_delta = parse_timedelta(repeat, minimum=timedelta(days=1), allowed_units=['weeks', 'days'])
            except commands.BadArgument as ba:
                await ctx.respond(embed=gen_embed(title='Reminder Edit', content=str(ba)), ephemeral=True)
                return
            await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id},
                                          {"$set": {'repeat': int(time_delta.total_seconds())}})
            await ctx.respond(embed=gen_embed(
                title="Reminder Edited Successfuly",
                content=(f"Reminder {reminder_id} will now remind you every {humanize_timedelta(timedelta=time_delta)},"
                         f" with the first reminder being sent in "
                         f"{humanize_timedelta(seconds=int(reminder['future_time'] - time.time()))}.")),
                ephemeral=True)

    @edit.command(name='time',
                  description="Change/modify the time of an existing reminder")
    async def mtime(self,
                    ctx: discord.ApplicationContext,
                    reminder_id: Option(int, 'Unique ID of the reminder to change',
                                        min_value=1),
                    new_time: Option(str, 'New time for the reminder')):
        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.respond(embed=gen_embed(
                title="Could not find reminder",
                content=(f"I couldn't find any reminder with id {reminder_id}."
                         f" Check the id again to ensure it is correct.")),
                ephemeral=True)
            return
        try:
            time_delta = parse_timedelta(new_time, minimum=timedelta(minutes=1))
        except commands.BadArgument as ba:
            await ctx.respond(embed=gen_embed(title='Reminder Edit', content=str(ba)), ephemeral=True)
            return
        future = int(time.time() + time_delta.total_seconds())
        future_timestamp = humanize_timedelta(timedelta=time_delta)
        await db.reminders.update_one({'user_id': ctx.author.id, "nid": reminder_id},
                                      {"$set": {'future_time': future, 'future_timestamp': future_timestamp}})
        message = f"Reminder {reminder_id} will now remind you in {future_timestamp}"
        if reminder['repeat']:
            message += f", repeating every {humanize_timedelta(seconds=reminder['repeat'])} thereafter."
        else:
            message += '.'
        await ctx.respond(embed=gen_embed(title="Reminder Edited Successfuly",
                                          content=message),
                          ephemeral=True)

    async def _create_reminder(self, ctx, time_and_optional_text: str):
        class ReminderLocationView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.value = None

            @discord.ui.button(label="DM", style=discord.ButtonStyle.primary)
            async def dm_location(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                for item in self.children:
                    item.disabled = True
                self.value = 1
                self.stop()

            @discord.ui.button(label="Channel", style=discord.ButtonStyle.primary)
            async def channel_location(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                for item in self.children:
                    item.disabled = True
                self.value = 2
                self.stop()

        try:
            (reminder_time, reminder_time_repeat, reminder_text) = self._process_reminder_text(
                time_and_optional_text.strip())
        except discord.ext.commands.BadArgument as ba:
            await ctx.interaction.followup.send(embed=gen_embed(title='remindme', content=str(ba)),
                                                ephemeral=True)
            return
        if not reminder_time:
            log.warning('Missing Required Argument')
            await ctx.interaction.followup.send(embed=gen_embed(
                title="Cannot Parse Reminder Time",
                content="I could not determine the time to wait before sending you this reminder! Please try again."),
                ephemeral=True)
            return
        if len(reminder_text) > 900:
            log.warning('Exceeded length limit')
            await ctx.interaction.followup.send(embed=gen_embed(
                title="Exceeded length limit",
                content='Your reminder text is too long (must be <900 characters)'),
                ephemeral=True)
            return

        msg_location_view = ReminderLocationView()
        sent_prompt = await ctx.interaction.followup.send(embed=gen_embed(
            title='Reminder Location',
            content=('Where would you like to be reminded? Available options are [channel] to be reminded here,'
                     ' or [dm] to be reminded in dms.')),
                                                          view=msg_location_view)
        await msg_location_view.wait()
        await sent_prompt.delete()
        if not msg_location_view.value:
            log.info('Cancelled operation')
            await ctx.interaction.followup.send(content='Reminder has been cancelled.',
                                                ephemeral=True)
            return

        location = None
        if msg_location_view.value == 2:
            location = 'channel'
        elif msg_location_view.value == 1:
            location = 'dm'

        repeat = (int(reminder_time_repeat.total_seconds()) if reminder_time_repeat else None)
        future_timeunix = int(time.time() + reminder_time.total_seconds())
        future_timestamp = humanize_timedelta(timedelta=reminder_time)

        query = {'nid_index': {"$exists": True}}
        qdocument = await db.reminders.find_one(query)
        old_nid = qdocument['nid_index']
        nid = old_nid + 1
        post = {
            'nid': nid,
            'user_id': ctx.author.id,
            'channel_id': ctx.channel.id,
            'creation_date': time.time(),
            'reminder': reminder_text,
            'repeat': repeat,
            'future_time': future_timeunix,
            'future_timestamp': future_timestamp,
            'query_id': None,
            'location': location
        }
        reminder = await db.reminders.insert_one(post)
        await db.reminders.update_one({"nid_index": old_nid}, {"$set": {'nid_index': nid}})

        message = f"I will remind you of {'that' if reminder_text else 'this'} "
        if repeat:
            message += f"every {humanize_timedelta(timedelta=reminder_time_repeat)}"
        else:
            message += f"in {future_timestamp}"
        if repeat and reminder_time_repeat != reminder_time:
            message += f", with the first reminder in {future_timestamp}."
        else:
            message += "."
        await ctx.interaction.followup.send(embed=gen_embed(title='Reminder set!',
                                                            content=message))

        query: discord.Message = await ctx.send(embed=gen_embed(
            title='Want to be reminded too?',
            content=(f"If anyone else would like {'these reminders' if repeat else 'to be reminded'}"
                     f" as well, click the bell below!")))
        db.reminders.update_one({"_id": reminder.inserted_id}, {"$set": {'query_id': query.id}})
        await query.add_reaction('\N{BELL}')
        await query.delete(delay=30.0)

    #############################

    def _process_reminder_text(self, reminder_text):
        """Completely process the given reminder text into timedeltas, removing them from the reminder text.
        Takes all "every {time_repeat}", "in {time}", and "{time}" from the beginning of the reminder_text.
        At most one instance of "every {time_repeat}" and one instance of "in {time}" or "{time}" will be consumed.
        If the parser runs into a timedelta (in or every) that has already been parsed, parsing stops.
        Same process is then repeated from the end of the string.
        If an "every" time is provided but no "in" time, the "every" time will be copied over to the "in" time.
        """

        reminder_time = None
        reminder_time_repeat = None
        # find the time delta(s) at the beginning of the text
        (
            reminder_time,
            reminder_time_repeat,
            reminder_text,
        ) = self._process_reminder_text_from_ends(reminder_time, reminder_time_repeat, reminder_text,
                                                  self.timedelta_begin)
        # find the time delta(s) at the end of the text
        (
            reminder_time,
            reminder_time_repeat,
            reminder_text,
        ) = self._process_reminder_text_from_ends(reminder_time, reminder_time_repeat, reminder_text,
                                                  self.timedelta_end)

        # cleanup
        reminder_time = reminder_time or reminder_time_repeat
        if len(reminder_text) > 1 and reminder_text[0:2] == "to":
            reminder_text = reminder_text[2:].strip()
        return reminder_time, reminder_time_repeat, reminder_text

    def _process_reminder_text_from_ends(self, reminder_time, reminder_time_repeat, reminder_text, search_regex):
        """Repeatedly regex search and modify the reminder_text looking for all instances of timedeltas."""
        regex_result = search_regex.search(reminder_text)
        while regex_result:
            repeating = regex_result[1] and regex_result[1].strip() == "every"
            if (repeating and reminder_time_repeat) or (not repeating and reminder_time):
                break
            parsed_timedelta = self._parse_timedelta(regex_result[2], repeating)
            if not parsed_timedelta:
                break
            reminder_text = (
                    reminder_text[0: regex_result.span()[0]] + reminder_text[regex_result.span()[1] + 1:]).strip()
            if repeating:
                reminder_time_repeat = parsed_timedelta
            else:
                reminder_time = parsed_timedelta
        return reminder_time, reminder_time_repeat, reminder_text

    @staticmethod
    def _parse_timedelta(timedelta_string, repeating):
        """Parse a timedelta, taking into account if it is a repeating timedelta (day minimum) or not."""
        result = None
        testing_text = ""
        for chunk in timedelta_string.split():
            if chunk == "and":
                continue
            if chunk.isdigit():
                testing_text += chunk
                continue
            testing_text += chunk.rstrip(",")
            if repeating:
                try:
                    parsed = parse_timedelta(
                        testing_text,
                        minimum=timedelta(hours=1),
                        allowed_units=["weeks", "days", "hours"],
                    )
                except commands.BadArgument as ba:
                    orig_message = str(ba)[0].lower() + str(ba)[1:]
                    raise discord.ext.commands.BadArgument(
                        f"For the repeating portion of this reminder, {orig_message}. "
                        "You must only use `days`, `weeks`, or `hours` when dealing with repeating reminders."
                    )
            else:
                parsed = parse_timedelta(testing_text, minimum=timedelta(minutes=1))
            if parsed != result:
                result = parsed
            else:
                return None
        return result

    async def _delete_reminder(self, ctx, index: str):
        def check(m):
            return m.author == ctx.user

        query = {'user_id': ctx.user.id}
        num_reminders = await db.reminders.count_documents(query)

        if num_reminders <= 0:
            await ctx.interaction.followup.send(embed=gen_embed(title='No Reminders Found',
                                                                content="You don't have any upcoming reminders."),
                                                ephemeral=True)
            return

        if index == 'all':
            sent_prompt = await ctx.interaction.followup.send(('Are you **sure** you want to remove all your reminders?'
                                                               ' (yes/no)'))
            resp = None
            try:
                resp = await self.bot.wait_for('message', check=check, timeout=30)
            except asyncio.TimeoutError:
                pass
            if resp.content == 'yes':
                await sent_prompt.delete()
                pass
            else:
                await sent_prompt.delete()
                await ctx.interaction.followup.send(embed=gen_embed(title='Deletion cancelled',
                                                                    content='I have left your reminders alone.'),
                                                    ephemeral=True)
                return
            await db.reminders.delete_many(query)
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Reminders Deleted',
                                                          content='All of your reminders have been deleted.'),
                                                ephemeral=True)
            return

        if index == 'last':
            reminder_to_delete = db.reminders.find_one(query, {'sort': {'$natural': -1}})
            rid = reminder_to_delete['nid']
            await db.reminders.delete_one(query, {'sort': {'$natural': -1}})
            await ctx.interaction.followup.send(embed=gen_embed(
                title='Latest Reminder Deleted',
                content=f"Your most recently created reminder (ID: {rid}) has been deleted."),
                ephemeral=True)
            return
        else:
            try:
                index = int(index)
            except ValueError:
                raise discord.ext.commands.BadArgument(
                    f"`{index}` is not a valid ID for this command"
                )
            uquery = {'user_id': ctx.author.id, 'nid': index}
            reminder_to_delete = await db.reminders.find_one(uquery)
            if reminder_to_delete:
                rid = reminder_to_delete['nid']
                await db.reminders.delete_one(uquery)
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Reminder Deleted',
                                                              content=f"Reminder (ID: {rid}) has been deleted."),
                                                    ephemeral=True)
            else:
                log.error(f'Reminder {index} could not be found')
                await ctx.interaction.followup.send(embed=
                                                    gen_embed(title='Reminder Could Not Be Found',
                                                              content=f"Check the ID or spelling of the parameter."),
                                                    ephemeral=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        async def reminder_exists(new_reminder):
            async for document in db.reminders.find():
                try:
                    if (
                            document['user_id'] == new_reminder['user_id']
                            and document['reminder'] == new_reminder['reminder']
                            and document['future_time'] == new_reminder['future_time']
                            and document['future_timestamp'] == new_reminder['future_timestamp']
                    ):
                        return True
                    return False
                except KeyError:
                    continue

        if not payload.guild_id:
            return
        if str(payload.emoji) != "\N{BELL}":
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.NotFound:
                return
        if member.bot:
            return

        found_reminder = await db.reminders.find_one({'query_id': payload.message_id})
        if found_reminder:
            reminder_text = found_reminder['reminder']
            repeat = found_reminder['repeat']
            future_time = found_reminder['future_time']
            future_timestamp = found_reminder['future_timestamp']
            location = found_reminder['location']
            query = {'nid_index': {"$exists": True}}
            qdocument = await db.reminders.find_one(query)
            old_nid = qdocument['nid_index']
            nid = old_nid + 1
            channel = guild.get_channel(payload.channel_id)
            post = {
                'nid': nid,
                'user_id': member.id,
                'channel_id': channel,
                'creation_date': time.time(),
                'reminder': reminder_text,
                'repeat': repeat,
                'future_time': future_time,
                'future_timestamp': future_timestamp,
                'query_id': None,
                'location': location
            }
            if await reminder_exists(post):
                return
            await db.reminders.insert_one(post)
            await db.reminders.update_one({'nid_index': old_nid}, {"$set": {'nid_index': nid}})
            message = 'Hello! I will also send you '
            if post['repeat']:
                human_repeat = humanize_timedelta(seconds=post["repeat"])
                message += f"those reminders every {human_repeat}"
                if human_repeat != post["future_timestamp"]:
                    message += (
                        f", with the first reminder in {post['future_timestamp']}."
                    )
                else:
                    message += "."
            else:
                message += f"that reminder in {post['future_timestamp']}."

            try:
                await member.send(embed=gen_embed(title='Reminder added!', content=message))
            except (discord.Forbidden, discord.NotFound):
                log.warning('Could not send reminder DM to user')
                pass


def setup(bot):
    bot.add_cog(Reminder(bot))
