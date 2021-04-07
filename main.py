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

# read config information
with open("config.json") as file:
    config_json = json.load(file)
    TOKEN = config_json["token"]


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

dlog = logging.getLogger('discord')
dlog.setLevel(logging.WARNING)

intents = discord.Intents.default()
intents.members = True

prefix = "^"
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

if os.path.isfile("logs/epsilon.log"):
    log.info("Moving old bot log")
    try:
        if os.path.isfile("logs/epsilon.log.last"):
            os.unlink("logs/epsilon.log.last")
        os.rename("logs/epsilon.log", "logs/epsilon.log.last")
    except:
        pass

with open("logs/epsilon.log", 'w', encoding = 'utf8') as f:
    f.write('\n')
    f.write(" PRE-RUN CHECK PASSED ".center(80, '#'))
    f.write('\n\n')

fhandler = logging.FileHandler("logs/epsilon.log", mode = 'a')
fhandler.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
))
fhandler.setLevel(logging.DEBUG)
log.addHandler(fhandler)

####################

#db init and first time setup
log.info(f'\nEstablishing connection to MongoDB database {databaseName}')

mclient = motor.motor_asyncio.AsyncIOMotorClient()
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
            'welcome_banner': None
            }
    log.info(f"Creating document for {guild.name}...")
    await db.servers.insert_one(post)


async def _check_document(guild, id):
    log.info("Checking db document for {}".format(guild.name))
    if await db.servers.find_one({"server_id": id}) == None:
        log.info("Did not find one, creating document...")
        await _initialize_document(guild, id)

####################

log.info('Starting Epsilon {}'.format(BOTVERSION))

bot = commands.Bot(command_prefix = prefix, intents = intents, case_insensitive = True)

try:
    sys.stdout.write("\x1b]2;Epsilon {}\x07".format(BOTVERSION))
except:
    pass

uptime = time.time()
message_count = 0

####################

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await _check_document(guild, guild.id)

    log.info("\n### PRE-STARTUP CHECKS PASSED ###\n")

    ####################

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
    post = {'server_id': ctx.guild.id,
            'channel_id': ctx.channel.id,
            'author_id': ctx.author.id,
            'msg_id': ctx.message.id}
    await db.msgid.insert_one(post)

    if ctx.author.bot is False:
        if ctx.prefix:
            log.info(f"{ctx.message.author.id}/{ctx.message.author.name}{ctx.message.author.discriminator}: {ctx.message.content}")
        if ctx.message.reference:
            ref_message = await ctx.message.channel.fetch_message(ctx.message.reference.message_id)
            if ref_message.author == bot.user:
                log.info("Found a mention of myself, generating response...")
                msg = await get_msgid(ctx.message)
                log.info(f"Message retrieved: {msg}\n")
                await ctx.message.reply(content = msg)
        elif bot.user.id in ctx.message.raw_mentions and ctx.author != bot.user:
            log.info("Found a mention of myself, generating response...")
            msg = await get_msgid(ctx.message)
            log.info(f"Message retrieved: {msg}\n")
            await ctx.message.reply(content = msg)

        await bot.invoke(ctx)

@bot.event
async def on_guild_join(guild):
    general = find(lambda x: x.name == 'general',  guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        await general.send("Thanks for inviting me!")

@bot.event
async def on_member_join(member):
    log.info(f"A new member joined in {member.guild.name}")
    document = await dbservers.find_one({"server_id": member.guild.id})
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

async def get_msgid(message, attempts = 1):
    pipeline = [{'$match': {'$and': [{'server_id': message.guild.id}, {'author_id': {'$not': {'$regex': str(bot.user.id)}}}] }}, {'$sample': {'size': 1}}]
    async for msgid in db.msgid.aggregate(pipeline):
            for channel in message.guild.channels:
                if channel.id == msgid['channel_id']:
                    try:
                        msg = await channel.fetch_message(msgid['msg_id'])
                        #log.info(msg.content)
                        if (re.match('^%|\^|^\$|^!|@', msg.content) == None) and (re.match(f'<@!?{bot.user.id}>', msg.content) == None) and (len(msg.embeds) == 0) and (msg.author.bot == False):
                            log.info("Attempts taken:{}".format(attempts))
                            log.info("Message ID:{}".format(msg.id))
                            return msg.clean_content
                        else:
                            attempts += 1
                            mid = msgid['msg_id']
                            await db.msgid.delete_one({"msg_id": mid})
                            return await get_msgid(message, attempts)

                    except discord.Forbidden:
                        raise discord.exceptions.CommandError("I don't have permissions to read message history.")

                    except discord.NotFound:
                        attempts += 1
                        mid = msgid['msg_id']
                        await db.msgid.delete_one({"msg_id": mid})
                        return await get_msgid(message, attempts)

####################

@bot.command(name = "stats",
            description = "Gives statistics about the bot.")
async def stats(ctx):
    content = discord.Embed(colour = 0x1abc9c)
    content.set_author(name = "Epsilon v" + BOTVERSION, icon_url = bot.user.avatar_url)
    content.set_footer(text = "Sugoi!")
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
    content.add_field(name = "Uptime", value = f"{day:d} days\n{hour:d} hours\n%{minutes:d} minutes")
    await ctx.send(embed = content)

bot.remove_command('help')
bot.load_extension("commands.help")
bot.load_extension("commands.utility")
bot.load_extension("commands.errorhandler")
bot.load_extension("commands.administration")
bot.run(TOKEN)
