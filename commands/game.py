import json
import os
import math
import datetime
import uuid
from time import strftime, gmtime, localtime
import time

import numpy as np
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

from datetime import timezone, timedelta
from tabulate import tabulate

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

import discord
from discord import File
from discord.ext import commands, pages
from discord.commands import Option, OptionChoice, SlashCommandGroup
from discord.commands.permissions import default_permissions

from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageFont import truetype
from io import BytesIO
from os import path
from pathlib import Path
from operator import itemgetter

from formatting.embed import gen_embed
from formatting.constants import SCHOOL_NAME_DICT
from __main__ import log, db


def find_rank(rank: int):
    xp_table = get_xp_table()
    if rank < 145:
        return xp_table[rank]
    else:
        n = rank - 145
        return xp_table[145] + 2560 * n * (n + 1) + n * 237730


def get_xp_table():
    xp_table = [0, 0, 10, 160, 1360, 2960, 4960, 7360, 10160, 13360, 16960, 20960, 25360, 30160, 35360, 40960, 46960,
                53280, 59920, 66880, 74160, 81760, 89680, 97920, 106480, 115360, 124560, 134080, 143920, 154080, 164560,
                175360, 186480, 197920, 209680, 221760, 234160, 246880, 259920, 273280, 286960, 300960, 315280, 329920,
                344880, 360160, 375760, 391680, 407920, 424480, 441360, 458560, 476080, 493920, 512080, 530560, 549360,
                568480, 587920, 607680, 627760, 648160, 668880, 689920, 711280, 732960, 754960, 777280, 799920, 822880,
                846160, 869760, 893680, 917920, 942480, 967360, 992560, 1018080, 1043920, 1070080, 1096560, 1123360,
                1150480, 1177920, 1205680, 1233760, 1262160, 1290880, 1319920, 1349280, 1378960, 1408960, 1439280,
                1469920, 1500880, 1532160, 1563760, 1595680, 1627920, 1660480, 1693360, 1728800, 1766800, 1807360,
                1850480, 1896160, 1945680, 1999040, 2056240, 2117280, 2182160, 2251520, 2325360, 2403680, 2486480,
                2573760, 2665840, 2762720, 2864400, 2970880, 3082160, 3198400, 3319600, 3445760, 3576880, 3712960,
                3854080, 4000240, 4151440, 4307680, 4468960, 4635320, 4806760, 4983280, 5164880, 5351560, 5543340,
                5740220, 5942200, 6149280, 6361460, 6578750, 6801150, 7028660, 7261280, 7499010]

    return xp_table


def get_xp_per_flame(flames_used: int):
    match flames_used:
        case 1:
            return 2500
        case 2:
            return 3000
        case 3:
            return 3500


def get_ep_per_flame(flames_used: int):
    match flames_used:
        case 0:
            return 1
        case 1:
            return 5
        case 2:
            return 10
        case _:
            return 15


def get_song_meta_rows(song_meta_api: dict, song_name_api: dict, song_id: str, fever: bool, song_name: str = "") -> list:
    output_rows = []

    song_length = song_name_api[song_id]['length']
    song_length = strftime("%H:%M:%S", gmtime(song_length))

    if "4" in song_meta_api[song_id]:
        song_values = song_meta_api[song_id]["4"]["7"]
        if fever:
            output_rows.append(
                [song_name + ' (SP)', round(((song_values[2] + song_values[3] * 2) * 1.1) * 100),
                 song_length])
        else:
            output_rows.append(
                [song_name + ' (SP)', round(((song_values[0] + song_values[1] * 2) * 1.1) * 100),
                 song_length])
    song_values = song_meta_api[song_id]["3"]["7"]
    if fever:
        output_rows.append(
            [song_name, round(((song_values[2] + song_values[3] * 2) * 1.1) * 100), song_length])
    else:
        output_rows.append(
            [song_name, round(((song_values[0] + song_values[1] * 2) * 1.1) * 100), song_length])

    return output_rows


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
                          id: Option(int, "Player ID to lookup",
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
            player_api = await self.fetch_api(f'https://bestdori.com/api/player/{server}/{id}?mode=2')
            if not player_api['result']:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Error fetching player data',
                                    content=f'Failed to get data for player with ID `{id} (Server {server})`.'),
                    ephemeral=True)
                return

            profile = player_api['data']['profile']
            if profile is None:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='No player data',
                                    content=f'No data found for player with ID `{id} (Server {server})`.'))
                return
            embed = gen_embed(title=f"{profile['userName']} ({server.upper()}: {id})")
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
                                content=f'Failed to get data for player with ID `{id} (Server {server})`.'),
                ephemeral=True)
        except KeyError as e:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content=f'Failed to process player data: Could not find key `{e.args[0]}`'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching player data',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)

    async def song_name_autocomplete(self, ctx: discord.ApplicationContext):
        song_list = await self.fetch_api('https://bestdori.com/api/songs/all.7.json')
        matches = []
        for x in range(0, 4):
            matches.extend([song_list[song_id]['musicTitle'][x] for song_id in song_list if
                            song_list[song_id]['musicTitle'][x] is not None and ctx.value.lower() in
                            song_list[song_id]['musicTitle'][x].lower()])
        return set(matches)

    @game_commands.command(name='songinfo',
                           description='Provides info about a song')
    async def song_info(self,
                        ctx: discord.ApplicationContext,
                        name: Option(str, "Song name to lookup", required=True, autocomplete=song_name_autocomplete)):
        await ctx.interaction.response.defer()
        try:
            song_id = ""
            song_api = await self.fetch_api("https://bestdori.com/api/songs/all.7.json")
            displayed_song_name = ""
            for key in song_api:
                element = song_api[key]['musicTitle'][1]
                if element is not None and element == name:
                    displayed_song_name = element
                    song_id = key
                    break
                else:
                    element = song_api[key]['musicTitle'][0]
                    if element is not None and element == name:
                        displayed_song_name = element
                        song_id = key
                        break

            if song_id not in song_api:
                await ctx.interaction.followup.send(
                    "Couldn't find the specified song.", ephemeral=True)
                return

            min_bpm = song_api[song_id]['bpm']['0'][0]['bpm']
            max_bpm = min_bpm
            for timingpoint in song_api[song_id]['bpm']['0']:
                if timingpoint['bpm'] < min_bpm:
                    min_bpm = timingpoint['bpm']
                if timingpoint['bpm'] > max_bpm:
                    max_bpm = timingpoint['bpm']
            if min_bpm != max_bpm:
                song_bpm = f"{min_bpm} - {max_bpm}"
            else:
                song_bpm = min_bpm

            song_levels_data = []
            for i in range(len(song_api[song_id]['difficulty'])):
                song_levels_data.append({
                    "level": song_api[song_id]['difficulty'][str(i)]['playLevel'],
                    "notes": song_api[song_id]['notes'][str(i)]
                })

            song_length_sec = int(song_api[song_id]['length'])
            m, s = divmod(song_length_sec, 60)
            song_length = ('{:02d}:{:02d}'.format(m, s))

            embed = gen_embed(title=f"{displayed_song_name} (ID: {song_id})")
            embed.add_field(name='BPM', value=song_bpm, inline=True)
            embed.add_field(name='Length', value=song_length, inline=True)
            embed.add_field(name='\u200b', value='\u200b', inline=True)

            diff_names = ["Easy", "Normal", "Hard", "Expert", "Special"]
            for i, data in enumerate(song_levels_data):
                embed.add_field(name=f"{diff_names[i]}",
                                value=f"Level: {data['level']}\nNotes: {data['notes']}",
                                inline=True)
            for i in range(6 - len(song_levels_data)):  # pad the remaining fields to align properly
                embed.add_field(name='\u200b', value='\u200b', inline=True)

            await ctx.interaction.followup.send(embed=embed)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching song list',
                                content='Could not get song list from Bestdori API.'),
                ephemeral=True)
        except KeyError as e:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content=f'Failed to process song data: Could not find key `{e.args[0]}`'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching song data',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)

    @game_commands.command(name='songmeta',
                           description='Show song meta info')
    async def song_meta(self,
                        ctx: discord.ApplicationContext,
                        fever: Option(bool, "Whether or not fever is enabled", required=False, default=True),
                        song: Option(str, "Song name to lookup", required=False, autocomplete=song_name_autocomplete)):
        await ctx.interaction.response.defer()
        try:
            song_name_api = await self.fetch_api('https://bestdori.com/api/songs/all.7.json')
            song_meta_api = await self.fetch_api('https://bestdori.com/api/songs/meta/all.5.json')
            song_weight_list = []
            song_id = ""
            name_server_order = (1, 0, 2, 3, 4)

            if song != "" and song is not None:
                # Get APIs

                # Find the IDs for the input
                # So 5.3.2 = [2.7628, 1.0763, 3.3251, 1.488]
                # Means that song (id = 5) on expert (difficulty = 3) on a 7 second skill (duration = 2 + 5) has those meta numbers.
                # First two = non fever, so if the skill is 60% then song score = 2.7628 + 1.0763 * 60%
                for x in song_name_api:
                    for i in name_server_order:
                        if song_name_api[x]['musicTitle'][i] is not None and song == song_name_api[x]['musicTitle'][i]:
                            song_id = x
                            break
                if song_id != "":
                    song_weight_list.extend(get_song_meta_rows(song_meta_api, song_name_api, song_id, fever, song))

            else:

                for x in song_meta_api:
                    song_name = ""
                    for i in name_server_order:
                        if song_name_api[x]['musicTitle'][i] is not None:
                            song_name = song_name_api[x]['musicTitle'][i]
                            break
                    if song_name != "":
                        song_weight_list.extend(get_song_meta_rows(song_meta_api, song_name_api, x, fever, song_name))

            if song_weight_list:
                song_weight_list = sorted(song_weight_list, key=itemgetter(1), reverse=True)
                song_weight_list = song_weight_list[:20]
                if fever:
                    title = "Song Meta (with Fever)"
                else:
                    title = "Song Meta (no Fever)"
                output = ("```" + tabulate(song_weight_list, tablefmt="plain",
                                                            headers=["Song", "Score %", "Length"]) + "```")
                await ctx.interaction.followup.send(
                    embed=gen_embed(title=title, content=output))
                return
            else:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title="Error", content="No songs found."))
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching song meta',
                                content='Could not get song meta list from Bestdori API.'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)
        except KeyError as e:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content=f'Failed to process song meta: Could not find key `{e.args[0]}`'),
                ephemeral=True)


    @game_commands.command(name='leaderboard',
                           description='View Bestdori leaderboards for various categories.')
    async def player_leaderboards(self,
                                  ctx: discord.ApplicationContext,
                                  server: Option(str, "Choose which server to check leaderboards on",
                                                 choices=[OptionChoice('EN', value='1'),
                                                          OptionChoice('JP', value='0'),
                                                          OptionChoice('TW', value='2'),
                                                          OptionChoice('CN', value='3'),
                                                          OptionChoice('KR', value='4')],
                                                 required=False,
                                                 default='1'),
                                  category: Option(str, "Choose the leaderboard category",
                                                   choices=[OptionChoice('High Score Rating', value='hsr'),
                                                            OptionChoice('Band Rating', value='dtr'),
                                                            OptionChoice('All Perfect', value='allPerfectCount'),
                                                            OptionChoice('Full Combo', value='fullComboCount'),
                                                            OptionChoice('Clears', value='cleared'),
                                                            OptionChoice('Player Rank', value='rank')],
                                                   required=False,
                                                   default='hsr'),
                                  entries: Option(int, "Number of entries to display",
                                                  required=False,
                                                  default=20,
                                                  min_value=1,
                                                  max_value=50)):
        await ctx.interaction.response.defer()
        try:
            lb_api = await self.fetch_api(
                f'https://bestdori.com/api/sync/list/player?server={server}&stats={category}&limit={entries}&offset=0')
            total_entries = min(entries, len(lb_api['rows']))
            category_names = {
                'hsr': 'High Score Rating',
                'dtr': 'Band Rating',
                'allPerfectCount': 'All Perfect Count',
                'fullComboCount': 'Full Combo Count',
                'cleared': 'Clear Count',
                'rank': 'Player Rank'
            }

            rows_per_page = 20
            output_pages = []
            curr_page_results = []
            for index, row in enumerate(lb_api['rows']):
                data = [str(index+1), row['user']['username'], row['stats']]
                if row['user']['username']:
                    data.append(row['user']['nickname'])
                curr_page_results.append(data)
                if ((index+1) >= rows_per_page and (index+1) % rows_per_page == 0) or (index == len(lb_api['rows']) - 1):
                    page_str = "```" + tabulate(curr_page_results, tablefmt="plain",
                                                 headers=["#", "Player", "Value", "Bestdori Name"]) + "```"
                    output_pages.append(gen_embed(title=f'Entries {(index // rows_per_page) * rows_per_page + 1} - {index+1} of {total_entries} for {category_names[category]}',
                                                  content=page_str))
                    curr_page_results = []

            paginator = pages.Paginator(pages=output_pages)
            await paginator.respond(ctx.interaction)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching leaderboard',
                                content='Could not get leaderboard data from Bestdori.'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)

    async def chara_name_autocomplete(self, ctx: discord.ApplicationContext):
        chara_api = await self.fetch_api('https://bestdori.com/api/characters/all.2.json')
        main_charas = [chara_api[chara_id] for chara_id in chara_api if 'bandId' in chara_api[chara_id]]
        names = [chara['characterName'] for chara in main_charas]
        nicknames = [chara['nickname'] for chara in main_charas]
        jp_name_match = [name[0] for name in names if name[0] is not None and ctx.value.lower() in name[0].lower()]
        en_name_match = [name[1] for name in names if name[1] is not None and ctx.value.lower() in name[1].lower()]
        jp_nick_match = [nick[0] for nick in nicknames if nick[0] is not None and ctx.value.lower() in nick[0].lower()]
        en_nick_match = [nick[1] for nick in nicknames if nick[1] is not None and ctx.value.lower() in nick[1].lower()]
        return set(en_name_match + en_nick_match + jp_name_match + jp_nick_match)

    @game_commands.command(name='character',
                           description='Posts character info.')
    async def chara_lookup(self,
                           ctx: discord.ApplicationContext,
                           character: Option(str, "Character Name", autocomplete=chara_name_autocomplete,
                                             required=True)):
        await ctx.interaction.response.defer()
        try:
            r = await self.fetch_api('https://bestdori.com/api/characters/all.2.json')
            chara_id = False
            for x in r:
                if chara_id:
                    break
                chara_name_data = [r[x]['characterName'], r[x]['nickname']]

                match chara_name_data:
                    case [[_, name, *_], _] if name == character:
                        chara_id = x
                    case [[name, *_], _] if name == character:
                        chara_id = x
                    case [_, [_, nick, *_]] if nick == character:
                        chara_id = x
                    case [_, [nick, *_]] if nick == character:
                        chara_id = x

            if not chara_id:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Error', content='Could not find character.'), ephemeral=True)
                return

            chara_api = await self.fetch_api(f'https://bestdori.com/api/characters/{int(chara_id)}.json')
            if 'profile' not in chara_api:
                await ctx.interaction.followup.send(
                    embed=gen_embed(title='Error', content='Character does not have a profile.'), ephemeral=True)
                return

            chara_names = chara_api['characterName'][1] + ' / ' + chara_api['characterName'][0]
            if chara_api['nickname'][1] is not None:
                chara_names = chara_names + f" ({chara_api['nickname'][1]})"

            try:
                chara_favfood = '**Favorite Food**: ' + chara_api['profile']['favoriteFood'][1]
                chara_seiyuu = '**Seiyuu**: ' + chara_api['profile']['characterVoice'][1]
                chara_hatedfood = '**Hated Food**: ' + chara_api['profile']['hatedFood'][1]
                chara_hobbies = '**Hobbies**: ' + chara_api['profile']['hobby'][1]
                chara_about = chara_api['profile']['selfIntroduction'][1]
                chara_school = chara_api['profile']['school'][1]
            except IndexError:
                chara_favfood = '**Favorite Food**: ' + chara_api['profile']['favoriteFood'][0]
                chara_seiyuu = '**Seiyuu**: ' + chara_api['profile']['characterVoice'][0]
                chara_hatedfood = '**Hated Food**: ' + chara_api['profile']['hatedFood'][0]
                chara_hobbies = '**Hobbies**: ' + chara_api['profile']['hobby'][0]
                chara_about = chara_api['profile']['selfIntroduction'][0]
                chara_school = chara_api['profile']['school'][0]

            for school_key in SCHOOL_NAME_DICT:
                if school_key in chara_school:
                    chara_school = SCHOOL_NAME_DICT[school_key]
                    break
            chara_school = '**School**: ' + chara_school

            chara_year_anime = '**Year (anime)**: ' + str(chara_api['profile']['schoolYear'][0])
            chara_position = '**Position**: ' + chara_api['profile']['part'].capitalize()
            if 'Guitar_vocal' in chara_position:
                chara_position = '**Position**: Guitarist + Vocals'
            chara_birthday_fmt = '**Birthday**: ' + strftime("%d %b %Y",
                                                             localtime(int(chara_api['profile']['birthday']) / 1000))
            chara_constellation = '**Constellation**: ' + chara_api['profile']['constellation'].capitalize()
            chara_height = '**Height**: ' + str(chara_api['profile']['height']) + "cm"
            chara_image_url = f'https://bestdori.com/res/icon/chara_icon_{chara_id}.png'
            chara_url = f'https://bestdori.com/info/characters/{chara_id}'

            chara_info = tabulate(
                [[chara_seiyuu], [chara_height], [chara_birthday_fmt], [chara_position], [chara_constellation]],
                tablefmt="plain")
            chara_interests = [chara_favfood, chara_hatedfood, chara_hobbies]
            chara_edu = [chara_school, chara_year_anime]

            embed = discord.Embed(title=chara_names, url=chara_url, description=chara_about)
            embed.set_thumbnail(url=chara_image_url)
            embed.add_field(name='About', value=chara_info, inline=True)
            embed.add_field(name='Interests', value='\n'.join(chara_interests), inline=True)
            embed.add_field(name='School', value='\n'.join(chara_edu), inline=True)
            await ctx.interaction.followup.send(embed=embed)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching character info',
                                content='Could not get data from Bestdori API.'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)
        except KeyError as e:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content=f'Could not find key `{e.args[0]}` in character data.'),
                ephemeral=True)

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

    async def get_event_time_left_sec(self, server: int, eventid: int):
        current_time = time.time() * 1000.0
        end_time = await self.get_event_end_time(server, eventid)
        time_left_sec = (float(end_time) - current_time) / 1000
        return time_left_sec

    async def get_event_end_time(self, server: int, eventid: int):
        api = await self.fetch_api(f'https://bestdori.com/api/events/{eventid}.json')
        end_time = api['endAt'][server]
        return float(end_time)

    @game_commands.command(name='staruse',
                           description='Provides star usage when aiming for a certain amount of EP.')
    async def staruse(self,
                      ctx: discord.ApplicationContext,
                      ep: Option(int, "EP gained per song", required=True),
                      current: Option(int, "Current event point total", min_value=0, required=True),
                      target: Option(int, "Target event point total", min_value=0, required=True),
                      flames: Option(int, "Flames used per game", choices=[1, 2, 3], required=True),
                      rank: Option(int, "Current player rank", min_value=1, max_value=500,
                                   required=True),
                      server: Option(str, "Server to get the current event's remaining time",
                                     choices=[OptionChoice('EN', value='1'),
                                              OptionChoice('JP', value='0'),
                                              OptionChoice('TW', value='2'),
                                              OptionChoice('CN', value='3'),
                                              OptionChoice('KR', value='4')],
                                     required=False,
                                     default='1'),
                      hours: Option(float,
                                    "Manually input remaining time in hours. Overrides time from 'server' argument.",
                                    required=False),
                      ):
        await ctx.interaction.response.defer()

        try:
            if rank > 500:
                ctx.interaction.followup.send(
                    embed=gen_embed(title="Error", content="Beginning rank can't be over 500."))
                return
            else:
                xp_per_flame = get_xp_per_flame(flames)
                # , timeleft: int = timeLeftInt('en')
                # songs played
                songs_played = (target - current) / ep

                # beg xp
                if rank != 500:
                    current_xp = find_rank(rank)

                    # xp gained + end xp
                    xp_gained = xp_per_flame * songs_played
                    ending_xp = current_xp + xp_gained
                    xp_table = get_xp_table()

                    if ending_xp > xp_table[-1]:
                        end_rank = 500
                    else:

                        for x in range(len(xp_table)):
                            if ending_xp < xp_table[x]:
                                end_rank = x - 1
                                break
                            elif ending_xp == xp_table[x]:
                                end_rank = x
                                break
                else:
                    end_rank = 500

                server_id = int(server)

                if hours is None:
                    event_id = await self.get_current_event_id(server_id)
                    hours = await self.get_event_time_left_sec(server_id, event_id) / 3600

                # rankups
                rank_up_amt = end_rank - rank
                if rank_up_amt <= 0:
                    rank_up_amt = 1

                # other stuff
                nat_flames = (32 * (int(hours) / 24))  # assuming 16 hours efficient
                pts_per_refill = ((ep / flames) * 10)
                pts_from_rankup = (rank_up_amt * ((ep / flames) * 10))
                pts_naturally = (ep / flames) * nat_flames

                # time spent
                time_spent = math.floor((songs_played * 150) / 3600)  # seconds
                if time_spent > hours:
                    time_spent_str = f'{time_spent} (Warning: event ends in {hours} hours)'
                else:
                    time_spent_str = str(time_spent)

                # gems used
                stars_used = ((((target - current) - pts_naturally - pts_from_rankup) / pts_per_refill) * 100)
                if stars_used < 0:
                    stars_used = 0
                else:
                    stars_used = math.ceil(stars_used / 100.00) * 100

                embed = gen_embed(title='Result')
                embed.add_field(name='Stars Used:', value=stars_used)
                embed.add_field(name='Beginning Rank', value=rank)
                embed.add_field(name='Ending Rank', value=end_rank)
                embed.add_field(name='Songs Played', value=songs_played)
                embed.add_field(name='Hours Spent (approx.)', value=time_spent)
                await ctx.interaction.followup.send(embed=embed)
        except HTTPStatusError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error fetching event data',
                                content='Could not get data from Bestdori API.'),
                ephemeral=True)
        except json.decoder.JSONDecodeError:
            await ctx.interaction.followup.send(
                embed=gen_embed(title='Error',
                                content='Could not decode response from Bestdori API.'),
                ephemeral=True)

    @game_commands.command(name='epgain',
                           description='Calculates EP gain for a single game.')
    async def epgain(self,
                     ctx: discord.ApplicationContext,
                     score: Option(int, "Individual score", min_value=0, required=True),
                     flames: Option(int, "Flames used per game", choices=[0, 1, 2, 3], required=True),
                     event: Option(int,
                                   "Event type (Note: Medley and Team Live calculations are not supported yet)",
                                   choices=[
                                       OptionChoice("Normal", value=1),
                                       OptionChoice("Live Goals", value=2),
                                       OptionChoice("Challenge Live", value=3),
                                       OptionChoice("VS Live", value=4)
                                   ],
                                   required=True),
                     bonus: Option(int,
                                   "Event bonus percentage, not including the base 100%. Used in events other than VS Live.",
                                   min_value=0,
                                   default=0,
                                   required=False),
                     total: Option(int,
                                   "Total room score in Multi Live. Used in events other than VS Live.",
                                   default=9000000,
                                   required=False),
                     ranking: Option(int, "VS Live multi rank placement (1-5)",
                                     min_value=1, max_value=5, default=1, required=False)
                     ):
        await ctx.interaction.response.defer()
        bp_percent_modifier = (bonus / 100) + 1

        ep_per_flame = get_ep_per_flame(flames)
        match event:
            case 1:
                event_scaling = 10000
                event_base = 50
            case 2:
                event_scaling = 13000
                event_base = 40
            case 3:
                event_scaling = 25000
                event_base = 20
            case 4:
                event_scaling = 550
                event_base = 1

        if event <= 3:
            ep = event_base
            team_score = total - score
            if score <= 1600000:
                ep += math.floor(score / event_scaling)
            else:
                ep += math.floor(1600000 / event_scaling)
                if score <= 1750000:
                    ep += math.floor((score - 1600000) / event_scaling / 2)
                else:
                    ep += math.floor((1750000 - 1600000) / event_scaling / 2)
                    if score <= 2000000:
                        ep += math.floor((score - 1750000) / event_scaling / 3)
                    else:
                        ep += math.floor((2000000 - 1750000) / event_scaling / 3)
                        ep += math.floor((score - 2000000) / event_scaling / 4)
            if team_score <= 6400000:
                ep += math.floor(team_score / event_scaling / 10)
            else:
                ep += math.floor(6400000 / event_scaling / 10)
                if team_score <= 7000000:
                    ep += math.floor((team_score - 6400000) / event_scaling / 10 / 2)
                else:
                    ep += math.floor((7000000 - 6400000) / event_scaling / 10 / 2)
                    if team_score <= 8000000:
                        ep += math.floor((team_score - 7000000) / event_scaling / 10 / 3)
                    else:
                        ep += math.floor((8000000 - 7000000) / event_scaling / 10 / 3)
                        ep += math.floor((team_score - 8000000) / event_scaling / 10 / 4)

            ep = (ep * bp_percent_modifier)
            ep *= ep_per_flame
        else:
            # bp calcs
            match ranking:
                case 1:
                    placement_bonus = 60
                case 2:
                    placement_bonus = 52
                case 3:
                    placement_bonus = 44
                case 4:
                    placement_bonus = 37
                case 5:
                    placement_bonus = 30
            ep = (placement_bonus + math.floor(score / 5500)) * ep_per_flame
        await ctx.interaction.followup.send(
            embed=gen_embed(title='Result', content=f'EP Gain: {math.floor(ep)}'))

    # @game_commands.command(name='card',
    #                        description='Provides embedded image of card with specified filters.')
    # async def card_lookup(self,
    #                       ctx: discord.ApplicationContext):
    #     await ctx.interaction.followup.send("Command not implemented.")


def setup(bot):
    bot.add_cog(Game(bot))
