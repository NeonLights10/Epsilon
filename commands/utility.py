import asyncio
import discord
import datetime
import random

from discord.ext import commands
from formatting.embed import gen_embed

def find_key(dic, val):
    try:
        #99% sure there is a less convoluted way to implement this
        key = [k for k, v in TIMEZONE_DICT.items() if v == val][0]
        return True
    except:
        return False

class Utility(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(name='roll', 
					description="Generates a random number from 0-100 unless you specify a max number.",
					help = 'Examples:\n\n^roll 20')
	async def roll(self, ctx, num: int = 100):
		answer = random.randint(0, num)
		embed = gen_embed(
			name=f"{ctx.author.name}#{ctx.author.discriminator}", 
			icon_url=ctx.author.avatar_url, 
			title="roll",
			content=f"{ctx.author.mention} rolled a {str(answer)}")
		await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Utility(bot))

