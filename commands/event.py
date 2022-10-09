import json
import os
import time
import math
import datetime

import numpy as np
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

from datetime import timezone, timedelta
from tabulate import tabulate

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

import discord
from discord import File
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


def check_valid_server_tier(server, tier):
    server = server_name(server)
    valid_servers_by_tier = {
        50: ['en', 'cn'],
        100: ['en', 'jp', 'cn', 'tw', 'kr'],
        300: ['en', 'cn'],
        500: ['tw'],
        1000: ['en', 'jp', 'cn'],
        2000: ['jp', 'cn'],
        2500: ['en'],
        5000: ['jp'],
        10000: ['jp']
    }
    if server in valid_servers_by_tier[tier]:
        return True
    else:
        return False


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
        if event == 0:
            event_id = await self.get_current_event_id(server)
        else:
            event_id = event
        try:
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
                        entries.append(
                            [i, format_number(points['value']), user['rank'], user['uid'], string_check(user['name'])])
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
        if event == 0:
            event_id = await self.get_current_event_id(server)
        else:
            event_id = event
        try:
            songs_output = []
            song_ids = []
            song_api = await self.fetch_api('https://bestdori.com/api/songs/all.7.json')
            event_api = await self.fetch_api(f'https://bestdori.com/api/events/{event_id}.json')

            try:
                for x in event_api['musics'][0]:
                    song_ids.append(x['musicId'])
                fmt = "%Y-%m-%d %H:%M:%S %Z%z"
                now_time = datetime.datetime.now(timezone(-timedelta(hours=4), 'US/Eastern'))

                if event_api['eventType'] == "medley":
                    output = '```  Songs:  '
                    for index, song in enumerate(song_ids):
                        song_name = song_api[str(song)]['musicTitle'][1]
                        if song_name is None:
                            song_name = song_api[str(song)]['musicTitle'][0]
                        output += song_name
                        if index < len(song_ids) - 1:
                            output += " / "
                    output += "\n  Time:  " + now_time.strftime(fmt) + "\n\n"

                    api_url = f'https://bestdori.com/api/eventtop/data?server={server}&event={event_id}&mid=-1&latest=1'
                    t10_api = await self.fetch_api(api_url)

                    entries = []
                    i = 1
                    for points in t10_api['points']:
                        uid = points['uid']
                        for user in t10_api['users']:
                            if uid == user['uid']:
                                entries.append(
                                    [i, format_number(points['value']), user['rank'], user['uid'],
                                     string_check(user['name'])])
                                break
                        i += 1
                    output += tabulate(entries, tablefmt="plain",
                                       headers=["#", "Score", "Level", "ID", "Player"]) + "```"
                    songs_output.append(output)

                else:
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
                                        [i, format_number(points['value']), user['rank'], user['uid'],
                                         string_check(user['name'])])
                                    break
                            i += 1
                        output += tabulate(entries, tablefmt="plain",
                                           headers=["#", "Score", "Level", "ID", "Player"]) + "```"
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
                    embed.add_field(name='Time Left' if event_active else 'Begins In', value=time_left_text,
                                    inline=True)
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

    async def create_graph(self, server: int, tier: int, event_id: int,
                           ep_data: [],
                           time_data: [],
                           estimate_data: []):
        estimate_times = []
        estimate_values = []
        for entry in estimate_data:
            estimate_times.append(entry['time'])
            estimate_values.append(entry['estimate'])
        fig = go.Figure()
        config = {'displayModeBar': False}
        fig.add_trace(go.Scatter(x=time_data, y=ep_data, mode='lines+markers'))
        log.info(estimate_times)
        log.info(estimate_values)
        fig.add_trace(go.Scatter(x=estimate_times, y=estimate_values, mode='lines+markers'))
        fig.update_xaxes(range=[0, 100])
        fig.update_layout(
            xaxis=dict(
                title='Event Progress (%)',
                showline=True,
                showgrid=False,
                showticklabels=True,
                linecolor='rgb(204, 204, 204)',
                linewidth=2,
                ticks='outside',
                tickfont=dict(
                    family='Arial',
                    size=12,
                    color='rgb(82, 82, 82)',
                ),
            ),
            yaxis=dict(
                title='EP Values',
                showgrid=False,
                zeroline=False,
                showline=True,
                ticks='outside',
                tickfont=dict(
                    family='Arial',
                    size=12,
                    color='rgb(82, 82, 82)',
                ),

            ),
            autosize=False,
            margin=dict(
                autoexpand=False,
                l=100,
                r=20,
                t=110,
            ),
            showlegend=False,
            template='plotly_dark'
        )
        file_name = f"server{server}_{event_id}_t{tier}.png"
        saved_file = f"data/img/graphs/{file_name}"
        if not os.path.exists("data/img/graphs"):
            os.mkdir("data")
            os.mkdir("data/img")
            os.mkdir("data/img/graphs")

        fig.write_image(saved_file)

        image_file = File(saved_file, filename=file_name)
        return file_name, image_file

    async def calc_cutoff(self, server: int, event_id: int, tier: int):
        event_api = await self.fetch_api(f'https://bestdori.com/api/events/{event_id}.json')
        cutoff_api = await self.fetch_api(
            f'https://bestdori.com/api/tracker/data?server={server}&event={event_id}&tier={tier}')
        rates_api = await self.fetch_api(f'https://bestdori.com/api/tracker/rates.json')

        event_type = event_api['eventType']
        event_start = int(event_api['startAt'][server])
        event_end = int(event_api['endAt'][server])
        event_duration = event_end - event_start
        thp_check = event_start + 43200000  # twelve hours since event start check
        tfhp_check = thp_check + 43200000  # twenty-four hours since event start check
        end_freeze_check = event_end - 86400000  # freeze calc twenty-four hours before event end

        event_rate = None
        for rate in rates_api:
            if rate['type'] == event_type and rate['server'] == server and rate['tier'] == tier:
                event_rate = rate['rate']
        if not event_rate:
            event_rate = .01

        last_retrieved_cutoff = cutoff_api['cutoffs'][-1]['ep']
        all_time_data = []
        all_ep_data = []
        qualified_time_data = []
        qualified_ep_data = []
        estimate_data = []

        for entry in cutoff_api['cutoffs']:
            entry_time = int(entry['time'])
            time_difference = entry_time - event_start
            percent_into_event = time_difference / event_duration

            all_time_data.append(percent_into_event * 100)
            all_ep_data.append(entry['ep'])

            if thp_check <= entry_time <= end_freeze_check:
                qualified_time_data.append(percent_into_event)
                qualified_ep_data.append(entry['ep'])
            if tfhp_check <= entry_time <= end_freeze_check and len(qualified_ep_data) >= 5:
                x = np.array(qualified_time_data).reshape((-1, 1))
                y = np.array(qualified_ep_data)
                model = LinearRegression().fit(x, y)
                slope, intercept = model.coef_, model.intercept_
                estimate = (intercept + slope + (event_rate * slope))
                weights = [estimate * percent_into_event ** 2, percent_into_event ** 2]
                data_point = {
                    'estimate': estimate,
                    'slope': slope,
                    'intercept': intercept,
                    'weights': weights,
                    'time': percent_into_event
                }
                estimate_data.append(data_point)
            if entry_time >= end_freeze_check:
                # Calculate last estimate using a different weight
                try:
                    variables = estimate_data[-1]
                    intercept = variables['intercept']
                    slope = variables['slope']
                    estimate = (intercept + slope + (event_rate * slope))
                except IndexError:
                    estimate = 0
                    intercept = 0  # not sure if this is good assumption
                    slope = 0

                weights = [estimate * percent_into_event ** 2, percent_into_event ** 2]
                data_point = {
                    'estimate': estimate,
                    'slope': slope,
                    'intercept': intercept,
                    'weights': weights,
                    'time': percent_into_event
                }
                estimate_data.append(data_point)

        total_weight = 0
        total_time = 0
        for entry in estimate_data:
            total_weight += entry['weights'][0]
            total_time += entry['weights'][1]

        if estimate_data:
            non_smoothed_estimate = int(estimate_data[-1]['estimate'])
            try:
                smoothed_estimate = math.floor(total_weight / total_time)
            except ZeroDivisionError:
                smoothed_estimate = 0
        else:
            non_smoothed_estimate = 0
            smoothed_estimate = 0

        last_updated_time = cutoff_api['cutoffs'][-1]['time']
        elapsed_hours = (last_updated_time - event_start) / 1000 / 3600
        ep_per_hour = math.floor(last_retrieved_cutoff / elapsed_hours)

        cutoff_estimate = {
            'smoothed_estimate': smoothed_estimate,
            'non_smoothed_estimate': non_smoothed_estimate,
            'ep_per_hour': ep_per_hour,
            'estimate_data': estimate_data,
            'all_time_data': all_time_data,
            'all_ep_data': all_ep_data,
        }
        return cutoff_estimate

    async def get_cutoff(self, server: int, tier: int, graph: bool):
        event_id = await self.get_current_event_id(server)
        cutoff_api = await self.fetch_api(
            f'https://bestdori.com/api/tracker/data?server={server}&event={event_id}&tier={tier}')
        event_api = await self.fetch_api(f'https://bestdori.com/api/events/{event_id}.json')

        event_name = event_api['eventName'][server]
        banner_name = event_api['assetBundleName']
        event_start = event_api['startAt'][server]
        event_end = event_api['endAt'][server]
        event_url = f'https://bestdori.com/info/events/{event_id}'
        server_abbv = server_name(server)
        thumbnail = f'https://bestdori.com/assets/{server_abbv}/event/{banner_name}/images_rip/logo.png'

        if (time.time() * 1000) < float(event_start):
            embed = discord.Embed(title=event_name, url=event_url, colour=0x1abc9c)
            embed.set_thumbnail(url=thumbnail)
            embed.add_field(name='Event has not started.',
                            value=f'The event will start in <t:{event_start / 1000}:R>',
                            inline=True)

        latest_retrieved_cutoff = cutoff_api['cutoffs'][-1]['ep']
        latest_retrieved_time = cutoff_api['cutoffs'][-1]['time'] / 1000

        current_time = time.time()
        update_interval = current_time - float(latest_retrieved_time)
        days = str(int(update_interval // 86400))
        hours = str(int(update_interval // 3600 % 24))
        minutes = str(int(update_interval // 60 % 60))
        last_updated_text = f'{days}d {hours}h {minutes}m ago'

        latest_stored_cutoff = await db.eventdata.find_one({"server": server,
                                                            "event_id": event_id,
                                                            'tier': tier})

        if latest_stored_cutoff:
            cutoff = latest_stored_cutoff['cutoff_data'][-1]['current_ep']
            s_estimate = latest_stored_cutoff['cutoff_data'][-1]['smoothed_estimate']
            ns_estimate = latest_stored_cutoff['cutoff_data'][-1]['non_smoothed_estimate']
            ep_per_hour = latest_stored_cutoff['cutoff_data'][-1]['ep_per_hour']

            if latest_retrieved_cutoff == latest_stored_cutoff['cutoff_data'][-1]['current_ep']:
                # Data is the same, skip updating and use latest stored
                # Check if we have previous data - if so, we can calulate difference
                if len(latest_stored_cutoff['cutoff_data']) >= 2:
                    previous_cutoff = latest_stored_cutoff['cutoff_data'][-2]['current_ep']
                    previous_s_estimate = latest_stored_cutoff['cutoff_data'][-2]['smoothed_estimate']
                    previous_ns_estimate = latest_stored_cutoff['cutoff_data'][-2]['non_smoothed_estimate']
                    previous_ep_per_hour = latest_stored_cutoff['cutoff_data'][-2]['ep_per_hour']

                    log.info(s_estimate)
                    log.info(previous_s_estimate)
                    cutoff_difference = cutoff - previous_cutoff
                    s_estimate_difference = s_estimate - previous_s_estimate
                    ns_estimate_difference = ns_estimate - previous_ns_estimate
                    ep_per_hour_difference = ep_per_hour - previous_ep_per_hour

                    if cutoff_difference > 0:
                        cutoff_difference = "{:+,}".format(cutoff_difference)
                    else:
                        cutoff_difference = "{:,}".format(cutoff_difference)

                    if s_estimate_difference > 0:
                        s_estimate_difference = "{:+,}".format(s_estimate_difference)
                    else:
                        s_estimate_difference = "{:,}".format(s_estimate_difference)

                    if ns_estimate_difference > 0:
                        ns_estimate_difference = "{:+,}".format(ns_estimate_difference)
                    else:
                        ns_estimate_difference = "{:,}".format(ns_estimate_difference)

                    if ep_per_hour_difference > 0:
                        ep_per_hour_difference = "{:+,}".format(ep_per_hour_difference)
                    else:
                        ep_per_hour_difference = "{:,}".format(ep_per_hour_difference)

                    cutoff = "{:,}".format(cutoff) + f' ({cutoff_difference})'
                    s_estimate = "{:,}".format(s_estimate) + f' ({s_estimate_difference})'
                    ns_estimate = "{:,}".format(ns_estimate) + f' ({ns_estimate_difference})'
                    ep_per_hour = "{:,}".format(ep_per_hour) + f' ({ep_per_hour_difference})'

                else:
                    cutoff = "{:,}".format(cutoff)
                    s_estimate = "{:,}".format(s_estimate)
                    ns_estimate = "{:,}".format(ns_estimate)
                    ep_per_hour = "{:,}".format(ep_per_hour)

                if graph:
                    graph_info = []
                    file_name = f"server{server}_{event_id}_t{tier}.png"
                    saved_file = f"data/img/graphs/{file_name}"
                    if os.path.exists(saved_file):
                        graph_file = File(saved_file, filename=file_name)
                        graph_info.append(file_name)
                        graph_info.append(graph_file)
                    else:
                        estimate = await self.calc_cutoff(server, event_id, tier)
                        graph_info = await self.create_graph(server, event_id, tier,
                                                             estimate['all_ep_data'],
                                                             estimate['all_time_data'],
                                                             estimate['estimate_data'])
            else:
                # Data is not the same, udpate DB and calculate values
                cutoff_difference = latest_retrieved_cutoff - cutoff
                estimate = await self.calc_cutoff(server, event_id, tier)
                entry = {
                    'current_ep': latest_retrieved_cutoff,
                    'smoothed_estimate': estimate['smoothed_estimate'],
                    'non_smoothed_estimate': estimate['non_smoothed_estimate'],
                    'ep_per_hour': estimate['ep_per_hour']
                }

                cutoff_data = latest_stored_cutoff['cutoff_data']
                cutoff_data.append(entry)
                await db.eventdata.update_one({"server": server, "event_id": event_id, 'tier': tier},
                                              {"$set": {'cutoff_data': cutoff_data}})

                s_estimate_difference = estimate['smoothed_estimate'] - s_estimate
                ns_estimate_difference = estimate['non_smoothed_estimate'] - ns_estimate
                ep_per_hour_difference = estimate['ep_per_hour'] - ep_per_hour

                if cutoff_difference > 0:
                    cutoff_difference = "{:+,}".format(cutoff_difference)
                else:
                    cutoff_difference = "{:,}".format(cutoff_difference)

                if s_estimate_difference > 0:
                    s_estimate_difference = "{:+,}".format(s_estimate_difference)
                else:
                    s_estimate_difference = "{:,}".format(s_estimate_difference)

                if ns_estimate_difference > 0:
                    ns_estimate_difference = "{:+,}".format(ns_estimate_difference)
                else:
                    ns_estimate_difference = "{:,}".format(ns_estimate_difference)

                if ep_per_hour_difference > 0:
                    ep_per_hour_difference = "{:+,}".format(ep_per_hour_difference)
                else:
                    ep_per_hour_difference = "{:,}".format(ep_per_hour_difference)

                cutoff = "{:,}".format(cutoff) + f' ({cutoff_difference})'
                s_estimate = "{:,}".format(s_estimate) + f' ({s_estimate_difference})'
                ns_estimate = "{:,}".format(ns_estimate) + f' ({ns_estimate_difference})'
                ep_per_hour = "{:,}".format(ep_per_hour) + f' ({ep_per_hour_difference})'

                # Update graph regardless of user request
                graph_info = await self.create_graph(server, event_id, tier,
                                                     estimate['all_ep_data'],
                                                     estimate['all_time_data'],
                                                     estimate['estimate_data'])
        else:
            # No data stored, just go ahead and calculate estimates
            estimate = await self.calc_cutoff(server, event_id, tier)
            entry = {
                'current_ep': latest_retrieved_cutoff,
                'smoothed_estimate': estimate['smoothed_estimate'],
                'non_smoothed_estimate': estimate['non_smoothed_estimate'],
                'ep_per_hour': estimate['ep_per_hour']
            }
            # log.info(entry)
            cutoff_data = [entry]
            post = {
                'server': server,
                'event_id': event_id,
                'tier': tier,
                'cutoff_data': cutoff_data
            }
            await db.eventdata.insert_one(post)

            cutoff = "{:,}".format(latest_retrieved_cutoff)
            s_estimate = "{:,}".format(estimate['smoothed_estimate'])
            ns_estimate = "{:,}".format(estimate['non_smoothed_estimate'])
            ep_per_hour = "{:,}".format(estimate['ep_per_hour'])

            if graph:
                graph_info = await self.create_graph(server, event_id, tier,
                                                     estimate['all_ep_data'],
                                                     estimate['all_time_data'],
                                                     estimate['estimate_data'])

        current_time = time.time() * 1000
        time_left = (float(event_end) - current_time)
        if time_left < 0:
            time_left_text = 'The event is completed.'
            event_progress = '100'
        else:
            time_left_seconds = time_left / 1000
            days = str(int(time_left_seconds // 86400))
            hours = str(int(time_left_seconds // 3600 % 24))
            minutes = str(int(time_left_seconds // 60 % 60))
            time_left_text = f'{days}d {hours}h {minutes}m'

            event_length = float(event_end) - float(event_start)
            event_progress = round((((event_length - time_left) / event_length) * 100), 2)
            if int(event_progress) < 0:
                event_progress = '100%'
            else:
                event_progress = str(event_progress) + '%'

        if s_estimate == "0":
            s_estimate = '?'
            ns_estimate = '?'

        embed = discord.Embed(title=event_name, url=event_url, colour=0x1abc9c)
        embed.set_thumbnail(url=thumbnail)
        embed.add_field(name='Current', value=cutoff, inline=True)
        embed.add_field(name='EP/Hour', value=ep_per_hour, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.add_field(name='Estimate', value=s_estimate, inline=True)
        embed.add_field(name='Estimate (No Smoothing)', value=ns_estimate, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)
        embed.add_field(name='Last Updated', value=last_updated_text, inline=True)
        embed.add_field(name='Time Left', value=time_left_text, inline=True)
        embed.add_field(name='Progress', value=event_progress, inline=True)
        if graph:
            embed.set_image(url=f"attachment://{graph_info[0]}")
            embed.set_footer(text=f'{time.ctime()}')
            image_file = graph_info[1]
            return embed, image_file
        else:
            embed.set_footer(text=f'Want a graph? Try this command with the graph parameter.\n{time.ctime()}')

        return embed

    @discord.slash_command(name='t50',
                           description='Cutoff estimate for t100')
    async def t50_cutoff(self,
                         ctx: discord.ApplicationContext,
                         server: Option(str, "Choose which server to check t50 data",
                                        choices=[OptionChoice('EN', value='1'),
                                                 OptionChoice('JP', value='0'),
                                                 OptionChoice('TW', value='2'),
                                                 OptionChoice('CN', value='3'),
                                                 OptionChoice('KR', value='4')],
                                        required=False,
                                        default='1'),
                         graph: Option(str, "Do you want to show a graph of the cutoff estimate?",
                                       choices=[OptionChoice('Show graph', value='1'),
                                                OptionChoice('Do not show graph', value='0')],
                                       required=False,
                                       default='0')):
        await ctx.interaction.response.defer()
        server = int(server)
        if check_valid_server_tier(server, 50):
            if graph == '1':
                embed = await self.get_cutoff(server, 50, True)
                await ctx.interaction.followup.send(file=embed[1], embed=embed[0])
            else:
                embed = await self.get_cutoff(server, 50, False)
                await ctx.interaction.followup.send(embed=embed)
        else:
            valid_servers = ['en', 'cn']
            vs_text = ', '.join(valid_servers[:-1]) + ', and ' + valid_servers[-1]
            await ctx.interaction.followup.send(embed=gen_embed(title='Cannot Retrieve Cutoff',
                                                                content=f't50 cutoff is only valid for {vs_text}.'))

    @discord.slash_command(name='t100',
                           description='Cutoff estimate for t100')
    async def t100_cutoff(self,
                          ctx: discord.ApplicationContext,
                          server: Option(str, "Choose which server to check t100 data",
                                         choices=[OptionChoice('EN', value='1'),
                                                  OptionChoice('JP', value='0'),
                                                  OptionChoice('TW', value='2'),
                                                  OptionChoice('CN', value='3'),
                                                  OptionChoice('KR', value='4')],
                                         required=False,
                                         default='1'),
                          graph: Option(str, "Do you want to show a graph of the cutoff estimate?",
                                        choices=[OptionChoice('Show graph', value='1'),
                                                 OptionChoice('Do not show graph', value='0')],
                                        required=False,
                                        default='0')):
        await ctx.interaction.response.defer()
        server = int(server)
        if check_valid_server_tier(server, 100):
            if graph == '1':
                embed = await self.get_cutoff(server, 100, True)
                await ctx.interaction.followup.send(file=embed[1], embed=embed[0])
            else:
                embed = await self.get_cutoff(server, 100, False)
                await ctx.interaction.followup.send(embed=embed)
        else:
            valid_servers = ['en', 'jp', 'cn', 'tw', 'kr']
            vs_text = ', '.join(valid_servers[:-1]) + ', and ' + valid_servers[-1]
            await ctx.interaction.followup.send(embed=gen_embed(title='Cannot Retrieve Cutoff',
                                                                content=f't100 cutoff is only valid for {vs_text}.'))

    @discord.slash_command(name='t300',
                           description='Cutoff estimate for t300')
    async def t300_cutoff(self,
                          ctx: discord.ApplicationContext,
                          server: Option(str, "Choose which server to check t300 cutoff data",
                                         choices=[OptionChoice('EN', value='1'),
                                                  OptionChoice('JP', value='0'),
                                                  OptionChoice('TW', value='2'),
                                                  OptionChoice('CN', value='3'),
                                                  OptionChoice('KR', value='4')],
                                         required=False,
                                         default='1'),
                          graph: Option(str, "Do you want to show a graph of the cutoff estimate?",
                                        choices=[OptionChoice('Show graph', value='1'),
                                                 OptionChoice('Do not show graph', value='0')],
                                        required=False,
                                        default='0')):
        await ctx.interaction.response.defer()
        server = int(server)
        if check_valid_server_tier(server, 300):
            if graph == '1':
                embed = await self.get_cutoff(server, 300, True)
                await ctx.interaction.followup.send(file=embed[1], embed=embed[0])
            else:
                embed = await self.get_cutoff(server, 300, False)
                await ctx.interaction.followup.send(embed=embed)
        else:
            valid_servers = ['en', 'cn']
            vs_text = ', '.join(valid_servers[:-1]) + ', and ' + valid_servers[-1]
            await ctx.interaction.followup.send(embed=gen_embed(title='Cannot Retrieve Cutoff',
                                                                content=f't300 cutoff is only valid for {vs_text}.'))

    @discord.slash_command(name='t1000',
                           description='Cutoff estimate for t1000')
    async def t1000_cutoff(self,
                           ctx: discord.ApplicationContext,
                           server: Option(str, "Choose which server to check t1000 cutoff data",
                                          choices=[OptionChoice('EN', value='1'),
                                                   OptionChoice('JP', value='0'),
                                                   OptionChoice('TW', value='2'),
                                                   OptionChoice('CN', value='3'),
                                                   OptionChoice('KR', value='4')],
                                          required=False,
                                          default='1'),
                           graph: Option(str, "Do you want to show a graph of the cutoff estimate?",
                                         choices=[OptionChoice('Show graph', value='1'),
                                                  OptionChoice('Do not show graph', value='0')],
                                         required=False,
                                         default='0')):
        await ctx.interaction.response.defer()
        server = int(server)
        if check_valid_server_tier(server, 1000):
            if graph == '1':
                embed = await self.get_cutoff(server, 1000, True)
                await ctx.interaction.followup.send(file=embed[1], embed=embed[0])
            else:
                embed = await self.get_cutoff(server, 1000, False)
                await ctx.interaction.followup.send(embed=embed)
        else:
            valid_servers = ['en', 'jp', 'cn']
            vs_text = ', '.join(valid_servers[:-1]) + ', and ' + valid_servers[-1]
            await ctx.interaction.followup.send(embed=gen_embed(title='Cannot Retrieve Cutoff',
                                                                content=f't1000 cutoff is only valid for {vs_text}.'))

    @discord.slash_command(name='t2500',
                           description='Cutoff estimate for t2500')
    async def t2500_cutoff(self,
                           ctx: discord.ApplicationContext,
                           server: Option(str, "Choose which server to check t2500 cutoff data",
                                          choices=[OptionChoice('EN', value='1'),
                                                   OptionChoice('JP', value='0'),
                                                   OptionChoice('TW', value='2'),
                                                   OptionChoice('CN', value='3'),
                                                   OptionChoice('KR', value='4')],
                                          required=False,
                                          default='1'),
                           graph: Option(str, "Do you want to show a graph of the cutoff estimate?",
                                         choices=[OptionChoice('Show graph', value='1'),
                                                  OptionChoice('Do not show graph', value='0')],
                                         required=False,
                                         default='0')):
        await ctx.interaction.response.defer()
        server = int(server)
        if check_valid_server_tier(server, 2500):
            if graph == '1':
                embed = await self.get_cutoff(server, 2500, True)
                await ctx.interaction.followup.send(file=embed[1], embed=embed[0])
            else:
                embed = await self.get_cutoff(server, 2500, False)
                await ctx.interaction.followup.send(embed=embed)
        else:
            valid_servers = ['en', 'jp', 'cn']
            vs_text = ', '.join(valid_servers[:-1]) + ', and ' + valid_servers[-1]
            await ctx.interaction.followup.send(embed=gen_embed(title='Cannot Retrieve Cutoff',
                                                                content=f't2500 cutoff is only valid for {vs_text}.'))

def setup(bot):
    bot.add_cog(Event(bot))
