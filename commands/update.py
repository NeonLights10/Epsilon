import asyncio
import json
import os
import time
import datetime
from datetime import timezone, timedelta
from tabulate import tabulate

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

import discord
from discord.ext import commands, tasks
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


class Update(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncClient()
        self.client = CachingClient(self.client)
        self.oneh_synced = False
        self.twom_synced = False
        self.t10_2m_tracking.start()
        self.t10_1h_tracking.start()

    def cog_unload(self):
        self.t10_2m_tracking.cancel()

    async def fetch_api(self, url):
        api = await self.client.get(url)
        if api.status_code == 200:
            return api.json()
        else:
            return None

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

    @tasks.loop(seconds=120.0)
    async def t10_2m_tracking(self):
        if self.twom_synced:
            self.t10_2m_tracking.change_interval(minutes=2)
            self.twom_synced = False
        log.info('Sending 2 minute tracking')
        current_time = datetime.datetime.now(datetime.timezone.utc)
        if (current_time.minute % 2) != 0:
            log.info('Not 2 minutes, update interval')
            wait_time = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
            wait_time = wait_time.time()
            self.t10_2m_tracking.change_interval(time=wait_time)
            self.twom_synced = True

        for guild in self.bot.guilds:
            documents = db.tracking.find({"server_id": guild.id})
            async for server_document in documents:
                for channel in server_document['channels']:
                    server = int(channel['server'])
                    event_id = await self.get_current_event_id(server)
                    try:
                        api_url = f'https://bestdori.com/api/eventtop/data?server={server}&event={event_id}&mid=0&latest=1'
                        t10_api = await self.fetch_api(api_url)
                        if not t10_api:
                            return
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
                                        [i, format_number(points['value']), user['rank'], user['uid'],
                                         string_check(user['name'])])
                                    break
                            i += 1
                        output = ("```" + "  Time:  " + now_time.strftime(
                            fmt) + "\n  Event: " + event_name + "\n\n" + tabulate(
                            entries, tablefmt="plain", headers=["#", "Points", "Level", "ID", "Player"]) + "```")
                    except HTTPStatusError:
                        return

                    if channel['interval'] == '2m':
                        post_channel = guild.get_channel(int(channel['id']))
                        try:
                            await post_channel.send(output)
                        except discord.Forbidden:
                            log.error(f'Permission error while attempting to send t10 2m update to {guild.name}')
                            pass
                        except discord.HTTPException:
                            pass

    @tasks.loop(hours=1)
    async def t10_1h_tracking(self):
        if self.oneh_synced:
            self.t10_1h_tracking.change_interval(hours=1)
            self.oneh_synced = False
        log.info('Sending 2 minute tracking')
        current_time = datetime.datetime.now(datetime.timezone.utc)
        if current_time.minute != 0:
            log.info('Not 2 minutes, update interval')
            remainder = 60 - (current_time.minute % 60)
            wait_time = (current_time + timedelta(minutes=remainder)).replace(second=0, microsecond=0)
            wait_time = wait_time.time()
            self.t10_1h_tracking.change_interval(time=wait_time)
            self.oneh_synced = True

        for guild in self.bot.guilds:
            documents = db.tracking.find({"server_id": guild.id})
            async for server_document in documents:
                for channel in server_document['channels']:
                    server = int(channel['server'])
                    event_id = await self.get_current_event_id(server)
                    try:
                        api_url = f'https://bestdori.com/api/eventtop/data?server={server}&event={event_id}&mid=0&latest=1'
                        t10_api = await self.fetch_api(api_url)
                        if not t10_api:
                            return
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
                                        [i, format_number(points['value']), user['rank'], user['uid'],
                                         string_check(user['name'])])
                                    break
                            i += 1
                        output = ("```" + "  Time:  " + now_time.strftime(
                            fmt) + "\n  Event: " + event_name + "\n\n" + tabulate(
                            entries, tablefmt="plain", headers=["#", "Points", "Level", "ID", "Player"]) + "```")
                    except HTTPStatusError:
                        return

                    if channel['interval'] == '1h':
                        post_channel = guild.get_channel(int(channel['id']))
                        try:
                            await post_channel.send(output)
                        except discord.Forbidden:
                            log.error(f'Permission error while attempting to send t10 1h update to {guild.name}')
                            pass
                        except discord.HTTPException:
                            pass

    @t10_2m_tracking.before_loop
    @t10_1h_tracking.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()

    tracking = SlashCommandGroup('tracking', 't10 and cutoff tracking commands')
    t10_tracking = tracking.create_subgroup(name='t10', description='t10 tracking commands')
    cutoff_tracking = tracking.create_subgroup(name='cutoff', description='Cutoff tracking commands')

    @t10_tracking.command(name='enable',
                          description='Sets up t10 tracking in the channel the command is run in')
    @default_permissions(manage_messages=True)
    async def enable_t10_tracking(self,
                                  ctx: discord.ApplicationContext,
                                  interval: Option(str, "Interval to update tracking",
                                                   choices=[OptionChoice('2 minutes', value='2m'),
                                                            OptionChoice('1 hour', value='1h')],
                                                   required=True),
                                  server: Option(str, "Choose which server to check t10 data. Defaults to EN",
                                                 choices=[OptionChoice('EN', value='1'),
                                                          OptionChoice('JP', value='0'),
                                                          OptionChoice('TW', value='2'),
                                                          OptionChoice('CN', value='3'),
                                                          OptionChoice('KR', value='4')],
                                                 required=False,
                                                 default='1')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.tracking.find_one({"server_id": ctx.interaction.guild_id})
        if not document:
            post = {
                'server_id': ctx.interaction.guild_id,
                'channels': []
            }
            await db.tracking.insert_one(post)
            document = await db.tracking.find_one({"server_id": ctx.interaction.guild_id})
        channels = document['channels']
        match interval:
            case '2m':
                channels.append({'id': ctx.interaction.channel_id,
                                 'interval': '2m',
                                 'server': server})
                await db.tracking.update_one({"server_id": ctx.interaction.guild_id},
                                             {"$set": {'channels': channels}})
            case '1h':
                channels.append({'id': ctx.interaction.channel_id,
                                 'interval': '1h',
                                 'server': server})
                await db.tracking.update_one({"server_id": ctx.interaction.guild_id},
                                             {"$set": {'channels': channels}})

        server = server_name(server)
        await ctx.interaction.followup.send(embed=
                                            gen_embed(title='Configure t10 tracking',
                                                      content=f'{interval} t10 tracking has been enabled in'
                                                              f' {ctx.interaction.channel.mention} for the'
                                                              f' {server} server.'),
                                            ephemeral=True)

    @t10_tracking.command(name='disable',
                          description='Disables t10 tracking in the channel the command is run in')
    @default_permissions(manage_messages=True)
    async def disable_t10_tracking(self,
                                   ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.tracking.find_one({"server_id": ctx.interaction.guild_id})
        if document:
            channels = document['channels']
            channels = list(filter(lambda c: c['id'] != ctx.interaction.channel_id, channels))
            await db.tracking.update_one({"server_id": ctx.interaction.guild_id},
                                         {"$set": {'channels': channels}})
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Configure t10 tracking',
                                                          content=f't10 tracking has been disabled in'
                                                                  f' {ctx.interaction.channel.mention}'),
                                                ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Configure t10 tracking',
                                                          content='t10 tracking is not enabled for this channel!'),
                                                ephemeral=True)

    @cutoff_tracking.command(name='enable',
                             description='Enables cutoff tracking in the channel the command is run in')
    @default_permissions(manage_messages=True)
    async def enable_cutoff_tracking(self,
                                     ctx: discord.ApplicationContext,
                                     server: Option(str, "Choose which server to check cutoff data. Defaults to EN",
                                                    choices=[OptionChoice('EN', value='1'),
                                                             OptionChoice('JP', value='0'),
                                                             OptionChoice('TW', value='2'),
                                                             OptionChoice('CN', value='3'),
                                                             OptionChoice('KR', value='4')],
                                                    required=False,
                                                    default='1')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.ctracking.find_one({"server_id": ctx.interaction.guild_id})
        if not document:
            post = {
                'server_id': ctx.interaction.guild_id,
                'channels': []
            }
            document = await db.ctracking.insert_one(post)

        channels = document['channels']
        channels.append({'id': ctx.interaction.channel_id,
                         'server': server})
        await db.ctracking.update_one({"server_id": ctx.interaction.guild_id},
                                      {"$set": {'channels': channels}})

        await ctx.interaction.followup.send(embed=
                                            gen_embed(title='Configure cutoff tracking',
                                                      content=f'Cutoff tracking has been enabled in'
                                                              f' {ctx.interaction.channel.mention} for the'
                                                              f' {server_name(server)} server.'),
                                            ephemeral=True)

    @cutoff_tracking.command(name='disable',
                             description='Disables cutoff tracking in the channel the command is run in')
    @default_permissions(manage_messages=True)
    async def disable_cutoff_tracking(self,
                                      ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.ctracking.find_one({"server_id": ctx.interaction.guild_id})
        if document:
            channels = document['channels']
            channels = list(filter(lambda c: c['id'] != ctx.interaction.channel_id, channels))
            await db.ctracking.update_one({"server_id": ctx.interaction.guild_id},
                                          {"$set": {'channels': channels}})
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Configure cutoff tracking',
                                                          content=f'Cutoff tracking has been disabled in'
                                                                  f' {ctx.interaction.channel.mention}'),
                                                ephemeral=True)
        else:
            await ctx.interaction.followup.send(embed=
                                                gen_embed(title='Configure cutoff tracking',
                                                          content='Cutoff tracking is not enabled for this channel!'),
                                                ephemeral=True)


def setup(bot):
    bot.add_cog(Update(bot))
