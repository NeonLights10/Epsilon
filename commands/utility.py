import asyncio
import discord
import datetime
import random
import time
import re

from datetime import timedelta
from discord.ext import commands
from formatting.embed import gen_embed
from formatting.constants import TIMEZONE_DICT
from __main__ import log

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
                    content=f"{ctx.author.mention} rolled a {str(answer)}"
                    )
        await ctx.send(embed=embed)

    @commands.command(name='time',
                    description="Print the current date and time in UTC. If a timezone is specified, the time will be displayed in that timezone.",
                    help = "Usage:\n\n^time [timezone]")
    async def time(self, ctx, timezone=None):
        """
        Usage:
            {command_prefix}time [timezone]
        Prints the current date and time in UTC.
        If a timezone is specified, the time will be displayed in that timezone.
        """        
        #Get current time in UTC.
        current_time = datetime.datetime.utcnow()
       
        #If a timezone is specified let's convert time into that timezone.
        if timezone:
            timezone = timezone.upper()
            if re.search('(UTC)(\+|\-)(\d{2})(:\d{2})?', timezone):
                if find_key(TIMEZONE_DICT, timezone):
                    pass
                else:
                    raise discord.exceptions.UserInputError("This is not a valid timezone.")
            else:
                #Let's convert the abbreviation into UTC format
                try:
                    timezone = TIMEZONE_DICT[timezone]
                except KeyError:
                    raise discord.exceptions.UserInputError("This is not a valid timezone.")
            #Take care of those pesky 30 or 45 minute intervals that some timezones have (I'm looking at you, NST :/)
            if ":" in timezone:
                timezone_parsed = timezone.split(":")
                timezone_hour = timezone_parsed[0]
                timezone_minute = timezone_parsed[1]
                try:
                    hour = int(timezone_hour[3:len(timezone_hour)])
                    minute = int(timezone_minute)
                except ValueError:
                    raise discord.exceptions.UserInputError("This is not a valid timezone.")
                 
                current_time = current_time + timedelta(hours=hour, minutes=minute)
            else:
                try:
                    hour = int(timezone[3:len(timezone)])
                except ValueError:
                    raise discord.exceptions.UserInputError("This is not a valid timezone.")

                current_time = current_time + timedelta(hours=hour)
        else:
            timezone = "UTC"
            
        current_time = current_time.strftime('%Y-%m-%d | %H:%M ' + timezone)
        msg = f"The current time is: {current_time}"
        embed = gen_embed(title = "time", content = f"{msg}")
        await ctx.send(embed=embed)

    '''@time.error
    async def time_error(self, ctx, error):
        if isinstance(error, commands.UserInputError):
            await ctx.send(embed = gen_embed(title="Input Error", content=f"{error.message}"))'''

def setup(bot):
    bot.add_cog(Utility(bot))

