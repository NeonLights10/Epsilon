import asyncio
import json
import time
import math
import re
import datetime
from datetime import timezone, timedelta
from tabulate import tabulate

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

import discord
from discord.ext import commands
from discord.commands import Option, OptionChoice, SlashCommandGroup
from discord.commands.permissions import default_permissions

from formatting.embed import gen_embed
from __main__ import log, db


# adds commas to a number to make it easier to read
def format_number(number):
    number = "{:,}".format(number)
    return number


def string_check(string: str):
    import re
    string = string.replace('```', '')
    string = string.replace("?", '')
    string = re.sub('(\[(\w{6}|\w{2})\])', '', string)
    string = re.sub('\[([CcIiBbSsUu]|(sup|sub){1})\]', '', string)
    return string

def server_name(num):
    match num:
        case 0:
            return 'jp'
        case 1:
            return 'en'
        case 2:
            return 'tw'
        case 3:
            return 'cn'
        case 4:
            return 'kr'


class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncClient()
        self.client = CachingClient(self.client)

        with open("config.json") as file:
            config_json = json.load(file)
            en_event_id = int(config_json["en_event_id"])
            jp_event_id = int(config_json["jp_event_id"])
            self.valid_t10_events_en = [en_event_id, en_event_id - 1, en_event_id -
                                        2, en_event_id - 3, en_event_id - 4, en_event_id - 5]
            self.valid_t10_events_jp = [jp_event_id, jp_event_id - 1, jp_event_id -
                                        2, jp_event_id - 3, jp_event_id - 4, jp_event_id - 5]

    async def fetch_api(self, url):
        api = await self.client.get(url)
        return api.json()

    async def get_current_event_id(self, server: int):
        current_time = time.time() * 1000
        current_event_id = ''
        api = await self.fetch_api('https://bestdori.com/api/events/all.5.json')
        for event in api:
            if api[event]['startAt'][server]:
                if float(api[event]['startAt'][server]) < current_time < float(api[event]['endAt'][server]):
                    current_event_id = event
                    break
        if not current_event_id:
            try:
                for event in api:
                    try:
                        if current_time < float(api[event]['startAt'][server]):
                            current_event_id = event
                            break
                    except TypeError:  # For between events
                        continue
            except KeyError:
                current_event_id = list(api.keys())[-1]
        if current_event_id:
            return current_event_id
        else:
            return 0

    async def get_event_name(self, server: int, eventid: int):
        api = await self.fetch_api(f'https://bestdori.com/api/events/{eventid}.json')
        return api['eventName'][server]

    t10_commands = SlashCommandGroup('t10', 'T10 related commands')

    async def archive_autocomplete(self, ctx):
        return 0

    @t10_commands.command(name='archive',
                          description='Returns txt file containing 2 minute t10 updates for a specific event.')
    async def t10archive(self,
                         ctx: discord.ApplicationContext,
                         eventid: Option(str, "Enter a valid event ID",
                                         default="",
                                         required=True,
                                         autocomplete=archive_autocomplete),
                         server: Option(str, "Choose which server to return archive from",
                                        choices=[OptionChoice('EN', value='1'),
                                                 OptionChoice('JP', value='0')],
                                        required=False,
                                        default='1')):
        pass

    @t10_commands.command(name='event',
                          description='Returns current t10 info')
    async def t10(self,
                  ctx: discord.ApplicationContext,
                  server: Option(str, "Choose which server to check t10 data",
                                 choices=[OptionChoice('EN', value='1'),
                                          OptionChoice('JP', value='0'),
                                          OptionChoice('TW', value='2'),
                                          OptionChoice('CN', value='3'),
                                          OptionChoice('KR', value='4')],
                                 required=False,
                                 default='1'),
                  event: Option(int, "Event ID to check t10 info for",
                                required=False,
                                default=0,
                                min_value=1,
                                max_value=999)):
        await ctx.interaction.response.defer()
        server = int(server)
        try:
            if event == 0:
                event_id = await self.get_current_event_id(server)
            else:
                event_id = event
            api_url = f'https://bestdori.com/api/eventtop/data?server={server}&event={event_id}&mid=0&latest=1'
            t10_api = await self.fetch_api(api_url)
            event_name = await self.get_event_name(server, event_id)
            fmt = "%Y-%m-%d %H:%M:%S %Z%z"
            now_time = datetime.datetime.now(timezone(-timedelta(hours=4), 'US/Eastern'))
            i = 1
            entries = []
            for points in t10_api['points']:
                uid = points['uid']
                for user in t10_api['users']:
                    if uid == user['uid']:
                        entries.append([i, format_number(points['value']), user['rank'], user['uid'], string_check(user['name'])])
                        break
                i += 1
            output = ("```" + "  Time:  " + now_time.strftime(fmt) + "\n  Event: " + event_name + "\n\n" + tabulate(
                entries, tablefmt="plain", headers=["#", "Points", "Level", "ID", "Player"]) + "```")
            await ctx.interaction.followup.send(output)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching t10 data',
                                content=f'Failed to get data for event with ID `{event_id} (Server ID {server})`.'),
                ephemeral=True)

    @t10_commands.command(name='songs',
                          description='Posts t10 song info for the event specified')
    async def t10song(self,
                      ctx: discord.ApplicationContext,
                      server: Option(str, "Choose which server to check t10 data",
                                     choices=[OptionChoice('EN', value='1'),
                                              OptionChoice('JP', value='0'),
                                              OptionChoice('TW', value='2'),
                                              OptionChoice('CN', value='3'),
                                              OptionChoice('KR', value='4')],
                                     required=False,
                                     default='1'),
                      event: Option(int, "Event ID to check t10 info for",
                                    required=False,
                                    default=0,
                                    min_value=1,
                                    max_value=999)):
        await ctx.interaction.response.defer()
        server = int(server)
        try:
            if event == 0:
                event_id = await self.get_current_event_id(server)
            else:
                event_id = event

            songs_output = []
            song_ids = []
            song_api = await self.fetch_api('https://bestdori.com/api/songs/all.7.json')
            event_api = await self.fetch_api(f'https://bestdori.com/api/events/{event_id}.json')

            try:
                for x in event_api['musics'][0]:
                    song_ids.append(x['musicId'])
                fmt = "%Y-%m-%d %H:%M:%S %Z%z"
                now_time = datetime.datetime.now(timezone(-timedelta(hours=4), 'US/Eastern'))

                for song in song_ids:
                    i = 1
                    entries = []
                    song_name = song_api[str(song)]['musicTitle'][1]
                    if song_name is None:
                        song_name = song_api[str(song)]['musicTitle'][0]
                    output = '```'
                    output += "  Song:  " + song_name + "\n  Time:  " + now_time.strftime(fmt) + "\n\n"
                    api_url = f'https://bestdori.com/api/eventtop/data?server={server}&event={event_id}&mid={song}&latest=1'
                    t10_api = await self.fetch_api(api_url)

                    for points in t10_api['points']:
                        uid = points['uid']
                        for user in t10_api['users']:
                            if uid == user['uid']:
                                entries.append(
                                    [i, format_number(points['value']), user['rank'], user['uid'], string_check(user['name'])])
                                break
                        i += 1
                    output += tabulate(entries, tablefmt="plain", headers=["#", "Score", "Level", "ID", "Player"]) + "```"
                    songs_output.append(output)
            except KeyError:
                songs_output = "This event doesn't have any songs"
                pass
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching t10 data',
                                content=f'Failed to get song data for event with ID `{event_id} (Server ID {server})`.'),
                ephemeral=True)
            return
        output = ''.join(songs_output)
        await ctx.interaction.followup.send(output)

    @discord.slash_command(name='timeleft',
                           description='Provides the amount of time left (in hours) for an event.')
    async def timeleft(self,
                       ctx: discord.ApplicationContext,
                       server: Option(str, "Choose which server to check t10 data",
                                      choices=[OptionChoice('EN', value='1'),
                                               OptionChoice('JP', value='0'),
                                               OptionChoice('TW', value='2'),
                                               OptionChoice('CN', value='3'),
                                               OptionChoice('KR', value='4')],
                                      required=False,
                                      default='1')):
        await ctx.interaction.response.defer()
        server = int(server)
        try:
            event_id = await self.get_current_event_id(server)
            if event_id:
                current_time = time.time() * 1000
                event_api = await self.fetch_api(f'https://bestdori.com/api/events/{event_id}.json')
                if event_api['startAt'][server]:
                    event_name = event_api['eventName'][server]
                    banner_name = event_api['assetBundleName']

                    event_start = float(event_api['startAt'][server])
                    event_end = float(event_api['endAt'][server])
                    event_end_formatted = datetime.datetime.fromtimestamp(
                        float(event_api['endAt'][server]) / 1000).strftime("%Y-%m-%d %H:%M:%S %Z%z") + ' UTC'
                    time_left = float(event_api['endAt'][server]) - current_time

                    event_url = f'https://bestdori.com/info/events/{event_id}'
                    server_abbv = server_name(server)
                    thumbnail = f'https://bestdori.com/assets/{server_abbv}/event/{banner_name}/images_rip/logo.png'

                    event_attribute = event_api['attributes'][0]['attribute']
                    if event_attribute == 'powerful':
                        embed_color = 0x0ff345a
                    elif event_attribute == 'cool':
                        embed_color = 0x04057e3
                    elif event_attribute == 'pure':
                        embed_color = 0x044c527
                    else:
                        embed_color = 0x0ff6600

                    if float(event_api['startAt'][server]) < current_time < float(event_api['endAt'][server]):
                        event_active = True

                        if time_left < 0:
                            event_progress = '100'
                        else:
                            event_length = event_end - event_start
                            event_progress = round((((event_length - time_left) / event_length) * 100), 2)
                            if int(event_progress) < 0:
                                event_progress = '100'
                            else:
                                event_progress = str(event_progress)

                        time_left_seconds = time_left / 1000
                        if time_left_seconds < 0:
                            time_left_text = 'The event is completed.'
                        else:
                            days = str(int(time_left_seconds // 86400))
                            hours = str(int(time_left_seconds // 3600 % 24))
                            minutes = str(int(time_left_seconds // 60 % 60))
                            time_left_text = f'{days}d {hours}h {minutes}m'

                    else:
                        event_active = False
                        event_progress = "N/A"
                        time_to_event = event_start - current_time / 1000
                        days = str(int(time_to_event // 86400))
                        hours = str(int(time_to_event // 3600 % 24))
                        minutes = str(int(time_to_event // 60 % 60))
                        time_left_text = f'{days}d {hours}h {minutes}m'

                    embed = discord.Embed(title=event_name, url=event_url, color=embed_color)
                    embed.set_thumbnail(url=thumbnail)
                    embed.add_field(name='Time Left' if event_active else 'Begins In', value=time_left_text, inline=True)
                    embed.add_field(name='Progress', value=event_progress, inline=True)
                    embed.add_field(name='End Date', value=event_end_formatted, inline=True)
                    embed.set_footer(
                        text=f"\n\n\nFor more info, try /event \n{time.ctime()}")
                    await ctx.interaction.followup.send(embed=embed)
            else:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Event has not started yet.',
                                    content=f'There is currently no event happening at this time.'))
        except TypeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Missing details on next event',
                                content=f'Details for the next event have not been released yet.'))

def setup(bot):
    bot.add_cog(Event(bot))
