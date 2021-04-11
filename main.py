import json
import asyncio
import os
import sys
import logging

import re
import random

import psutil
import time

import discord
import colorlog
import motor.motor_asyncio

from discord.ext import commands
from discord.utils import find, get
from pymongo import MongoClient

from formatting.constants import VERSION as BOTVERSION
from formatting.constants import NAME

# read config information
with open("config.json") as file:
    config_json = json.load(file)
    TOKEN = config_json["token"]
    DBPASSWORD = config_json['db_password']


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

dlog = logging.getLogger('discord')
dlog.setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.members = True

default_prefix = "^"
databaseName = config_json["database_name"]

####################

#set up fancy format logging
def _setup_logging():
    shandler = logging.StreamHandler()
    shandler.setLevel(config_json["log_level"])
    shandler.setFormatter(colorlog.LevelFormatter(
        fmt = {
            'DEBUG': '{log_color}[{levelname}:{module}] {message}',
            'INFO': '{log_color}{message}',
            'WARNING': '{log_color}{levelname}: {message}',
            'ERROR': '{log_color}[{levelname}:{module}] {message}',
            'CRITICAL': '{log_color}[{levelname}:{module}] {message}',

            'EVERYTHING': '{log_color}[{levelname}:{module}] {message}',
            'NOISY': '{log_color}[{levelname}:{module}] {message}',
            'VOICEDEBUG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}',
            'FFMPEG': '{log_color}[{levelname}:{module}][{relativeCreated:.9f}] {message}'
        },
        log_colors = {
            'DEBUG':    'cyan',
            'INFO':     'white',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',

            'EVERYTHING': 'white',
            'NOISY':      'white',
            'FFMPEG':     'bold_purple',
            'VOICEDEBUG': 'purple',
    },
        style = '{',
        datefmt = ''
    ))
    log.addHandler(shandler)
    dlog.addHandler(shandler)

_setup_logging()

log.info(f"Set logging level to {config_json['log_level']}")

if config_json["debug_mode"] == True:
    debuglog = logging.getLogger('discord')
    debuglog.setLevel(logging.DEBUG)
    dhandler = logging.FileHandler(filename = 'logs/discord.log', encoding = 'utf-8', mode = 'w')
    dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style = '{'))
    debuglog.addHandler(dhandler)

if os.path.isfile(f"logs/{NAME}.log"):
    log.info("Moving old bot log")
    try:
        if os.path.isfile(f"logs/{NAME}.log.last"):
            os.unlink(f"logs/{NAME}.log.last")
        os.rename(f"logs/{NAME}.log", f"logs/{NAME}.log.last")
    except:
        pass

with open(f"logs/{NAME}.log", 'w', encoding = 'utf8') as f:
    f.write('\n')
    f.write(" PRE-RUN CHECK PASSED ".center(80, '#'))
    f.write('\n\n')

fhandler = logging.FileHandler(f"logs/{NAME}.log", mode = 'a')
fhandler.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
))
fhandler.setLevel(logging.DEBUG)
log.addHandler(fhandler)

####################

#db init and first time setup
log.info(f'\nEstablishing connection to MongoDB database {databaseName}')

mclient = motor.motor_asyncio.AsyncIOMotorClient(f"mongodb+srv://admin:{DBPASSWORD}@delphinium.jnxfw.mongodb.net/{databaseName}?retryWrites=true&w=majority")
db = mclient[databaseName]

log.info(f'Database loaded.\n')

async def _initialize_document(guild, id):
    post = {'server_id': id,
            'name': guild.name,
            'modrole': None,
            'autorole': None,
            'log_channel': None,
            'welcome_channel': None,
            'welcome_message': f"Welcome to the {guild.name}!",
            'welcome_banner': None,
            'max_strike': 3,
            'modmail_channel': None,
            'fun': False,
            'prefix': None,
            }
    log.info(f"Creating document for {guild.name}...")
    await db.servers.insert_one(post)


async def _check_document(guild, id):
    log.info("Checking db document for {}".format(guild.name))
    if await db.servers.find_one({"server_id": id}) == None:
        log.info("Did not find one, creating document...")
        await _initialize_document(guild, id)

####################

def gen_embed(name = None, icon_url = None, title = None, content = None):
    """Provides a basic template for embeds"""
    e = discord.Embed(colour = 0x1abc9c)
    if name and icon_url:
        e.set_author(name = name, icon_url = icon_url)
    e.set_footer(text = "Fueee~")
    e.title = title
    e.description = content
    return e 

#This is a super jenk way of handling the prefix without using the async db connection but it works
prefix_list = {}

def prefix(bot, message): 
    results =  None
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

bot = commands.Bot(command_prefix = prefix, intents = intents, case_insensitive = True)

try:
    sys.stdout.write(f"\x1b]2;{NAME} {BOTVERSION}\x07")
except:
    pass

uptime = time.time()
message_count = 0

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
    await bot.change_presence(activity = status)

    log.info(f"Connected: {bot.user.id}/{bot.user.name}#{bot.user.discriminator}")
    owner = await bot.application_info()
    owner = owner.owner
    log.info(f"Owner: {owner.id}/{owner.name}#{owner.discriminator}\n")

    log.info("Guild List:")
    for s in bot.guilds:
        ser = (f'{s.name} (unavailable)' if s.unavailable else s.name)
        log.info(f" - {ser}")    
    print(flush = True)

@bot.event
async def on_message(message):
    global message_count
    message_count += 1
    ctx = await bot.get_context(message)

    if isinstance(ctx.channel, discord.TextChannel):
        document = await db.servers.find_one({"server_id": ctx.guild.id})

        if ctx.author.bot is False:
            if ctx.prefix:
                log.info(f"{ctx.message.author.id}/{ctx.message.author.name}{ctx.message.author.discriminator}: {ctx.message.content}")
            else:
                if document['fun']:
                    post = {'server_id': ctx.guild.id,
                            'channel_id': ctx.channel.id,
                            'msg_id': ctx.message.id}
                    await db.msgid.insert_one(post)

            if ctx.message.reference and document['fun']:
                ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
                if ref_message.author == bot.user:
                    
                    #modmail logic
                    if ctx.channel.id == document['modmail_channel']:
                        if ref_message.embeds[0].title == 'New Modmail':
                            ref_embed = ref_message.embeds[0].footer
                            user_id = ref_embed.text
                            user = await bot.fetch_user(user_id)
                            if document['modmail_channel']:
                                embed = gen_embed(name = f'{ctx.author.name}#{ctx.author.discriminator}', icon_url = ctx.author.avatar_url, title = "New Modmail", content = message.clean_content)
                                embed.set_footer(text = f"{ctx.guild.id}")
                                dm_channel = user.dm_channel
                                if user.dm_channel is None:
                                    dm_channel = await user.create_dm()
                                await dm_channel.send(embed = embed)
                                await ctx.send(embed = gen_embed(title = 'Modmail sent', content = f'Sent modmail to {user.name}#{user.discriminator}.'))
                    else:
                        log.info("Found a reply to me, generating response...")
                        msg = await get_msgid(ctx.message)
                        log.info(f"Message retrieved: {msg}\n")
                        await ctx.message.reply(content = msg)

            elif bot.user.id in ctx.message.raw_mentions and ctx.author != bot.user:
                log.info("Found a mention of myself, generating response...")
                msg = await get_msgid(ctx.message)
                log.info(f"Message retrieved: {msg}\n")
                await ctx.message.reply(content = msg)

            await bot.invoke(ctx)

    elif isinstance(ctx.channel, discord.DMChannel):
        if ctx.author.bot is False:
            if ctx.message.reference:
                ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
                if ref_message.embeds[0].title == 'You have been given a strike' or 'New Modmail':
                    ref_embed = ref_message.embeds[0].footer
                    guild_id = ref_embed.text
                    document = await db.servers.find_one({"server_id": int(guild_id)})
                    if document['modmail_channel']:
                        guild = discord.utils.find(lambda g: g.id == int(guild_id), bot.guilds)
                        embed = gen_embed(name = f'{ctx.author.name}#{ctx.author.discriminator}', icon_url = ctx.author.avatar_url, title = "New Modmail", content = f'{message.clean_content}\n\nYou may reply to this modmail using the reply function.')
                        embed.set_footer(text = f"{ctx.author.id}")
                        channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], guild.channels)
                        await channel.send(embed = embed)
                        await ctx.send(embed = gen_embed(title = 'Modmail sent', content = 'The moderators will review your message and get back to you shortly.'))
                        return



@bot.event
async def on_guild_join(guild):
    general = find(lambda x: x.name == 'general',  guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        embed = gen_embed(name=f'{guild.name}',
                        icon_url = guild.icon_url,
                        title = 'Thanks for inviting me!',
                        content = 'You can get started by typing \%help to find the current command list.\nChange the command prefix by typing \%setprefix, and configure server settings with serverconfig and channelconfig.\n\nSource code: https://github.com/neon10lights/Epsilon\nSupport: https://ko-fi.com/neonlights\nIf you have feedback or need help, please DM Neon#5555.')
        await general.send(embed = embed)

@bot.event
async def on_member_join(member):
    log.info(f"A new member joined in {member.guild.name}")
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['autorole']:
        role = discord.utils.find(lambda r: r.name == str(document['autorole']), member.guild.roles)
        if role:
            await member.add_roles(role)
            log.info("Auto-assigned role to new member in {}".format(member.guild.name))
        else:
            log.error("Auto-assign role does not exist!")
    if document['welcome_message'] and document['welcome_channel']:
        welcome_channel = find(lambda c: c.id == int(document['welcome_channel'], member.guild.text_channels))
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                        icon_url= member.avatar_url, 
                        title=f"Welcome to {member.guild.name}", 
                        content=document['welcome_message'])
        if document['welcome_banner']:
            embed.set_image(document['welcome_banner'])
        await welcome_channel.send(embed = embed)

###################

def is_owner():
    async def predicate(ctx):
        if ctx.message.author.id == 133048058756726784:
            return True
        else:
            return False
    return commands.check(predicate)

async def generate_invite_link(permissions=discord.Permissions(335932630), guild=None):
    app_info = await bot.application_info()
    return discord.utils.oauth_url(app_info.id, permissions=permissions, guild=guild)

async def get_msgid(message, attempts = 1):
    pipeline = [{'$match': {'$and': [{'server_id': message.guild.id}, {'author_id': {'$not': {'$regex': str(bot.user.id)}}}] }}, {'$sample': {'size': 1}}]
    async for msgid in db.msgid.aggregate(pipeline):
            for channel in message.guild.channels:
                if channel.id == msgid['channel_id']:
                    try:
                        msg = await channel.fetch_message(msgid['msg_id'])
                        #log.info(msg.content)
                        if (re.match('^%|^\^|^\$|^!|^\.|@', msg.content) == None) and (re.match(f'<@!?{bot.user.id}>', msg.content) == None) and (len(msg.embeds) == 0) and (msg.author.bot == False):
                            log.info("Attempts taken:{}".format(attempts))
                            log.info("Message ID:{}".format(msg.id))
                            return msg.clean_content
                        else:
                            attempts += 1
                            mid = msgid['msg_id']
                            await db.msgid.delete_one({"msg_id": mid})
                            log.info("Removing entry from db...")
                            return await get_msgid(message, attempts)

                    except discord.Forbidden:
                        raise discord.exceptions.CommandError("I don't have permissions to read message history.")

                    except discord.NotFound:
                        attempts += 1
                        mid = msgid['msg_id']
                        await db.msgid.delete_one({"msg_id": mid})
                        log.info("Removing entry from db...")
                        return await get_msgid(message, attempts)

####################

@bot.command(name = "stats",
            description = "Gives statistics about the bot.")
async def stats(ctx):
    content = discord.Embed(colour = 0x1abc9c)
    content.set_author(name = f"{NAME} v{BOTVERSION}", icon_url = bot.user.avatar_url)
    content.set_footer(text = "Fueee~")
    content.add_field(name = "Author", value = "Neon#5555")
    content.add_field(name = "BotID", value = bot.user.id)
    content.add_field(name = "Messages", value = f"{message_count} ({(message_count / ((time.time()-uptime) / 60)):.2f}/min)")
    process = psutil.Process(os.getpid())
    mem = process.memory_full_info()
    mem = mem.uss / 1000000
    content.add_field(name = "Memory Usage", value = f'{mem:.2f} MB')
    content.add_field(name = "Servers", value = f"I am running on {str(len(bot.guilds))} servers")
    ctime = float(time.time()-uptime)
    day = ctime // (24 * 3600)
    ctime = ctime % (24 * 3600)
    hour = ctime // 3600
    ctime %= 3600
    minutes = ctime // 60
    content.add_field(name = "Uptime", value = f"{day:.0f} days\n{hour:.0f} hours\n{minutes:.0f} minutes")
    await ctx.send(embed = content)

@bot.command(name = 'joinserver',
            description = 'Creates a link to invite the bot to another server.')
async def joinserver(ctx):
    url = await generate_invite_link()
    content = discord.Embed(colour = 0x1abc9c)
    content.set_author(name = f"{NAME} v{BOTVERSION}", icon_url = bot.user.avatar_url)
    content.set_footer(text = "Fueee~")
    content.add_field(name = "Invite Link:", value = url)
    await ctx.send(embed = content)

@bot.command(name = 'leave',
            description = 'Makes the bot leave the server and purges all information from database.')
@is_owner()
async def leave(ctx):
    await db.msgid.delete_many({'server_id': ctx.guild.id})
    await db.warns.delete_many({'server_id': ctx.guild.id})
    await db.servers.delete_one({'server_id': ctx.guild.id})
    await ctx.guild.leave()

bot.remove_command('help')
bot.load_extension("commands.help")
bot.load_extension("commands.utility")
bot.load_extension("commands.errorhandler")
bot.load_extension("commands.administration")
bot.load_extension("commands.fun")
bot.load_extension("commands.modmail")
bot.run(TOKEN)
