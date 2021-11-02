import discord
import asyncio
import psutil
import time
import os
import csv
import dateutil.parser

from io import StringIO
from discord.ext import commands
from __main__ import log, db, uptime
import main
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
        content.add_field(name = "Messages", value = f"{main.message_count} ({(main.message_count / ((time.time()-uptime) / 60)):.2f}/min)")
        content.add_field(name="Commands Processed", value=f"{main.command_count}")
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

    @commands.command(name = 'deleteguild',
                description = 'Makes the bot leave the server specified and purges all information from database.')
    @is_owner()
    async def deleteguild(self, ctx, server_id: int):
        guild = self.bot.get_guild(server_id)
        if guild:
            await db.msgid.delete_many({'server_id': guild.id})
            await db.warns.delete_many({'server_id': guild.id})
            await db.rolereact.delete_many({'server_id': guild.id})
            await db.servers.delete_one({'server_id': guild.id})
            await db.emoji.delete_many({'server_id': guild.id})
            await db.reminders.delete_many({'server_id': guild.id})
            await guild.leave()
        await ctx.send(embed = gen_embed(title = 'deleteguild', content = f'Guild {guild.name} ({server_id}) information deleted, left server.'))

    @commands.command(name='deleteuser',
                      description='Makes the bot delete all data tied to a user id from database.')
    @is_owner()
    async def deleteuser(self, ctx, user_id: int):
        user = await self.bot.fetch_user(user_id)
        if user:
            await db.msgid.delete_many({'author_id': guild.id})
            await db.warns.delete_many({'user_id': guild.id})
            await db.reminders.delete_many({'user_id': guild.id})
        await ctx.send(embed = gen_embed(title = 'deleteuser', content = f'User {user.name}#{user.discriminator} ({user_id}) information deleted.'))

    @commands.command(name = 'unload',
                    description = 'Unload a cog.')
    @is_owner()
    async def unload(self, ctx, cog_name: str):
        cog = f"commands.{cog_name.lower()}"
        self.bot.unload_extension(cog)
        await ctx.send(embed = gen_embed(title = 'Unload Cog', content = f'{cog_name.capitalize()} unloaded.'))

    @commands.command(name = 'load',
                    description = 'Load a cog.')
    @is_owner()
    async def load(self, ctx, cog_name: str):
        cog = f"commands.{cog_name.lower()}"
        self.bot.load_extension(cog)
        await ctx.send(embed = gen_embed(title = 'Load Cog', content = f'{cog_name.capitalize()} loaded.'))

    @commands.command(name = 'reload',
                    description = 'Reload a cog.')
    @is_owner()
    async def reload(self, ctx, cog_name: str):
        cog = f"commands.{cog_name.lower()}"
        self.bot.unload_extension(cog)
        self.bot.load_extension(cog)
        await ctx.send(f"Successfully reloaded the {cog} cog")

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

    @commands.command(name = 'announce',
                    description = 'dev only, creates an announcement to send to all servers')
    @is_owner()
    async def announce(self, ctx, *, message: str):
        for guild in self.bot.guilds:
            document = db.servers.find_one({'server_id': ctx.guild.id})
            if document['announcement_channel']:
                try:
                    channel = self.bot.get_channel(document['announcement_channel'])
                    await channel.send(embed = gen_embed(title = 'Global Announcement', content = f'{message}'))
                    return
                except:
                    pass
            try:
                if guild.public_updates_channel:
                    await guild.public_updates_channel.send(embed = gen_embed(title = 'Global Announcement', content = f'{message}'))
                    return
            except:
                pass
            try:
                if guild.system_channel:
                    await guild.system_channel.send(embed = gen_embed(title = 'Global Announcement', content = f'{message}'))
                    return
            except:
                pass
            try:
                general = discord.utils.find(lambda x: x.name == 'general', guild.text_channels)
                if general and general.permissions_for(guild.me).send_messages:
                    await general.send(embed=gen_embed(title='Global Announcement', content=f'{message}'))
                    return
            except:
                pass

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

    @commands.command(name = 'objgraph',
                    description = 'dev only')
    @is_owner()
    async def objgraph(self, ctx, func='most_common_types()'):
        import objgraph

        if func == 'growth':
            f = StringIO()
            objgraph.show_growth(limit=10, file=f)
            f.seek(0)
            data = f.read()
            f.close()

        elif func == 'leaks':
            f = StringIO()
            objgraph.show_most_common_types(objects=objgraph.get_leaking_objects(), file=f)
            f.seek(0)
            data = f.read()
            f.close()

        elif func == 'leakstats':
            data = objgraph.typestats(objects=objgraph.get_leaking_objects())

        else:
            data = eval('objgraph.' + func)

        await ctx.send(f'```python\n{data}\n```')

def setup(bot):
    bot.add_cog(Miscellaneous(bot))