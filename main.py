import json
import asyncio
import os
import sys
import logging
import time

import re
import random

import discord
import colorlog
import motor.motor_asyncio

from discord.ext import commands
from discord.utils import find, get
from pymongo import MongoClient

from commands.constants import VERSION as BOTVERSION

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

uptime = time.time()
message_count = 0

####################

def _get_owner(bot, *, server=None):
    return discord.utils.find(
        lambda m: m.id == bot.owner_id,
        server.members if server else bot.get_all_members()
    )

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

    log.info(f"Set logging level to {config_json['log_level']}")

    if config_json["debug_mode"] == True:
        debuglog = logging.getLogger('discord')
        debuglog.setLevel(logging.DEBUG)
        dhandler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
        dhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
        debuglog.addHandler(dhandler)

    if os.path.isfile("logs/epsilon.log"):
        log.info("Moving old bot log")
        try:
            if os.path.isfile("logs/epsilon.log.last"):
                os.unlink("logs/epsilon.log.last")
            os.rename("logs/epsilon.log", "logs/epsilon.log.last")
        except:
            pass

    with open("logs/epsilon.log", 'w', encoding='utf8') as f:
        f.write('\n')
        f.write(" PRE-RUN CHECK PASSED ".center(80, '#'))
        f.write('\n\n')

    fhandler = logging.FileHandler("logs/epsilon.log", mode='a')
    fhandler.setFormatter(logging.Formatter(
        fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
    ))
    fhandler.setLevel(logging.DEBUG)
    log.addHandler(fhandler)

def _gen_embed(command, content):
        """Provides a basic template for embeds"""
        e = discord.Embed(colour=0x1abc9c)
        e.set_author(name="Epsilon v{}".format(BOTVERSION), icon_url=bot.user.avatar_url)
        e.set_footer(text="Sugoi!")
        e.title = title
        e.description = content
        return e 

_setup_logging()

#db init and first time setup
log.info(f'\nEstablishing connection to MongoDB database {databaseName}')

mclient = motor.motor_asyncio.AsyncIOMotorClient()
db = mclient[databaseName]

log.info(f'Database loaded.\n')

async def _initialize_document(guild, id):
    post = {'server_id': id,
            'name': guild.name,
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

bot = commands.Bot(command_prefix=prefix, intents=intents, case_insensitive=True)

try:
    sys.stdout.write("\x1b]2;Epsilon {}\x07".format(BOTVERSION))
except:
    pass

####################

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await _check_document(guild, guild.id)

    log.info("\n### PRE-STARTUP CHECKS PASSED ###\n")

    ####################

    log.info(f"Connected: {bot.user.id}/{bot.user.name}#{bot.user.discriminator}\n")
    #owner = _get_owner(bot)
    #log.info(f"Owner: {owner.id}/{owner.name}#{owner.discriminator}\n")

    log.info("Guild List:")
    for s in bot.guilds:
        ser = (f'{s.name} (unavailable)' if s.unavailable else s.name)
        log.info(f" - {ser}")    
    print(flush=True)

@bot.event
async def on_message(message):
    ctx = await bot.get_context(message)
    post = {'server_id': ctx.guild.id,
            'channel_id': ctx.channel.id,
            'author_id': ctx.author.id,
            'msg_id': ctx.message.id}
    await db.msgid.insert_one(post)

    if ctx.author.bot is False:
        if ctx.prefix:
            log.info(f"{ctx.message.author.id}/{ctx.message.author.name}{ctx.message.author.discriminator}: {ctx.message.content}")
        elif bot.user.id in ctx.message.raw_mentions and ctx.author != bot.user:
            log.info("Found a mention of myself, generating response...")
            msg = await get_msgid(ctx.message)
            log.info(f"Message retrieved: {msg}\n")
            await ctx.channel.send(content = msg, reference= ctx.message)

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
            raise ValueError("Auto-assign role does not exist!")
    else:
        pass

###################

async def get_msgid(message, attempts = 1):
    pipeline = [{'$match': {'$and': [{'server_id': message.guild.id}, {'author_id': {'$not': {'$regex': str(bot.user.id)}}}] }}, {'$sample': {'size': 1}}]
    async for msgid in db.msgid.aggregate(pipeline):
            for channel in message.guild.channels:
                if channel.id == msgid['channel_id']:
                    try:
                        msg = await channel.fetch_message(msgid['msg_id'])
                        #log.info(msg.content)
                        if (re.match('^%|^\$|^!|@', msg.content) == None) and (re.match(f'<@!?{bot.user.id}>', msg.content) == None) and (len(msg.embeds) == 0) and (msg.author.bot == False):
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

bot.run(TOKEN)
