import discord
import aiohttp

from formatting.embed import gen_embed
from formatting.constants import NAME
from typing import Optional
from discord.ext import commands

from __main__ import db, log

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def fun_enabled():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            is_fun = document['fun']
            return is_fun
        return commands.check(predicate)

    async def _get_gif(self, type, msg):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://nekos.life/api/v2/img/{}'.format(type)) as resp:
                if resp.status == 200:
                    rjson = await resp.json()
                    content = discord.Embed(colour=0x1abc9c)
                    content.set_footer(text="Sugoi!")
                    url = rjson.get('url')
                    #something something 2 positional parameters so i have to do this extra variable assignment
                    content.set_image(url=url)
                    content.description = msg
                    return content
                else:
                    log.error("The API returned a status code of {}. This might mean that the service is unavailable at this time. Try again later?".format(resp.status))

    @commands.command(name = 'hug',
                    description = f'Hug someone! If no one is specified, {NAME} will hug you <3',
                    help = 'Usage\n\n^poke [user mentions/user ids/user name + discriminator (ex: name#0000)')
    @fun_enabled()
    async def hug(self, ctx, members: commands.Greedy[discord.Member]):
        if members:
            msg = f'{ctx.author.mention} hugged'
            if len(members) > 1:
                if len(members) == 2:
                    msg = msg + f' {members[0].mention} '
                else:
                    for i in range(len(members) - 1):
                        msg = msg + f' {members[i].mention},'
                msg = msg + f'and {members[len(members) - 1].mention}!'
            else:
                msg = msg + f' {members[0].mention}!'
        else:
            msg = f'{NAME} gives {ctx.author.mention} a soft hug :heart:'

        content = await self._get_gif("hug", msg)
        await ctx.send(embed = content)

    @commands.command(name = 'cuddle',
                    description = f'Cuddle someone! If no one is specified, {NAME} will cuddle you <3',
                    help = 'Usage\n\n^poke [user mentions/user ids/user name + discriminator (ex: name#0000)')
    @fun_enabled()
    async def cuddle(self, ctx, members: commands.Greedy[discord.Member]):
        if members:
            msg = f'{ctx.author.mention} cuddles'
            if len(members) > 1:
                if len(members) == 2:
                    msg = msg + f' {members[0].mention} '
                else:
                    for i in range(len(members) - 1):
                        msg = msg + f' {members[i].mention},'
                msg = msg + f'and {members[len(members) - 1].mention}!'
            else:
                msg = msg + f' {members[0].mention}!'
        else:
            msg = f'{NAME} takes a minute to cuddle {ctx.author.mention} :heart:'

        content = await self._get_gif("cuddle", msg)
        await ctx.send(embed = content)

    @commands.command(name = 'poke',
                    description = f'Poke someone! If no one is specified, {NAME} will poke you :P',
                    help = 'Usage\n\n^poke [user mentions/user ids/user name + discriminator (ex: name#0000)')
    @fun_enabled()
    async def poke(self, ctx, members: commands.Greedy[discord.Member]):
        if members:
            msg = f'{ctx.author.mention} poked'
            if len(members) > 1:
                if len(members) == 2:
                    msg = msg + f' {members[0].mention} '
                else:
                    for i in range(len(members) - 1):
                        msg = msg + f' {members[i].mention},'
                msg = msg + f'and {members[len(members) - 1].mention}!'
            else:
                msg = msg + f' {members[0].mention}!'
        else:
            msg = f'{NAME} pokes you :stuck_out_tongue_closed_eyes:'

        content = await self._get_gif("poke", msg)
        await ctx.send(embed = content)

    @commands.command(name = 'headpat',
                    description = f'Headpat someone! If no one is specified, {NAME} will give you a headpat <3',
                    help = 'Usage\n\n^headpat [user mentions/user ids/user name + discriminator (ex: name#0000)')
    @fun_enabled()
    async def headpat(self, ctx, members: commands.Greedy[discord.Member]):
        if members:
            msg = f'{ctx.author.mention} gave'
            if len(members) > 1:
                if len(members) == 2:
                    msg = msg + f' {members[0].mention} '
                else:
                    for i in range(len(members) - 1):
                        msg = msg + f' {members[i].mention},'
                msg = msg + f'and {members[len(members) - 1].mention} a headpat!'
            else:
                msg = msg + f' {members[0].mention}!'

            msg = f'{NAME} gives {ctx.author.mention} a small headpat :heart:'

        content = await self._get_gif("headpat", msg)
        await ctx.send(embed = content)

def setup(bot):
    bot.add_cog(Fun(bot))