import discord
import traceback
import asyncio
import time

from typing import Union, Optional
from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log, db

class Modmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def modmail_enabled():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                return True
            else:
                return False
        return commands.check(predicate)

    @commands.command(name = 'modmail',
                    description = 'Send a modmail to the moderators.',
                    help = 'Usage:\n\n^modmail <message>')
    @modmail_enabled()
    async def modmail(self, ctx, *, content: str):
        embed = gen_embed(name = f'{ctx.author.name}#{ctx.author.discriminator}', icon_url = ctx.author.avatar_url, content = content)
        embed.set_footer(text = f"UID: {ctx.author.id} | {time.ctime()}")
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], ctx.guild.channels)
        await channel.send(embed = embed)
        await ctx.send(embed = gen_embed(title = 'Modmail sent', content = 'The moderators will review your message and get back to you shortly.'))

    @modmail.error
    async def modmail_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            log.warning("Error: Modmail is Disabled")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Disabled Command', content = 'Sorry, modmail is disabled.'))

def setup(bot):
    bot.add_cog(Modmail(bot))