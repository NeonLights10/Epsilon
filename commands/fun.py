import discord
import aiohttp

from formatting.constants import NAME
from discord.ext import commands
from discord.commands import Option
from __main__ import log, db


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        return document['fun']

    async def _get_gif(self, type, msg):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://nekos.life/api/v2/img/{}'.format(type)) as resp:
                if resp.status == 200:
                    rjson = await resp.json()
                    content = discord.Embed(colour=0x1abc9c)
                    content.set_footer(text="Fueee~")
                    url = rjson.get('url')
                    # something something 2 positional parameters so i have to do this extra variable assignment
                    content.set_image(url=url)
                    content.description = msg
                    return content
                else:
                    log.error(
                        "The API returned a status code of {}. This might mean that the service is unavailable at this time. Try again later?".format(
                            resp.status))

    @discord.slash_command(name='hug',
                           description=f'Hug someone! If no one is specified, {NAME} will hug you <3')
    async def hug(self,
                  ctx: discord.ApplicationContext,
                  member: Option(discord.User, "User to hug", required=False)):
        if member:
            msg = f'{ctx.interaction.user.mention} hugged {member.mention}!'
        else:
            msg = f'{NAME} gives {ctx.interaction.user.mention} a soft hug :heart:'
        content = await self._get_gif("hug", msg)
        await ctx.respond(embed=content)

    @discord.slash_command(name='cuddle',
                           description=f'Cuddle someone! If no one is specified, {NAME} will cuddle you <3')
    async def cuddle(self,
                     ctx: discord.ApplicationContext,
                     member: Option(discord.User, "User to cuddle", required=False)):
        if member:
            msg = f'{ctx.interaction.user.mention} cuddles {member.mention}!'
        else:
            msg = f'{NAME} takes a minute to cuddle {ctx.interaction.user.mention} :heart:'
        content = await self._get_gif("cuddle", msg)
        await ctx.respond(embed=content)

    @discord.slash_command(name='headpat',
                           description=f'Headpat someone! If no one is specified, {NAME} will give you a headpat <3')
    async def headpat(self,
                      ctx: discord.ApplicationContext,
                      member: Option(discord.User, "User to headpat", required=False)):
        if member:
            msg = f'{ctx.interaction.user.mention} gave {member.mention} a headpat!'
        else:
            msg = f'{NAME} gives {ctx.interaction.user.mention} a small headpat :heart:'
        content = await self._get_gif("pat", msg)
        await ctx.respond(embed=content)


def setup(bot):
    bot.add_cog(Fun(bot))
