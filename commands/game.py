import json
import os
import time
import math
import datetime
import uuid

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

from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageFont import truetype
from io import BytesIO
from os import path
from pathlib import Path

from formatting.embed import gen_embed
from __main__ import log, db


class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncClient()
        self.client = CachingClient(self.client)

    async def fetch_api(self, url):
        api = await self.client.get(url)
        return api.json()

    async def generate_band_and_titles_image(self, member_situations: list, equipped_title_ids: list, server: str):
        icon_paths = []
        for situation in member_situations:
            icon_path = ""
            if situation['illust'] == "after_training":
                icon_path = f"data/img/icons/full_icons/{situation['situationId']}_trained.png"
            else:
                icon_path = f"data/img/icons/full_icons/{situation['situationId']}.png"

            if path.exists(icon_path):
                icon_paths.append(icon_path)
            # TODO: use a placeholder "unknown card" image if the card icon doesn't exist

        images = [Image.open(x) for x in icon_paths]
        widths, heights = zip(*(i.size for i in images))
        total_width = sum(widths)
        max_height = max(heights) * 2
        new_im = Image.new('RGBA', (int(total_width), max_height))
        x_offset = 0
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]

        titles_api = await self.fetch_api('https://bestdori.com/api/degrees/all.3.json')
        server_id_map = {
            'jp': 0,
            'en': 1,
            'tw': 2,
            'cn': 3,
            'kr': 4
        }
        tier = ''
        if len(equipped_title_ids) == 2:
            x_offset = 0
            for title_id in equipped_title_ids:
                server_id = server_id_map[server]
                image_contents = []
                title_info = titles_api[str(title_id)]
                event_title = f"data/img/titles/{server}/{title_info['baseImageName'][server_id]}.png"
                image_contents.append(event_title)
                event = Image.open(image_contents[0])
                event = event.resize((368, 80), Image.ANTIALIAS)
                new_im.paste(event, (x_offset, 250), event)

                tier = title_info['rank'][server_id]
                if tier != 'none' and tier != 'normal' and tier != 'extra':
                    tier_title = f'data/img/titles/{server}/event_point_{tier}.png'
                    image_contents.append(tier_title)
                    tier = Image.open(image_contents[1])
                    tier = tier.resize((368, 80), Image.ANTIALIAS)
                    new_im.paste(tier, (x_offset, 250), tier)
                elif tier == 'normal' or tier == 'extra':
                    tier_title = f'data/img/titles/{server}/try_clear_{tier}.png'
                    image_contents.append(tier_title)
                    tier = Image.open(image_contents[1])
                    tier = tier.resize((368, 80), Image.ANTIALIAS)
                    new_im.paste(tier, (x_offset, 250), tier)
                x_offset += 525
        else:
            x_offset = 250
            image_contents = []
            title_info = titles_api[str(equipped_title_ids[0])]
            server_id = server_id_map[server]
            event_title = f"data/img/titles/{server}/{title_info['baseImageName'][server_id]}.png"
            image_contents.append(event_title)
            event = Image.open(image_contents[0])
            event = event.resize((368, 80), Image.ANTIALIAS)
            new_im.paste(event, (x_offset, 250), event)

            tier = title_info['rank'][server_id]
            if tier != 'none':
                tier_title = f'data/img/titles/{server}/event_point_{tier}.png'
                image_contents.append(tier_title)
                tier = Image.open(image_contents[1])
                tier = tier.resize((368, 80), Image.ANTIALIAS)
                new_im.paste(tier, (x_offset, 250), tier)

        file_name = f'{str(uuid.uuid4())}.png'
        saved_file_path = f'data/img/imgTmp/{file_name}'
        if not path.exists('data/img/imgTmp/'):
            filepath = Path('data/img/imgTmp/')
            filepath.mkdir(parents=True, exist_ok=True)
        new_im.save(saved_file_path)
        return file_name, saved_file_path

    game_commands = SlashCommandGroup('game', 'game info related commands')

    @game_commands.command(name='lookup',
                           description='Searches a player on the specified server by ID')
    async def game_lookup(self,
                          ctx: discord.ApplicationContext,
                          player_id: Option(int, "Player ID to lookup",
                                            required=True),
                          server: Option(str, "Choose which server to lookup the player ID on",
                                         choices=[OptionChoice('EN', value='en'),
                                                  OptionChoice('JP', value='jp'),
                                                  OptionChoice('TW', value='tw'),
                                                  OptionChoice('CN', value='cn'),
                                                  OptionChoice('KR', value='kr')],
                                         required=False,
                                         default='en')):
        await ctx.interaction.response.defer()
        try:
            player_api = await self.fetch_api(f'https://bestdori.com/api/player/{server}/{player_id}?mode=2')
            if not player_api['result']:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Error fetching player data',
                                    content=f'Failed to get data for player with ID `{player_id} (Server {server})`.'),
                    ephemeral=True)
                return

            profile = player_api['data']['profile']
            if profile is None:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='No player data',
                                    content=f'No data found for player with ID `{player_id} (Server {server})`.'))
                return
            embed = gen_embed(title=f"{profile['userName']} ({server.upper()}: {player_id})")
            embed.add_field(name='Description', value=profile['introduction'], inline=True)
            embed.add_field(name='Level', value=profile['rank'], inline=True)
            embed.add_field(name='\u200b', value='\u200b', inline=True)

            # Check if user has manually set their displayed card, otherwise use the band center
            if profile['userProfileSituation'].get('viewProfileSituationStatus') == "profile_situation":
                profile_situation = profile['userProfileSituation']
            else:
                profile_situation = profile['mainDeckUserSituations']['entries'][0]

            if profile_situation['illust'] == "after_training":
                profile_picture = f"{profile_situation['situationId']}_trained.png"
            else:
                profile_picture = f"{profile_situation['situationId']}.png"
            icon = discord.File(f"data/img/icons/base_icons/{profile_picture}", filename=f'{profile_picture}')

            # clear/fc/ap stats - default to 0 if no values
            song_stats = {
                'ex_clear': profile['clearedMusicCountMap'].get('entries', {}).get('expert', 0),
                'ex_fc': profile['fullComboMusicCountMap'].get('entries', {}).get('expert', 0),
                'ex_ap': profile['allPerfectMusicCountMap'].get('entries', {}).get('expert', 0),
                'sp_clear': profile['clearedMusicCountMap'].get('entries', {}).get('special', 0),
                'sp_fc': profile['fullComboMusicCountMap'].get('entries', {}).get('special', 0),
                'sp_ap': profile['allPerfectMusicCountMap'].get('entries', {}).get('special', 0)
            }

            embed.add_field(name='EX Cleared / FC / AP',
                            value=f"{song_stats['ex_clear']} / {song_stats['ex_fc']} / {song_stats['ex_ap']}",
                            inline=True)
            embed.add_field(name='SP Cleared / FC / AP',
                            value=f"{song_stats['sp_clear']} / {song_stats['sp_fc']} / {song_stats['sp_ap']}",
                            inline=True)

            # high score rating
            total_hsr = 0
            for band_hsr in profile['userHighScoreRating'].values():
                for song in band_hsr['entries']:
                    total_hsr += song['rating']
            embed.add_field(name='\u200b', value='\u200b', inline=True)
            embed.add_field(name='High Score Rating', value=total_hsr, inline=True)

            # display the player's equipped band and titles
            title_ids = []
            title_ids.append(profile['userProfileDegreeMap']['entries']['first']['degreeId'])
            if 'second' in profile['userProfileDegreeMap']['entries']:
                title_ids.append(profile['userProfileDegreeMap']['entries']['second']['degreeId'])

            band_members = []
            card_order = [3, 1, 0, 2, 4]
            for i in card_order:
                band_members.append(profile['mainDeckUserSituations']['entries'][i])
            band_name_and_path = await self.generate_band_and_titles_image(band_members, title_ids, server)
            band_image_file = discord.File(band_name_and_path[1], filename=band_name_and_path[0])

            embed.set_thumbnail(url=f"attachment://{profile_picture}")
            embed.set_image(url=f"attachment://{band_name_and_path[0]}")

            await ctx.interaction.followup.send(files=[icon, band_image_file], embed=embed)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching player data',
                                content=f'Failed to get data for player with ID `{player_id} (Server {server})`.'),
                ephemeral=True)
        except KeyError as e:
            print(e)
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching player data',
                                content=f'Failed to get data for player with ID `{player_id} (Server {server})`.'),
                ephemeral=True)


def setup(bot):
    bot.add_cog(Game(bot))
