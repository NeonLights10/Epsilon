import json
import asyncio
import os
import sys
import logging

import re
import random

import twitter

import psutil
import time

import discord
import colorlog
import motor.motor_asyncio
import datetime

from discord.ext import commands
from discord.utils import find, get
from pymongo import MongoClient

from formatting.constants import VERSION as BOTVERSION
from formatting.constants import NAME
from formatting.constants import FILTER

# read config information
with open("config.json") as file:
    config_json = json.load(file)
    TOKEN = config_json["token"]
    DBPASSWORD = config_json['db_password']
    TWTTOKEN = config_json['twitter_token']
    TWTSECRET = config_json['twitter_secret']
    CONSUMER_KEY = config_json['consumer_key']
    CONSUMER_SECRET = config_json['consumer_secret']

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

dlog = logging.getLogger('discord')
dlog.setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.members = True
intents.messages = True

default_prefix = "%"
databaseName = config_json["database_name"]


####################

# set up fancy format logging
def _setup_logging():
    shandler = logging.StreamHandler()
    shandler.setLevel(config_json["log_level"])
    shandler.setFormatter(colorlog.LevelFormatter(
        fmt={
            'DEBUG': '{log_color}[{levelname}:{module}] {message}',
            'INFO': '{log_color}{asctime} | {message}',
            'WARNING': '{log_color}{levelname}: {message}',
            'ERROR': '{log_color}[{levelname}:{module}] {message}',
            'CRITICAL': '{log_color}[{levelname}:{module}] {message}',

            'EVERYTHING': '{log_color}[{levelname}:{module}] {message}',
            'NOISY': '{log_color}[{levelname}:{module}] {message}',
            'VOICEDEBUG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}',
            'FFMPEG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}'
        },
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'white',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',

            'EVERYTHING': 'white',
            'NOISY': 'white',
            'FFMPEG': 'bold_purple',
            'VOICEDEBUG': 'purple',
        },
        style='{',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    log.addHandler(shandler)
    dlog.addHandler(shandler)


_setup_logging()

log.info(f"Set logging level to {config_json['log_level']}")

if config_json["debug_mode"]:
    debuglog = logging.getLogger('discord')
    debuglog.setLevel(logging.DEBUG)
    dhandler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
    dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
    debuglog.addHandler(dhandler)

if os.path.isfile(f"logs/{NAME}.log"):
    log.info("Moving old bot log")
    try:
        if os.path.isfile(f"logs/{NAME}.log.last"):
            os.unlink(f"logs/{NAME}.log.last")
        os.rename(f"logs/{NAME}.log", f"logs/{NAME}.log.last")
    except:
        pass

with open(f"logs/{NAME}.log", 'w', encoding='utf8') as f:
    f.write('\n')
    f.write(" PRE-RUN CHECK PASSED ".center(80, '#'))
    f.write('\n\n')

fhandler = logging.FileHandler(f"logs/{NAME}.log", mode='a')
fhandler.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
))
fhandler.setLevel(logging.DEBUG)
log.addHandler(fhandler)

####################

# db init and first time setup
log.info('\n')
log.info(f'Establishing connection to MongoDB database {databaseName}')

mclient = motor.motor_asyncio.AsyncIOMotorClient(
    f"mongodb+srv://admin:{DBPASSWORD}@delphinium.jnxfw.mongodb.net/{databaseName}?retryWrites=true&w=majority")
db = mclient[databaseName]

log.info(f'Database loaded.\n')

t = twitter.Twitter(
    auth=twitter.OAuth(TWTTOKEN, TWTSECRET, CONSUMER_KEY, CONSUMER_SECRET)
)

log.info('Twitter API Initialized.\n')


async def _initialize_document(guild, id):
    post = {'server_id': id,
            'name': guild.name,
            'modrole': None,
            'autorole': None,
            'log_channel': None,
            'log_joinleaves': False,
            'log_kbm': False,
            'log_strikes': False,
            'welcome_channel': None,
            'welcome_message': f"Welcome to {guild.name}!",
            'welcome_banner': None,
            'max_strike': 3,
            'modmail_channel': None,
            'announcement_channel': None,
            'fun': True,
            'chat': False,
            'delete_twitterfix': False,
            'prefix': None,
            'blacklist': [],
            'whitelist': [],
            'verify': [],
            'announcements': True
            }
    log.info(f"Creating document for {guild.name}...")
    await db.servers.insert_one(post)


async def _check_document(guild, id):
    log.info("Checking db document for {}".format(guild.name))
    if await db.servers.find_one({"server_id": id}) is None:
        log.info("Did not find one, creating document...")
        await _initialize_document(guild, id)
    else:
        document = await db.servers.find_one({"server_id": id})
        blacklist = document['blacklist']
        for channel_id in blacklist:
            await db.msgid.delete_many({"channel_id": channel_id})
        # Update this list as new fields are inserted
        await db.servers.update_many(
            {"server_id": id},
            [{'$set': {
                "name": guild.name,
                "welcome_message": f'Welcome to {guild.name}!'
                #obsolete updates
                #"log_joinleaves": {'$cond': [{'$not': ["$log_joinleaves"]}, False, "$log_joinleaves"]},
                #"blacklist": {'$cond': [{'$not': ["$blacklist"]}, [], "$blacklist"]},
                #"whitelist": {'$cond': [{'$not': ["$whitelist"]}, [], "$whitelist"]},
                #"log_kbm": {'$cond': [{'$not': ["$log_kbm"]}, False, "$log_kbm"]},
                #"log_strikes": {'$cond': [{'$not': ["$log_strikes"]}, False, "$log_strikes"]},
                #"chat": {'$cond': [{'$not': ["$chat"]}, False, "$chat"]},
                #"announcement_channel": {'$cond': [{'$not': ["$announcement_channel"]}, None, "$announcement_channel"]},
                #"verify": {'$cond': [{'$not': ["$verify"]}, [], "$verify"]},
                #"announcements": {'$cond': [{'$not': ["$announcements"]}, True, "$announcements"]}```
            }}]
        )


####################

def gen_embed(name=None, icon_url=None, title=None, content=None):
    """Provides a basic template for embeds"""
    e = discord.Embed(colour=0x1abc9c)
    if name and icon_url:
        e.set_author(name=name, icon_url=icon_url)
    e.set_footer(text="Fueee~")
    e.title = title
    e.description = content
    return e

async def _emoji_log(message):
    custom_emojis_raw = re.findall(r'<a?:\w*:\d*>', message.content)
    custom_emojis_formatted = [int(e.split(':')[2].replace('>', '')) for e in custom_emojis_raw]
    custom_emojis = []
    for e in custom_emojis_formatted:
        entry = discord.utils.get(message.guild.emojis, id=e)
        if entry is not None:
            custom_emojis.append(entry)
    if len(custom_emojis) > 0:
        for emoji in custom_emojis:
            if await db.emoji.find_one({"id": emoji.id}) is None:
                post = {'id': emoji.id,
                        'name': emoji.name,
                        'guild': emoji.guild_id,
                        'count': 0
                }
                await db.emoji.insert_one(post)
            document = await db.emoji.find_one({"id": emoji.id})
            count = document['count'] + 1
            await db.emoji.update_one({"id": emoji.id}, {"$set": {'count': count}})

async def twtfix(message):
    message_link = message.clean_content
    author = message.author
    channel = message.channel
    modified = False

    twitter_links = re.findall(r'https://twitter\.com\S+', message_link)
    if twitter_links:
        document = await db.servers.find_one({"server_id": message.guild.id})
        for twt_link in twitter_links:
            log.info(f"[{message.guild.id}] Attempting to download tweet info from Twitter API")
            twid = int(re.sub(r'\?.*$', '', twt_link.rsplit("/", 1)[-1]))  # gets the tweet ID as a int from the passed url
            tweet = t.statuses.show(_id=twid, tweet_mode="extended")

            # Check to see if tweet has a video, if not, make the url passed to the VNF the first t.co link in the tweet
            if 'extended_entities' in tweet:
                if 'video_info' in tweet['extended_entities']['media'][0]:
                    log.info("Modifying twitter link to fxtwitter")
                    if document['delete_twitterfix']:
                        message_link = re.sub(fr'https://twitter\.com/([^/]+/status/{str(twid)}\?\S*)', fr'https://fxtwitter.com/\1', message_link)
                        modified = True
                    else:
                        new_message_content = re.sub(r'https://twitter', 'https://fxtwitter', twt_link)
                        try:
                            await channel.send(content=new_message_content)
                            log.info("Sent fxtwitter link")
                        except:
                            return None
        if document['delete_twitterfix'] and modified:
            try:
                await message.delete()
                log.info("Deleted message, sending fxtwitter link")
                return await channel.send(
                    content=f"**{author.display_name}** ({author.name}#{author.discriminator}) sent:\n{message_link}")
            except:
                return None
    return None



# This is a super jenk way of handling the prefix without using the async db connection but it works
prefix_list = {}


def prefix(bot, message):
    results = None
    try:
        results = prefix_list.get(message.guild.id)
    except:
        pass

    if results:
        prefix = results
    else:
        prefix = default_prefix
    return prefix


####################

log.info(f'Starting {NAME} {BOTVERSION}')

bot = commands.Bot(command_prefix=prefix, intents=intents, case_insensitive=True)

try:
    sys.stdout.write(f"\x1b]2;{NAME} {BOTVERSION}\x07")
except:
    pass

uptime = time.time()
message_count = 0
command_count = 0


####################

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await _check_document(guild, guild.id)

    async for document in db.servers.find({}):
        server_id = document['server_id']
        if document['prefix'] is not None:
            prefix_list[server_id] = document['prefix']

    log.info("\n### PRE-STARTUP CHECKS PASSED ###\n")

    ####################

    status = discord.Game(f'{default_prefix}help | {len(bot.guilds)} servers')
    await bot.change_presence(activity=status)

    log.info(f"Connected: {bot.user.id}/{bot.user.name}#{bot.user.discriminator}")
    owner = await bot.application_info()
    owner = owner.owner
    log.info(f"Owner: {owner.id}/{owner.name}#{owner.discriminator}\n")

    log.info("Guild List:")
    for s in bot.guilds:
        ser = (f'{s.name} (unavailable)' if s.unavailable else s.name)
        log.info(f" - {ser}")
    print(flush=True)

# TODO - refactor and move modmail logic and fun logic out to separate helper methods
@bot.event
async def on_message(message):
    global message_count
    global command_count
    message_count += 1
    ctx = await bot.get_context(message)

    if isinstance(ctx.channel, discord.TextChannel):
        document = await db.servers.find_one({"server_id": ctx.guild.id})

        if ctx.guild.id == 432379300684103699:
            await _emoji_log(message)

        whitelist = document['whitelist']
        if ctx.author.bot is False:
            if ctx.prefix:
                if whitelist and ctx.channel.id not in whitelist:
                    return
                log.info(
                    f"{ctx.message.author.id}/{ctx.message.author.name}{ctx.message.author.discriminator}: {ctx.message.content}")
                await bot.invoke(ctx)
                command_count += 1
            elif ctx.message.reference:
                ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
                if ref_message.author == bot.user:
                    # modmail logic
                    if ctx.channel.id == document['modmail_channel']:
                        valid_options = {'New Modmail', 'Attachment'}
                        if ref_message.embeds[0].title in valid_options:
                            ref_embed = ref_message.embeds[0].footer
                            user_id = ref_embed.text
                            try:
                                user = await bot.fetch_user(user_id)
                            except:
                                embed = gen_embed(title='Error',
                                                  content=f'Error finding user. This could be a server-side error, or you replied to the wrong message.')
                                await ctx.channel.send(embed=embed)
                                return
                            if document['modmail_channel']:
                                embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url,
                                                  title="New Modmail",
                                                  content=f'{message.clean_content}\n\nYou may reply to this modmail using the reply function.')
                                embed.set_footer(text=f"{ctx.guild.id}")
                                dm_channel = user.dm_channel
                                if user.dm_channel is None:
                                    dm_channel = await user.create_dm()
                                await dm_channel.send(embed=embed)
                                if len(ctx.message.attachments) > 0:
                                    attachnum = 1
                                    for attachment in ctx.message.attachments:
                                        embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url,
                                                          title='Attachment', content=f'Attachment #{attachnum}:')
                                        embed.set_image(url=attachment.url)
                                        embed.set_footer(text=f'{ctx.guild.id}')
                                        await dm_channel.send(embed=embed)
                                        attachnum += 1
                                await ctx.send(embed=gen_embed(title='Modmail sent',
                                                               content=f'Sent modmail to {user.name}#{user.discriminator}.'))
                    elif document['chat']:
                        if whitelist and ctx.channel not in whitelist:
                            return
                        log.info("Found a reply to me, generating response...")
                        msg = await get_msgid(ctx.message)
                        #log.info(f"Message retrieved: {msg}\n")
                        await ctx.message.reply(content=msg)

                else:
                    if ctx.channel.id not in document['blacklist']:
                        post = {'server_id': ctx.guild.id,
                                'channel_id': ctx.channel.id,
                                'msg_id': ctx.message.id}
                        await db.msgid.insert_one(post)
                        #await twtfix(message)
            elif bot.user.id in ctx.message.raw_mentions and ctx.author != bot.user:
                if document['chat']:
                    #new_message = await twtfix(message)
                    if whitelist and ctx.channel not in whitelist:
                        return
                    log.info("Found a reply to me, generating response...")
                    msg = await get_msgid(ctx.message)
                    #log.info(f"Message retrieved: {msg}\n")
                    await ctx.message.reply(content=msg)
            else:
                if ctx.channel.id not in document['blacklist']:
                    post = {'server_id': ctx.guild.id,
                            'channel_id': ctx.channel.id,
                            'msg_id': ctx.message.id}
                    await db.msgid.insert_one(post)
                    #await twtfix(message)


    elif isinstance(ctx.channel, discord.DMChannel):
        if ctx.author.bot is False:
            if ctx.message.reference:
                ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
                valid_options = {'You have been given a strike', 'New Modmail', 'You have been banned',
                                 'You have been kicked', 'Attachment'}
                if ref_message.embeds[0].title in valid_options or re.match('You have been muted',
                                                                            ref_message.embeds[0].title):
                    ref_embed = ref_message.embeds[0].footer
                    guild_id = ref_embed.text
                    try:
                        document = await db.servers.find_one({"server_id": int(guild_id)})
                    except ValueError:
                        embed = gen_embed(title='Error',
                                          content=f'Cannot find a valid server ID in the footer. Are you sure you replied to the right message?')
                        await ctx.channel.send(embed=embed)
                        return
                    if document['modmail_channel']:
                        guild = discord.utils.find(lambda g: g.id == int(guild_id), bot.guilds)
                        embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                                          icon_url=ctx.author.display_avatar.url, title="New Modmail",
                                          content=f'{message.clean_content}\n\nYou may reply to this modmail using the reply function.')
                        embed.set_footer(text=f"{ctx.author.id}")
                        channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], guild.channels)
                        await channel.send(embed=embed)
                        if len(ctx.message.attachments) > 0:
                            attachnum = 1
                            for attachment in ctx.message.attachments:
                                embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                                                  icon_url=ctx.author.display_avatar.url, title='Attachment',
                                                  content=f'Attachment #{attachnum}:')
                                embed.set_image(url=attachment.url)
                                embed.set_footer(text=f'{ctx.author.id}')
                                await channel.send(embed=embed)
                                attachnum += 1
                        await channel.send(content=f"{ctx.author.mention}")
                        await ctx.send(embed=gen_embed(title='Modmail sent',
                                                       content='The moderators will review your message and get back to you shortly.'), )
                        return
            elif ctx.prefix:
                if ctx.command.name == 'modmail':
                    await bot.invoke(ctx)
            else:
                await ctx.send(embed=gen_embed(title='Sorry...',
                                               content="Kanon does not accept regular messages in DM.\nAre you trying to send a modmail? Please make sure to use discord's reply function on any message from Kanon with the server id in the footer (see image below) OR send a command by doing %modmail <server id> <message content>."))
                await ctx.send(content="https://files.s-neon.xyz/share/DiscordPTB_OeITM0GLtA.png")

@bot.event
async def on_guild_join(guild):
    await _check_document(guild, guild.id)

    status = discord.Game(f'{default_prefix}help | {len(bot.guilds)} servers')
    await bot.change_presence(activity=status)

    general = find(lambda x: x.name == 'general', guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        embed = gen_embed(name=f'{guild.name}',
                          icon_url=guild.icon.url,
                          title='Thanks for inviting me!',
                          content='You can get started by typing %help to find the current command list.\nChange the command prefix by typing %setprefix, and configure server settings with %serverconfig and %channelconfig.\n\nSource code: https://github.com/neon10lights/Epsilon\nSupport: https://www.patreon.com/kanonbot or https://ko-fi.com/neonlights\nIf you have feedback or need help, please DM Neon#5555 or join the server at https://discord.gg/AYTFJY8VhF')
        await general.send(embed=embed)
        await general.send(embed=gen_embed(title='Thank you Kanon Supporters!', content= '**Thanks to:**\nReileky#4161, SinisterSmiley#0704, Makoto#7777, Vince.#6969'))
        return
    else:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = gen_embed(name=f'{guild.name}',
                                  icon_url=guild.icon.url,
                                  title='Thanks for inviting me!',
                                  content='You can get started by typing %help to find the current command list.\nChange the command prefix by typing %setprefix, and configure server settings with %serverconfig and %channelconfig.\n\nSource code: https://github.com/neon10lights/Epsilon\nSupport: https://www.patreon.com/kanonbot or https://ko-fi.com/neonlights\nIf you have feedback or need help, please DM Neon#5555 or join the server at https://discord.gg/AYTFJY8VhF.')
                await channel.send(embed=embed)
                await channel.send(embed=gen_embed(title='Thank you Kanon Supporters!', content= '**Thanks to:**\nReileky#4161, SinisterSmiley#0704, Makoto#7777, Vince.#6969'))
                return


@bot.event
async def on_member_join(member):
    log.info(f"A new member joined in {member.guild.name}")
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['autorole']:
        role = discord.utils.find(lambda r: r.id == int(document['autorole']), member.guild.roles)
        if role:
            await member.add_roles(role)
            log.info("Auto-assigned role to new member in {}".format(member.guild.name))
        else:
            log.error("Auto-assign role does not exist!")
    if document['welcome_message'] and document['welcome_channel']:
        welcome_channel = find(lambda c: c.id == int(document['welcome_channel']), member.guild.text_channels)
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title=f"Welcome to {member.guild.name}",
                          content=document['welcome_message'])
        if document['welcome_banner']:
            embed.set_image(url=document['welcome_banner'])
        await welcome_channel.send(embed=embed)
    if document['log_joinleaves'] and document['log_channel']:
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title="Member joined",
                          content=f"Member #{member.guild.member_count}")
        msglog = int(document['log_channel'])
        logChannel = member.guild.get_channel(msglog)
        await logChannel.send(embed=embed)


@bot.event
async def on_member_remove(member):
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['log_joinleaves'] and document['log_channel']:
        jointime = member.joined_at
        nowtime = datetime.datetime.now(datetime.timezone.utc)
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title="Member left",
                          content=f"Joined {member.joined_at} ({nowtime - jointime} ago)")
        msglog = int(document['log_channel'])
        logchannel = member.guild.get_channel(msglog)
        await logchannel.send(embed=embed)


###################

# This recursive function checks the database for a message ID for the bot to fetch a message and respond with when mentioned or replied to.
async def get_msgid(message, attempts=1):
    # Construct the aggregation pipeline, match for the current server id and exclude bot messages if they somehow snuck past the initial regex.
    pipeline = [
        {'$match': {'$and': [{'server_id': message.guild.id}, {'author_id': {'$not': {'$regex': str(bot.user.id)}}}]}},
        {'$sample': {'size': 1}}]
    async for msgid in db.msgid.aggregate(pipeline):
        # This is jenky and I believe can be fixed to use ctx instead, but it searches each channel until it finds the channel the message was sent in.
        # This lets us fetch the message.
        for channel in message.guild.channels:
            if channel.id == msgid['channel_id']:
                try:
                    #We fetch the message, as we do not store any message contents for user privacy. If the message is deleted, we can't access it.
                    msg = await channel.fetch_message(msgid['msg_id'])

                    # Now let's double check that we aren't mentioning ourself or another bot, and that the messages has no embeds or attachments.
                    filter = f"(?:{'|'.join(FILTER)})"
                    if (re.match('^%|^\^|^\$|^!|^\.|@|k!', msg.content) is None) and (
                            re.match(f'<@!?{bot.user.id}>', msg.content) is None) and (len(msg.embeds) == 0) and (
                            msg.author.bot is False) and (re.match(filter, msg.content) is None):
                                log.info("Attempts taken:{}".format(attempts))
                                log.info("Message ID:{}".format(msg.id))
                                return msg.clean_content
                    else:
                        # If we fail, remove that message ID from the DB so we never call it again.
                        attempts += 1
                        mid = msgid['msg_id']
                        await db.msgid.delete_one({"msg_id": mid})
                        log.info("Removing entry from db...")
                        return await get_msgid(message, attempts)

                except discord.Forbidden:
                    raise discord.exceptions.CommandError("I don't have permissions to read message history.")

                except discord.NotFound:
                    # This happens sometimes due to deleted message or other weird shenanigans, so do the same as above.
                    attempts += 1
                    mid = msgid['msg_id']
                    await db.msgid.delete_one({"msg_id": mid})
                    log.info("Removing entry from db...")
                    return await get_msgid(message, attempts)


####################

bot.remove_command('help')
bot.load_extension("commands.help")
bot.load_extension("commands.utility")
bot.load_extension("commands.errorhandler")
bot.load_extension("commands.fun")
bot.load_extension("commands.misc")
bot.load_extension("commands.administration")
bot.load_extension("commands.modmail")
bot.load_extension("commands.tiering")
bot.load_extension("commands.reminder")
bot.run(TOKEN)
