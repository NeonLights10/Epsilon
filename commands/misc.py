import discord
import asyncio
import psutil
import time
import os
import csv
import dateutil.parser

from discord.ext import commands
from __main__ import log, db, message_count, uptime
from formatting.embed import gen_embed

from formatting.constants import VERSION as BOTVERSION
from formatting.constants import NAME

class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner():
        async def predicate(ctx):
            if ctx.message.author.id == 133048058756726784:
                return True
            else:
                return False
        return commands.check(predicate)

    async def generate_invite_link(self, permissions=discord.Permissions(340126934), guild=None):
        app_info = await self.bot.application_info()
        return discord.utils.oauth_url(app_info.id, permissions=permissions, guild=guild)

    @commands.command(name = "stats",
                description = "Gives statistics about the bot.")
    async def stats(self, ctx):
        content = discord.Embed(colour = 0x1abc9c)
        content.set_author(name = f"{NAME} v{BOTVERSION}", icon_url = self.bot.user.avatar_url)
        content.set_footer(text = "Fueee~")
        content.add_field(name = "Author", value = "Neon#5555")
        content.add_field(name = "BotID", value = self.bot.user.id)
        content.add_field(name = "Messages", value = f"{message_count} ({(message_count / ((time.time()-uptime) / 60)):.2f}/min)")
        process = psutil.Process(os.getpid())
        mem = process.memory_full_info()
        mem = mem.uss / 1000000
        content.add_field(name = "Memory Usage", value = f'{mem:.2f} MB')
        content.add_field(name = "Servers", value = f"I am running on {str(len(self.bot.guilds))} servers")
        ctime = float(time.time()-uptime)
        day = ctime // (24 * 3600)
        ctime = ctime % (24 * 3600)
        hour = ctime // 3600
        ctime %= 3600
        minutes = ctime // 60
        content.add_field(name = "Uptime", value = f"{day:.0f} days\n{hour:.0f} hours\n{minutes:.0f} minutes")
        await ctx.send(embed = content)

    @commands.command(name = 'joinserver',
                description = 'Creates a link to invite the bot to another server.')
    async def joinserver(self, ctx):
        url = await self.generate_invite_link()
        content = discord.Embed(colour = 0x1abc9c)
        content.set_author(name = f"{NAME} v{BOTVERSION}", icon_url = self.bot.user.avatar_url)
        content.set_footer(text = "Fueee~")
        content.add_field(name = "Invite Link:", value = url)
        await ctx.send(embed = content)

    @commands.command(name = 'leave',
                description = 'Makes the bot leave the server and purges all information from database.')
    @is_owner()
    async def leave(self, ctx):
        await db.msgid.delete_many({'server_id': ctx.guild.id})
        await db.warns.delete_many({'server_id': ctx.guild.id})
        await db.servers.delete_one({'server_id': ctx.guild.id})
        await ctx.guild.leave()

    @commands.command(name = 'unload',
                    description = 'Unload a cog.')
    @is_owner()
    async def unload(self, ctx, cog_name: str):
        self.bot.unload_extension(cog_name)
        await ctx.send(embed = gen_embed(title = 'Unload Cog', content = f'{cog_name} unloaded.'))

    @commands.command(name = 'load',
                    description = 'Load a cog.')
    @is_owner()
    async def load(self, ctx, cog_name: str):
        self.bot.load_extension(cog_name)
        await ctx.send(embed = gen_embed(title = 'Load Cog', content = f'{cog_name} loaded.'))

    @commands.command(name = 'reload',
                    description = 'Reload a cog.')
    @is_owner()
    async def reload(self, ctx, cog_name: str):
        self.bot.unload_extension(cog_name)
        self.bot.load_extension(cog_name)
        await ctx.send(embed = gen_embed(title = 'Reload Cog', content = f'{cog_name} reloaded.'))

    @commands.command(name = 'exec',
                    description = 'exec',
                    help = 'dev only')
    @is_owner()
    async def cmd_debug(self, ctx, *, data):
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith('```') and data.endswith('```'):
            data = '\n'.join(data.rstrip('`\n').split('\n')[1:])

        code = data.strip('` \n')

        scope = globals().copy()
        scope.update({'self': self})

        try:
            result = eval(code, scope)
        except:
            try:
                exec(code, scope)
            except Exception as e:
                traceback.print_exc(chain=False)
                await ctx.send("{}: {}".format(type(e).__name__, e))

        if asyncio.iscoroutine(result):
            result = await result

    @commands.command(name = 'updatedb',
                    description = 'dev only')
    @is_owner()
    async def updatedb(self, ctx):
        with open("commands/db/warn_db.csv", encoding="utf8") as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count == 0:
                    log.info(f'Column names are {", ".join(row)}')
                    line_count += 1
                post = {
                    'time': dateutil.parser.parse(row['time']),
                    'server_id': 432379300684103699, #ctx.guild.id,
                    'user_name': row['user_name'],
                    'user_id': int(row['user_id']),
                    'moderator': row['moderator'],
                    'message_link': row['message_link'],
                    'reason': row['reason']
                }
                await db.warns.insert_one(post)
                line_count += 1
            print(f'Processed {line_count} lines.')

def setup(bot):
    bot.add_cog(Miscellaneous(bot))