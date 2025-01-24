import os
import sys

import asyncio
import re
import json
import time
import gc

import logging
import colorlog

import twitter

import discord
from discord.ext import bridge

import motor.motor_asyncio

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
intents.message_content = True

databaseName = config_json["database_name"]

default_prefix = "%"
prefix_list = {}


####################


# set up fancy format logging
def _setup_logging():
    shandler = logging.StreamHandler()
    shandler.setLevel(config_json["log_level"])
    # noinspection PyTypeChecker
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
    debuglog.setLevel(logging.INFO)
    dhandler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
    dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
    debuglog.addHandler(dhandler)

if os.path.isfile(f"logs/{NAME}.log"):
    log.info("Moving old bot log")
    try:
        if os.path.isfile(f"logs/{NAME}.log.last"):
            os.unlink(f"logs/{NAME}.log.last")
        os.rename(f"logs/{NAME}.log", f"logs/{NAME}.log.last")
    except Exception as e:
        pass

with open(f"logs/{NAME}.log", 'w', encoding='utf8') as f:
    f.write('\n')
    f.write(" PRE-RUN CHECK PASSED ".center(80, '#'))
    f.write('\n\n')

fhandler = logging.FileHandler(f"logs/{NAME}.log", mode='a')
fhandler.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
))
fhandler.setLevel(logging.ERROR)
log.addHandler(fhandler)

####################


sys.stdout.write(f"\x1b]2;{NAME} {BOTVERSION}\x07")

# db init and first time setup
log.info('\n')
log.info(f'Establishing connection to MongoDB database {databaseName}')

# f"mongodb+srv://admin:{DBPASSWORD}@delphinium.jnxfw.mongodb.net/{databaseName}?retryWrites=true&w=majority"
mclient = motor.motor_asyncio.AsyncIOMotorClient(
    f"mongodb://admin:{DBPASSWORD}@104.131.182.231/{databaseName}?retryWrites=true&authSource=admin")
mclient.get_io_loop = asyncio.get_running_loop

db = mclient[databaseName]
log.info(f'Database loaded.\n')

# twitter API load
t = twitter.Twitter(
    auth=twitter.OAuth(TWTTOKEN, TWTSECRET, CONSUMER_KEY, CONSUMER_SECRET)
)
log.info('Twitter API Initialized.\n')


##########


async def initialize_document(guild, id):
    post = {'server_id': id,
            'name': guild.name,
            'modrole': None,
            'autorole': None,
            'log_channel': None,
            'log_messages': [False, None],
            'log_joinleaves': [False, None],
            'log_kbm': [False, None],
            'log_strikes': [False, None],
            'max_strike': 3,
            'modmail_channel': None,
            'modmail_button_channel': None,
            'prev_message_modmail': None,
            'announcement_channel': None,
            'fun': True,
            'chat': False,
            'delete_twitterfix': False,
            'prefix': None,
            'blacklist': None,
            'whitelist': None,
            'verify': [],
            'announcements': True
            }
    log.info(f"Creating document for {guild.name}...")
    await db.servers.insert_one(post)


async def check_document(guild, id):
    log.info("Checking db document for {}".format(guild.name))
    if await db.servers.find_one({"server_id": id}) is None:
        log.info("Did not find one, creating document...")
        await initialize_document(guild, id)
    else:
        pass
        # Changeable to update old documents whenever a new feature/config is added
        #document = await db.servers.find_one({"server_id": id})
        #try:
        #    if document['log_messages']:
        #        pass
        #except KeyError:
        #    post = {'log_messages': [False, None]}
        #    await db.servers.update_one({"server_id": id},
        #                                {"$set": post})

        #try:
        #    if document['log_channel']:
        #        post = {'log_messages': [document['log_messages'], document['log_channel']],
        #                'log_joinleaves': [document['log_joinleaves'], document['log_channel']],
        #                'log_kbm': [document['log_kbm'], document['log_channel']],
        #                'log_strikes': [document['log_strikes'], document['log_channel']]}
        #        await db.servers.update_one({"server_id": id},
        #                                    {"$set": post})
        #    else:
        #        post = {'log_messages': [document['log_messages'], None],
        #                'log_joinleaves': [document['log_joinleaves'], None],
        #                'log_kbm': [document['log_kbm'], None],
        #                'log_strikes': [document['log_strikes'], None]}
        #        await db.servers.update_one({"server_id": id},
        #                                    {"$set": post})
        #except KeyError:
        #    post = {'log_channel': None,
        #            'log_messages': [False, None],
        #            'log_joinleaves': [False, None],
        #            'log_kbm': [False, None],
        #            'log_strikes': [False, None]}
        #    await db.servers.update_one({"server_id": id},
        #                                {"$set": post})

##########


async def get_prefix(bot, message):
    if isinstance(message.channel, discord.DMChannel):
        return default_prefix
    server_prefix = (await db.servers.find_one({"server_id": message.guild.id}))['prefix']
    return server_prefix or default_prefix


def gen_embed(name=None, icon_url=None, title=None, content=None):
    """Provides a basic template for embeds"""
    e = discord.Embed(colour=0x1abc9c)
    if name and icon_url:
        e.set_author(name=name, icon_url=icon_url)
    e.set_footer(text="Fueee~")
    e.title = title
    e.description = content
    return e


##########


class EpsilonBot(bridge.AutoShardedBot):

    def __init__(self, command_prefix, intents, case_insensitive, debug_guilds=None):
        super().__init__(max_messages=5000,
                         command_prefix=command_prefix,
                         intents=intents,
                         case_insensitive=case_insensitive,
                         debug_guilds=debug_guilds,
                         shard_count=2,
                         chunk_guilds_at_startup=False)
        self.command_count = 0
        self.message_count = 0
        self.ready = False
        self.uptime = time.time()


bot = EpsilonBot(command_prefix=get_prefix, intents=intents, case_insensitive=True)
# bot = EpsilonBot(command_prefix=get_prefix, intents=intents, case_insensitive=True)
bot.remove_command('help')
bot.load_extension("commands.help")
bot.load_extension("commands.errorhandler")
bot.load_extension("commands.listeners")
bot.load_extension("commands.misc")
bot.load_extension("commands.utility")
bot.load_extension("commands.administration")
bot.load_extension("commands.tiering")
bot.load_extension("commands.modmail")
bot.load_extension("commands.reminder")
bot.load_extension("commands.t100chart")
bot.load_extension("commands.fun")
bot.load_extension("commands.pubcord")
bot.load_extension("commands.old")
bot.load_extension("commands.event")
bot.load_extension("commands.update")
bot.load_extension("commands.game")
bot.load_extension("commands.custom")


@bot.event
async def on_ready():
    for guild in bot.guilds:
        await check_document(guild, guild.id)
    gc.collect()
    bot.ready = True

    log.info("\n### PRE-STARTUP CHECKS PASSED ###\n")

    ####################

    status = discord.Game(f'/help | {len(bot.guilds)} servers')
    await bot.change_presence(activity=status)
    banner_file = open('banner.gif', 'rb')
    banner = banner_file.read()
    avatar_file = open('avatar.gif', 'rb')
    avatar = avatar_file.read()
    await bot.user.edit(avatar=avatar, banner=banner)

    log.info(f"Connected: {bot.user.id}/{bot.user.name}#{bot.user.discriminator}")
    owner = await bot.application_info()
    owner = owner.owner
    log.info(f"Owner: {owner.id}/{owner.name}#{owner.discriminator}\n")

    log.info("Guild List:")
    for s in bot.guilds:
        ser = (f'{s.name} (unavailable)' if s.unavailable else s.name)
        log.info(f" - {ser}")
    print(flush=True)


@bot.event
async def on_message(message):
    bot.message_count += 1
    ctx = await bot.get_context(message)

    if isinstance(ctx.channel, discord.TextChannel) or isinstance(ctx.channel, discord.Thread):

        if ctx.guild.id == 432379300684103699:
            await _emoji_log(message)

        if ctx.author.bot is False:
            if ctx.prefix:
                # bypass check for now for t100 chart hub, keep prefix check first though
                if ctx.guild.id == 616088522100703241 and ctx.message.reference:
                    pass
                else:
                    # whitelist check
                    document = await db.servers.find_one({"server_id": ctx.guild.id})
                    try:
                        whitelist = document['whitelist']
                    except KeyError:
                        whitelist = None
                    if whitelist and ctx.channel.id not in whitelist:
                        return
                    log.info(
                        f"{ctx.message.author.id}/{ctx.message.author.name}{ctx.message.author.discriminator}: {ctx.message.content}")
                    await bot.invoke(ctx)
                    bot.command_count += 1
                    return

            # check if message has a reference & is a reply
            if ctx.message.reference and ctx.message.type != discord.MessageType.pins_add:
                if ctx.message.reference.message_id:
                    ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)

                    if ref_message.author == bot.user:
                        document = await db.servers.find_one({"server_id": ctx.guild.id})
                        if document['modmail_channel'] and ctx.channel.id == document['modmail_channel']:
                            await modmail_response_guild(message, ctx, ref_message)
                            return
                        elif document['chat']:
                            try:
                                whitelist = document['whitelist']
                            except KeyError:
                                whitelist = None
                            if whitelist and ctx.channel not in whitelist:
                                return
                            log.info("Found a reply to me, generating response...")
                            try:
                                blacklist = document['blacklist']
                            except TypeError:
                                blacklist = None
                            log.info("Obtained blacklist")
                            msg = await get_msgid(ctx.message, blacklist=blacklist)
                            await ctx.message.reply(content=msg)
                            return

            if bot.user.id in ctx.message.raw_mentions and ctx.author != bot.user:
                document = await db.servers.find_one({"server_id": ctx.guild.id})
                if document['chat']:
                    try:
                        whitelist = document['whitelist']
                    except TypeError:
                        whitelist = None
                    if whitelist and ctx.channel not in whitelist:
                        return
                    log.info("Found a reply to me, generating response...")
                    try:
                        blacklist = document['blacklist']
                    except TypeError:
                        blacklist = None
                    log.info("Obtained blacklist")
                    msg = await get_msgid(ctx.message, blacklist=blacklist)
                    await ctx.message.reply(content=msg)
                    return

            document = await db.servers.find_one({"server_id": ctx.guild.id})
            try:
                blacklist = document['blacklist']
            except TypeError:
                blacklist = None
            if document['blacklist']:
                if ctx.channel.id not in document['blacklist']:
                    post = {'server_id': ctx.guild.id,
                            'channel_id': ctx.channel.id,
                            'msg_id': ctx.message.id}
                    await db.msgid.insert_one(post)
            else:
                post = {'server_id': ctx.guild.id,
                        'channel_id': ctx.channel.id,
                        'msg_id': ctx.message.id}
                await db.msgid.insert_one(post)
            del document

    elif isinstance(ctx.channel, discord.DMChannel):
        if ctx.author.bot is False:
            if ctx.message.reference:
                ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
                await modmail_response_dm(message, ctx, ref_message)
            elif ctx.prefix:
                if ctx.command.name == 'modmail':
                    await bot.invoke(ctx)


##########


# This recursive function checks the database for a message ID for the bot to fetch a message and respond with when
# mentioned or replied to.
async def get_msgid(message, attempts=1, blacklist=None):
    # Construct the aggregation pipeline, match for the current server id and exclude bot messages if they somehow
    # snuck past the initial regex.
    pipeline = [{'$sample': {'size': 500}},
                {'$match':
                     {'$and': [{'server_id': message.guild.id},
                               {'author_id': {'$not': {'$regex': str(bot.user.id)}}}]}},
                {'$limit': 1}]
    async for msgid in db.msgid.aggregate(pipeline):
        # Searches each channel until it finds the channel the message was sent in.
        # This lets us fetch the message.
        for channel in message.guild.channels:
            if channel.id == msgid['channel_id']:
                try:
                    # We fetch the message, as we do not store any message contents for user privacy. If the message
                    # is deleted, we can't access it.
                    msg = await channel.fetch_message(msgid['msg_id'])
                    document = await db.servers.find_one({"server_id": msg.guild.id})
                    if blacklist:
                        log.info(f"blacklist detected")
                        # log.info(msg.channel.id)
                        if msg.channel.id in blacklist:
                            attempts += 1
                            mid = msgid['msg_id']
                            await db.msgid.delete_one({"msg_id": mid})
                            log.info("Channel blacklisted, removing entry from db...")
                            return await get_msgid(message, attempts, blacklist)
                    # Now let's doublecheck that we aren't mentioning ourselves or another bot, and that the messages
                    # has no embeds or attachments.
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
                    raise discord.ext.commands.CommandError("I don't have permissions to read message history.")

                except discord.NotFound:
                    # This happens sometimes due to deleted message or other weird shenanigans, so do the same as above.
                    attempts += 1
                    mid = msgid['msg_id']
                    await db.msgid.delete_one({"msg_id": mid})
                    log.info("Removing entry from db...")
                    return await get_msgid(message, attempts)
    attempts += 1
    return await get_msgid(message, attempts)


async def modmail_response_guild(message, ctx, ref_message):
    valid_options = {'New Modmail', 'Attachment', 'New Screenshot'}

    if ref_message.embeds[0].title in valid_options:
        # special check for the t100 chart hub
        if ctx.guild.id == 616088522100703241 and not ctx.prefix:
            return
        elif ctx.guild.id == 616088522100703241 and ctx.prefix and ctx.invoked_with != "reply":
            return

        ref_embed = ref_message.embeds[0].footer
        user_id = ref_embed.text
        try:
            user = await bot.fetch_user(user_id)
        except Exception:
            embed = gen_embed(title='Error',
                              content=("Error finding user. This could be a server-side error, or you replied to the "
                                       "wrong message."))
            await ctx.channel.send(embed=embed)
            return

        mclean_content = message.clean_content

        # darn t100 chart hub people
        if ctx.invoked_with == "reply":
            mclean_content = mclean_content.replace("%reply", "", 1)

        embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url,
                          title="New Modmail",
                          content=f'{mclean_content}\n\nYou may reply to this message using the reply function.')
        embed.set_footer(text=f"{ctx.guild.id}")

        dm_channel = user.dm_channel
        if user.dm_channel is None:
            dm_channel = await user.create_dm()

        await dm_channel.send(embed=embed)
        await modmail_attachment(ctx, dm_channel, scenario=1)

        await ctx.send(embed=gen_embed(title='Modmail sent',
                                       content=f'Sent modmail to {user.name}#{user.discriminator}.'))
        return


async def modmail_response_dm(message, ctx, ref_message):
    valid_options = {'You have been given a strike', 'New Modmail', 'You have been banned',
                     'You have been kicked', 'Attachment'}
    if ref_message.embeds[0].title in valid_options \
            or re.match('You have been muted', ref_message.embeds[0].title) \
            or re.match('You have been put in timeout', ref_message.embeds[0].title):
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
            embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                              icon_url=ctx.author.display_avatar.url, title="New Modmail",
                              content=f'{message.clean_content}\n\nYou may reply to this modmail using the reply function.')
            embed.set_footer(text=f"{ctx.author.id}")

            guild = discord.utils.find(lambda g: g.id == int(guild_id), bot.guilds)
            channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], guild.channels)

            await channel.send(embed=embed)
            await modmail_attachment(ctx, channel, scenario=2)
            await channel.send(content=f"{ctx.author.mention}")

            await ctx.send(embed=gen_embed(title='Modmail sent',
                                           content='The moderators will review your message and get back to you shortly.'), )
            return


async def modmail_attachment(ctx, channel, scenario: int = None):
    if len(ctx.message.attachments) > 0:
        attachnum = 1
        valid_media_type = ['image/jpeg', 'image/png', 'image/svg+xml', 'image/avif',
                            'image/heif',
                            'image/bmp', 'image/gif', 'image/vnd.mozilla.apng',
                            'image/tiff']

        for attachment in ctx.message.attachments:
            if attachment.content_type in valid_media_type:
                match scenario:
                    case 1:
                        embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url,
                                          title='Attachment',
                                          content=f'Attachment #{attachnum}:')
                        embed.set_image(url=attachment.url)
                        embed.set_footer(text=f'{ctx.guild.id}')
                    case 2:
                        embed = gen_embed(name=f'{ctx.author.name}', icon_url=ctx.author.display_avatar.url,
                                          title='Attachment',
                                          content=f'Attachment #{attachnum}:')
                        embed.set_image(url=attachment.url)
                        embed.set_footer(text=f'{ctx.author.id}')
                await channel.send(embed=embed)
                attachnum += 1
            else:
                await ctx.send(
                    content=f'Attachment #{attachnum} is not a supported media type.')
                match scenario:
                    case 1:
                        embed = gen_embed(name=f'{ctx.guild.name}',
                                          icon_url=ctx.guild.icon.url,
                                          title='Attachment Failed',
                                          content=f'The user attempted to send an attachement that is not a supported '
                                                  f'media type ({attachment.content_type}).')
                    case 2:
                        embed = gen_embed(name=f'{ctx.author.name}',
                                          icon_url=ctx.author.display_avatar.url,
                                          title='Attachment Failed',
                                          content=f'The user attempted to send an attachement that is not a supported '
                                                  f'media type ({attachment.content_type}).')
                await channel.send(embed=embed)
                attachnum += 1
    if len(ctx.message.stickers) > 0:
        for sticker in ctx.message.stickers:
            match scenario:
                case 1:
                    embed = gen_embed(name=f'{ctx.interaction.guild.name}',
                                      icon_url=ctx.interaction.guild.icon.url,
                                      title='Sticker',
                                      content=f'Attached sticker:')
                    embed.set_image(url=sticker.url)
                    embed.set_footer(text=f'{ctx.interaction.guild_id}')
                case 2:
                    embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                                      icon_url=ctx.author.display_avatar.url,
                                      title='Sticker',
                                      content=f'Attached sticker:')
                    embed.set_image(url=sticker.url)
                    embed.set_footer(text=f'{ctx.author.id}')
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                await ctx.send(embed=gen_embed(title='Warning',
                                               content='This user does not accept DMs. I could not send them the sticker.'))
                return


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
            twid = int(
                re.sub(r'\?.*$', '', twt_link.rsplit("/", 1)[-1]))  # gets the tweet ID as a int from the passed url
            tweet = t.statuses.show(_id=twid, tweet_mode="extended")

            # Check to see if tweet has a video, if not, make the url passed to the VNF the first t.co link in the tweet
            if 'extended_entities' in tweet:
                if 'video_info' in tweet['extended_entities']['media'][0]:
                    log.info("Modifying twitter link to fxtwitter")
                    if document['delete_twitterfix']:
                        message_link = re.sub(fr'https://twitter\.com/([^/]+/status/{str(twid)}\?\S*)',
                                              fr'https://fxtwitter.com/\1', message_link)
                        modified = True
                    else:
                        new_message_content = re.sub(r'https://twitter', 'https://fxtwitter', twt_link)
                        try:
                            await channel.send(content=new_message_content)
                            log.info("Sent fxtwitter link")
                        except Exception:
                            return None
        if document['delete_twitterfix'] and modified:
            try:
                await message.delete()
                log.info("Deleted message, sending fxtwitter link")
                return await channel.send(
                    content=f"**{author.display_name}** ({author.name}#{author.discriminator}) sent:\n{message_link}")
            except Exception:
                return None
    return None


##########


bot.run(TOKEN)
