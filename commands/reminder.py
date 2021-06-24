import asyncio
import discord
import time
import re
import datetime
import pymongo
from datetime import timedelta

from discord.ext import commands, tasks
from formatting.embed import gen_embed, embed_splitter
from typing import Union, Optional, List, SupportsInt
from __main__ import log, db

#Reminder system ported over for discord.py base and modified from PhasecoreX's Cogs for Red-DiscordBot
#https://github.com/PhasecoreX/PCXCogs

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
                    "This amount of time is too large for this command. (Maximum: {maximum})".format(maximum=humanize_timedelta(timedelta=maximum))
                )
            if minimum and delta < minimum:
                raise discord.ext.commands.BadArgument(
                    "This amount of time is too small for this command. (Minimum: {minimum})".format(minimum=humanize_timedelta(timedelta=minimum))
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
        self.printer.cancel()

    @tasks.loop(seconds=10)
    async def check_reminders(self):
        stime = int(time.time())
        to_remove = []
        count = await db.reminders.estimated_document_count()
        if count > 0:
            query = {'future_time': {'$lt': stime}}
            reminders = db.reminders.find(query)
            async for reminder in reminders:
                user = self.bot.get_user(reminder['user_id'])
                if user is None:
                    to_remove.append(reminder)

                delay = int(stime) - int(reminder['future_time'])
                embed=discord.Embed(
                        title = f":bell:{' (Delayed)' if delay > self.SEND_DELAY_SECONDS else ''} Reminder! :bell:",
                        colour = 0x1abc9c
                )
                if delay > self.SEND_DELAY_SECONDS:
                    embed.set_footer(
                        text=f"""This was supposed to send {humanize_timedelta(seconds=delay)} ago.
                            I might be having network or server issues, or perhaps I just started up.
                            Sorry about that!"""
                    )
                embed_name = f"From {reminder['future_timestamp']} ago:"
                if reminder['repeat']:
                    embed_name = f"Repeating reminder every {humanize_timedelta(seconds=max(reminder['repeat'], 86400))}:"
                reminder_text = reminder['reminder']
                if len(reminder_text) > 900:
                    reminder_text = reminder_text[:897] + "..."
                if reminder['jump_link']:
                    reminder_text += f"\n\n[original message]({reminder['jump_link']})"
                embed.add_field(
                    name = embed_name,
                    value = reminder_text,
                )

                try:
                    await user.send(embed=embed)
                except (discord.errors.Forbidden, discord.errors.Forbidden):
                    #Can't send DMs to user, delete it
                    log.error('Could not send reminder dm to user, deleting reminder')
                    to_remove.append(reminder)
                except discord.HTTPException:
                    # Something weird happened: retry next time
                    pass
                to_remove.append(reminder)
        if to_remove:
            for reminder in to_remove:
                if reminder['repeat']:
                    if reminder['repeat'] < 86400:
                        reminder['repeat'] = 86400
                    while reminder['future_time'] <= int(time.time()):
                        reminder['future_time'] += reminder['repeat']
                    reminder['future_timestamp'] = humanize_timedelta(seconds=reminder['repeat'])
                    await db.reminders.replace_one({'user_id': reminder['user_id'], 'nid': reminder['nid']}, reminder)
                else:
                    await db.reminders.delete_one({'user_id': reminder['user_id'], 'nid': reminder['nid']})

    @check_reminders.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

    @commands.group(name='reminder',
                    description='Manage your reminders.')
    async def reminder(self, ctx):
        pass

    @commands.group(name='modify',
                    aliases=['edit', 'change'],
                    description='Modify your reminders.')
    async def modify(self, ctx):
        pass

    @commands.command(name='remindme',
                      description="""Create a reminder with optional reminder text.
                                \nEither of the following formats are allowed:
                                \n`%remindme [in] <time> [to] [reminder_text]`
                                \n`%remindme [to] [reminder_text] [in] <time>`
                                \n\n`<time>` supports commas, spaces, and "and":
                                \n`12h30m`, `6 hours 15 minutes`, `2 weeks, 4 days, and 10 seconds`
                                \nAccepts seconds, minutes, hours, days, and weeks.
                                \n\nYou can also add `every <repeat_time>` to the command for repeating reminders.
                                \n`<repeat_time>` accepts days and weeks only, but otherwise is the same as `<time>`.""",
                      help="""Examples:
                                \n`%remindme in 8min45sec to do that thing`
                                \n`%remindme to water my plants in 2 hours`
                                \n`%remindme in 3 days`
                                \n`%remindme 8h`
                                \n`%remindme every 1 week to take out the trash`
                                \n`%remindme in 1 hour to drink some water every 1 day`""")
    async def remindme(self, ctx, *, time_and_optional_text: str = ''):
        await self._create_reminder(ctx, time_and_optional_text)

    @reminder.command(name='list',
                      aliases=['get'],
                      description='Show a list of all your reminders.\n\n<Sort> can either be:\n`time` (default) for reminder that will expire soonest first,\n or `added` for ordering by when reminder was added.')
    async def list(self, ctx, sort: str = 'time'):
        reminders = None
        if sort == 'time':
            reminders = db.reminders.find({'user_id': ctx.author.id}).sort('future_time', pymongo.DESCENDING)
        elif sort =='added':
            reminders = db.reminders.find({'user_id': ctx.author.id}).sort('creation_time', pymongo.ASCENDING)
        else:
            log.warning('Invalid option')
            await ctx.reply(embed=gen_embed(title="Invalid sort option entered",
                                           content=f"Sort can be `time` or `added`."))
            return

        if not reminders:
            await ctx.reply(embed=gen_embed(title="No upcoming reminders",
                                            content=f"You don't have any upcoming reminders."))
            return

        embed = discord.Embed(
            title=f"Reminders for {ctx.author.display_name}",
            color= 0x1abc9c,
        )
        embed.set_thumbnail(url=ctx.author.avatar_url)
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
            if reminder['jump_link']:
                reminder_text += f"\n([original message]({reminder['jump_link']}))"
            reminder_text = reminder_text or "(no reminder text or jump link)"
            embed.add_field(
                name=reminder_title,
                value=reminder_text,
                inline=False,
            )

        await embed_splitter(embed, ctx.channel)

    @reminder.command(name='create',
                      aliases=['add'],
                      description='Create a reminder with optional reminder text.\nFunctions the same as %remindme.')
    async def create(self, ctx, *, time_and_optional_text: str = ''):
        await self._create_reminder(ctx, time_and_optional_text)

    @commands.command(name='forgetme',
                      description='Delete all your upcoming reminders.',
                      help='Usage:\n\n%forgetme')
    async def forgetme(self, ctx):
        await self._delete_reminder(ctx, 'all')

    @reminder.command(name='delete',
                      aliases=['remove','del'],
                      description="""Delete a reminder. 
                                    \n\n <index> can either be:
                                    \n- the unique id for the reminder to delete
                                    \n- `last` to delete the most recently created reminder
                                    \n- `all` to delete all reminders (same as %forgetme)""",
                      help='\n\nUsage:\n\n%reminder delete [index]')
    async def remove(self, ctx, index: str):
        await self._delete_reminder(ctx, index)

    @modify.command(name='text',
                      description="Change/modify the text of an existing reminder.\n\n <reminder_id> is the unique id of the reminder to change.",
                      help='\n\nUsage:\n\n%modify text [reminder_id] [new text]')
    async def text(self, ctx, reminder_id: int, *, text: str):
        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.reply(embed=gen_embed(title="Could not find reminder",
                                            content=f"I couldn't find any reminder with id {reminder_id}. Check the id again to ensure it is correct."))
            return
        text = text.strip()
        if len(text) > 900:
            log.warning('Exceeded length limit')
            await ctx.reply(embed=gen_embed(title="Exceeded length limit",
                                            content='Your reminder text is too long (must be <900 characters)'))
        await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id}, {"$set": {'reminder': text}})
        await ctx.reply(embed=gen_embed(title="Reminder edited successfuly",
                                        content=f'Your reminder text for reminder {reminder_id} has been changed successfuly.'))

    @modify.command(name='repeat',
                      description="Change/modify the repeating time of an existing reminder.\n\n <reminder_id> is the unique id of the reminder to change.\nSet time to 0/stop/none/false/no/cancel/n to disable repeating.",
                      help='\n\nUsage:\n\n%modify repeat [reminder_id] [new time]')
    async def repeat(self, ctx, reminder_id: int, *, time: str):
        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.reply(embed=gen_embed(title="Could not find reminder",
                                            content=f"I couldn't find any reminder with id {reminder_id}. Check the id again to ensure it is correct."))
            return
        if time.lower() in ["0", "stop", "none", "false", "no", "cancel", "n"]:
            await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id}, {"$set": {'repeat': None}})
            await ctx.reply(embed=gen_embed(title="Repeating reminder disabled",
                                            content=f"Reminder {reminder_id} will no longer repeat. The final reminder will be sent in {humanize_timedelta(seconds=int(reminder['future_time'] - time.time()))}."))
        else:
            try:
                time_delta = parse_timedelta(time, minimum=timedelta(days=1), allowed_units=['weeks', 'days'])
            except commands.BadArgument as ba:
                await ctx.reply(embed = gen_embed(title='remindme', content=str(ba)))
                return
            await db.reminders.update_one({'user_id': ctx.author.id, 'nid': reminder_id}, {"$set": {'repeat': int(time_delta.total_seconds())}})
            await ctx.reply(embed=gen_embed(title="Reminder edited successfuly",
                                            content=f"Reminder {reminder_id} will now remind you every {humanize_timedelta(timedelta=time_delta)}, with the first reminder being sent in {humanize_timedelta(seconds=int(reminder['future_time'] - time.time()))}."))

    @modify.command(name='time',
                    description="Change/modify the time of an existing reminder.\n\n <reminder_id> is the unique id of the reminder to change.",
                    help='\n\nUsage:\n\n%modify time [reminder_id] [new time]')
    async def mtime(self, ctx, reminder_id: int, *, ntime: str):
        reminder = await db.reminders.find_one({'user_id': ctx.author.id, 'nid': reminder_id})
        if not reminder:
            log.warning('No reminder found')
            await ctx.reply(embed=gen_embed(title="Could not find reminder",
                                            content=f"I couldn't find any reminder with id {reminder_id}. Check the id again to ensure it is correct."))
            return
        try:
            time_delta = parse_timedelta(ntime, minimum=timedelta(minutes=1))
        except commands.BadArgument as ba:
            await ctx.reply(embed=gen_embed(title='remindme', content=str(ba)))
            return
        future = int(time.time() + time_delta.total_seconds())
        future_timestamp = humanize_timedelta(timedelta=time_delta)
        await db.reminders.update_one({'user_id': ctx.author.id, "nid": reminder_id}, {"$set": {'future_time': future, 'future_timestamp': future_timestamp}})
        message = f"Reminder {reminder_id} will now remind you in {future_timestamp}"
        if reminder['repeat']:
            message += f", repeating every {humanize_timedelta(seconds=reminder['repeat'])} thereafter."
        else:
            message += '.'
        await ctx.reply(embed=gen_embed(title="Reminder edited successfuly",
                                        content=message))

    async def _create_reminder(self, ctx, time_and_optional_text: str):
        try:
            (reminder_time, reminder_time_repeat, reminder_text) = self._process_reminder_text(time_and_optional_text.strip())
        except commands.BadArgument as ba:
            await ctx.reply(embed = gen_embed(title='remindme', content=str(ba)))
            return
        if not reminder_time:
            log.warning('Missing Required Argument')
            params = ' '.join([x for x in ctx.command.clean_params])
            await ctx.reply(embed=gen_embed(title="Invalid parameter(s) entered",
                                           content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            return
        if len(reminder_text) > 900:
            log.warning('Exceeded length limit')
            await ctx.reply(embed=gen_embed(title="Exceeded length limit",
                                            content='Your reminder text is too long (must be <900 characters)'))
            return
        repeat = (int(reminder_time_repeat.total_seconds()) if reminder_time_repeat else None)
        future_timeunix = int(time.time() + reminder_time.total_seconds())
        future_timestamp = humanize_timedelta(timedelta=reminder_time)
        query = {'user_id': ctx.author.id}
        nid = await db.reminders.count_documents(query) + 1
        post = {
            'nid': nid,
            'user_id': ctx.author.id,
            'creation_date': time.time(),
            'reminder': reminder_text,
            'repeat': repeat,
            'future_time': future_timeunix,
            'future_timestamp': future_timestamp,
            'jump_link': ctx.message.jump_url,
            'query_id': None
        }
        reminder = await db.reminders.insert_one(post)

        message = f"I will remind you of {'that' if reminder_text else 'this'} "
        if repeat:
            message += f"every {humanize_timedelta(timedelta=reminder_time_repeat)}"
        else:
            message += f"in {future_timestamp}"
        if repeat and reminder_time_repeat != reminder_time:
            message += f", with the first reminder in {future_timestamp}."
        else:
            message += "."
        await ctx.reply(embed=gen_embed(title='Reminder set!',
                                        content=message))

        query: discord.Message = await ctx.send(embed=gen_embed(title='Want to be reminded too?',
                                                                content=f"If anyone else would like {'these reminders' if repeat else 'to be reminded'} as well, click the bell below!"))
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
        ) = self._process_reminder_text_from_ends(reminder_time, reminder_time_repeat, reminder_text, self.timedelta_begin)
        # find the time delta(s) at the end of the text
        (
            reminder_time,
            reminder_time_repeat,
            reminder_text,
        ) = self._process_reminder_text_from_ends(reminder_time, reminder_time_repeat, reminder_text, self.timedelta_end)

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
            reminder_text = (reminder_text[0: regex_result.span()[0]] + reminder_text[regex_result.span()[1] + 1:]).strip()
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
                        minimum=timedelta(days=1),
                        allowed_units=["weeks", "days"],
                    )
                except commands.BadArgument as ba:
                    orig_message = str(ba)[0].lower() + str(ba)[1:]
                    raise BadArgument(
                        f"For the repeating portion of this reminder, {orig_message}. "
                        "You must only use `days` or `weeks` when dealing with repeating reminders."
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
            return m.author == ctx.author

        query = {'user_id': ctx.author.id}
        num_reminders = await db.reminders.count_documents(query)
        if num_reminders <= 0:
            await ctx.reply(embed=gen_embed(title='No Reminders Found',
                                            content="You don't have any upcoming reminders."))
            return
        if index == 'all':
            await ctx.reply('Are you **sure** you want to remove all your reminders? (yes/no)')
            resp = None
            try:
                resp = await self.bot.wait_for('message', check=check, timeout=30)
            except asyncio.TimeoutError:
                pass
            if resp.content == 'yes':
                pass
            else:
                await ctx.reply(embed=gen_embed(title='Deletion cancelled',
                                                content='I have left your reminders alone.'))
                return
            await db.reminders.delete_many(query)
            await ctx.reply(embed=gen_embed(title='Reminders deleted',
                                            content='All of your reminders have been deleted.'))
            return
        if index == 'last':
            reminder_to_delete = db.reminders.find_one(query, {'sort': {'$natural': -1}})
            rid = reminder_to_delete['nid']
            await db.reminders.delete_one(query, {'sort': { '$natural' :-1 }})
            await ctx.reply(embed=gen_embed(title='Latest reminder deleted',
                                            content=f"Your most recently created reminder (ID: {rid}) has been deleted."))
            return
        else:
            try:
                index = int(index)
            except ValueError:
                raise discord.ext.commands.BadArgument(
                    "`{unit}` is not a valid ID for this command".format(unit=k)
                )
            uquery = {'user_id': ctx.author.id, 'nid': index}
            reminder_to_delete = await db.reminders.find_one(uquery)
            if reminder_to_delete:
                rid = reminder_to_delete['nid']
                await db.reminders.delete_one(uquery)
                await ctx.reply(embed=gen_embed(title='Reminder deleted',
                                                content=f"Reminder (ID: {rid}) has been deleted."))
            else:
                log.error(f'Reminder {index} could not be found')
                await ctx.reply(embed=gen_embed(title='Reminder could not be found',
                                                content=f"The reminder could not be found. Check the id?"))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        async def reminder_exists(new_reminder):
            async for document in db.reminders.find():
                if (
                        document['user_id'] == new_reminder['user_id']
                        and document['reminder'] == new_reminder['reminder']
                        and document['future_time'] == new_reminder['future_time']
                        and document['future_timestamp'] == new_reminder['future_timestamp']
                ):
                    return True
            return False

        if not payload.guild_id:
            return
        if str(payload.emoji) != "\N{BELL}":
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if member.bot:
            return

        found_reminder = await db.reminders.find_one({'query_id': payload.message_id})
        if found_reminder:
            reminder_text = found_reminder['reminder']
            repeat = found_reminder['repeat']
            future_time = found_reminder['future_time']
            future_timestamp = found_reminder['future_timestamp']
            jump_link = found_reminder['jump_link']
            query = {'user_id': member.id}
            nid = await db.reminders.count_documents(query) + 1
            post = {
                'nid': nid,
                'user_id': member.id,
                'creation_date': time.time(),
                'reminder': reminder_text,
                'repeat': repeat,
                'future_time': future_time,
                'future_timestamp': future_timestamp,
                'jump_link': jump_link,
                'query_id': None
            }
            if await reminder_exists(post):
                return
            await db.reminders.insert_one(post)
            message = 'Hello! I will also send you'
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