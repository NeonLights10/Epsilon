import discord
import asyncio

from discord.ext import commands
from formatting.embed import gen_embed
from typing import Union, Optional
from __main__ import log, db

class Testing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_owner():
        async def predicate(ctx):
            if ctx.message.author.id == 133048058756726784:
                return True
            else:
                return False
        return commands.check(predicate)

    @commands.command(name='helloworld',
                      description='Hello World.')
    @is_owner()
    async def load(self, ctx):
        await ctx.send(embed=gen_embed(title='Hello World', content=f'I am Kanon Bot.'))