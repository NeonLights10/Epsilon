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

    @commands.command(name = 'roll', 
                    description = "Generates a random number from 0-100 unless you specify a max number.",
                    help = 'Examples:\n\n^roll 20')
    async def roll(self, ctx, num: int = 100):
        answer = random.randint(0, num)
        embed = gen_embed(
                    name = f"{ctx.author.name}#{ctx.author.discriminator}", 
                    icon_url = ctx.author.avatar_url, 
                    title = "roll",
                    content = f"{ctx.author.mention} rolled a {str(answer)}"
                    )
        await ctx.send(embed = embed)

    @commands.command(name = 'time',
                    description = "Print the current date and time in UTC. If a timezone is specified, the time will be displayed in that timezone.",
                    help = "Usage:\n\n^time [timezone]")
    async def time(self, ctx, timezone = None):
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
                    log.warning("Invalid Timezone")
                    await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid timezone."))
                    return
            else:
                #Let's convert the abbreviation into UTC format
                try:
                    timezone = TIMEZONE_DICT[timezone]
                except KeyError:
                    log.warning("KeyError: Invalid Timezone")
                    await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid timezone."))
                    return
            #Take care of those pesky 30 or 45 minute intervals that some timezones have (I'm looking at you, NST :/)
            if ":" in timezone:
                timezone_parsed = timezone.split(":")
                timezone_hour = timezone_parsed[0]
                timezone_minute = timezone_parsed[1]
                try:
                    hour = int(timezone_hour[3:len(timezone_hour)])
                    minute = int(timezone_minute)
                except ValueError:
                    log.warning("ValueError: Invalid Timezone")
                    await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid timezone."))
                    return
                 
                current_time = current_time + timedelta(hours = hour, minutes = minute)
            else:
                try:
                    hour = int(timezone[3:len(timezone)])
                except ValueError:
                    log.warning("ValueError: Invalid Timezone")
                    ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid timezone."))
                    return
                current_time = current_time + timedelta(hours = hour)
        else:
            timezone = "UTC"
            
        current_time = current_time.strftime('%Y-%m-%d | %H:%M ' + timezone)
        msg = f"The current time is: {current_time}"
        embed = gen_embed(title = "time", content = f"{msg}")
        await ctx.send(embed = embed)

    @commands.command(name = 'tconvert',
                    description = "Converts time from one timezone to another. All times in 24 hour time.",
                    help = "Usage:\n\n {command_prefix}tconvert [time] [timezone_from] [timezone_to]")
    async def tconvert(self, ctx, time_in: str, timezone1: str, timezone2: str):
        #Parse time first
        time_parsed = time_in.split(":")
        try:
            hour = int(time_parsed[0])
            minute = int(time_parsed[1])
        except ValueError:
            log.warning("ValueError: Invalid Time")
            await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid time."))
            return
        if hour > 23 or hour < 0 or minute > 59 or minute < 0:
            log.warning("UserError: Invalid Time")
            await ctx.send(embed = gen_embed(title = "Input Error", content = "You entered a time that does not exist! Make sure the hour is not negative or greater than 24, and that minutes are within 00-59."))
            return

        #Now parse from timezone and separate into hours and minutes, and get the combined minute version
        timezone1 = timezone1.upper()
        try:
            if re.search('(UTC)(\+|\-)(\d{1,2})(:\d{2})?', timezone1):
                if find_key(TIMEZONE_DICT, timezone1):
                    pass
                else:
                    log.warning("Invalid Timezone")
                    await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid [from] timezone."))
                    return
            else:
                timezone1 = TIMEZONE_DICT[timezone1]
        except KeyError:
            log.warning("KeyError: Invalid Timezone")
            await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid [from] timezone."))
            return
        if ":" in timezone1:
            timezone1_parsed = timezone1.split(":")
            try:
                timezone1_hour = timezone1_parsed[0]
                timezone1_hour = int(timezone1_hour[3:len(timezone1_hour)])
                timezone1_minute = int(timezone1_parsed[1])
                if timezone1_hour < 0:
                    timezone1_combined = timezone1_hour * 60 - timezone1_minute
                elif timezone1_hour > 0:
                    timezone1_combined = timezone1_hour * 60 + timezone1_minute
                elif timezone1_hour == 0:
                    timezone1_combined = 0
            except ValueError:
                log.warning("ValueError: Timezone Dictionary Error")
                await ctx.send(embed = gen_embed(title = "Timezone Dictionary Error", content = "There is an error with the timezone dictionary."))
                return
        else:
            try:
                timezone1_hour = int(timezone1[3:len(timezone1)])
                timezone1_combined = timezone1_hour * 60
            except ValueError:
                log.warning("ValueError: Timezone Parse Error")
                await ctx.send(embed = gen_embed(title = "Parsing Error", content = "Could not parse timezone."))
                return
        
        #Do the same with timezone 2, make sure it's nested in timezone1 check
        timezone2 = timezone2.upper()
        try:
            if re.search('(UTC)(\+|\-)(\d{2})(:\d{2})?', timezone2):
                if find_key(TIMEZONE_DICT, timezone2):
                    pass
                else:
                    log.warning("Invalid Timezone")
                    await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid [to] timezone."))
                    return
            else:
                timezone2 = TIMEZONE_DICT[timezone2]
        except KeyError:
            log.warning("KeyError: Invalid Timezone")
            await ctx.send(embed = gen_embed(title = "Input Error", content = "This is not a valid [to] timezone."))
            return
        if ":" in timezone2:
            timezone2_parsed = timezone2.split(":")
            try:
                timezone2_hour = timezone2_parsed[0]
                timezone2_hour = int(timezone2_hour[3:len(timezone2_hour)])
                timezone2_minute = int(timezone2_parsed[1])
                if timezone2_hour < 0:
                    timezone2_combined = timezone2_hour * 60 - timezone2_minute
                elif timezone2_hour > 0:
                    timezone2_combined = timezone2_hour * 60 + timezone2_minute
                elif timezone2_hour == 0:
                    timezone2_combined = 0;
            except ValueError:
                log.warning("ValueError: Timezone Dictionary Error")
                await ctx.send(embed = gen_embed(title = "Timezone Dictionary Error", content = "There is an error with the timezone dictionary."))
                return
        else:
            try:
                timezone2_hour = int(timezone2[3:len(timezone2)])
                timezone2_combined = timezone2_hour * 60
            except ValueError:
                log.warning("ValueError: Timezone Parse Error")
                await ctx.send(embed = gen_embed(title = "Parsing Error", content = "Could not parse timezone."))
                return
            
        #Catch all the different scenarios that could happen
        if timezone1_hour == 0:
            difference = timezone2_combined
        elif timezone2_hour == 0:
            if timezone1_hour < timezone2_hour:
                difference = abs(timezone1_combined)
            elif timezone1_hour > timezone2_hour:
                difference = -timezone1_combined
        elif timezone1_hour < 0 and timezone2_hour < 0:
            difference = abs(timezone1_combined) - abs(timezone2_combined)
        elif timezone1_hour < 0 and timezone2_hour > 0:
            difference = abs(timezone1_combined) + abs(timezone2_combined)
        elif timezone1_hour > 0 and timezone2_hour < 0:
            difference = -(abs(timezone1_combined) + abs(timezone2_combined))
        elif timezone1_hour > 0 and timezone2_hour > 0:
            difference = abs(timezone1_combined - timezone2_combined)
        
        converted_time = hour * 60 + minute + difference
        hour = int(converted_time / 60)
        #Make sure time isn't reported in negative time (because that doesn't exist) OR >24 (because that also doesn't exist)
        if hour < 0:
            hour = 24 + hour
        if hour >= 24:
            hour = abs(24 - hour)
        minute = converted_time % 60
        #print(converted_time)
       
        #I'm lazy, probably a better way to do this
        if minute == 0:
            minute = str(minute) + "0"
        elif minute < 10:
            minute = "0" + str(minute)
        final_time = str(hour) + ":" + str(minute)

        embed = gen_embed(title = "tconvert", content = f"Converted time from **{timezone1}** to **{timezone2}** is **{final_time}**")
        await ctx.send(embed = embed)      

def setup(bot):
    bot.add_cog(Utility(bot))

