import json
import os
import math
import datetime
import uuid
from time import strftime, gmtime

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
from operator import itemgetter

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

    @game_commands.command(name='songinfo',
                           description='Provides info about a song')
    async def song_info(self,
                        ctx: discord.ApplicationContext,
                        song_name: Option(str, "Song name to lookup", required=True)):
        await ctx.interaction.response.defer()
        try:
            song_id = ""
            song_api = await self.fetch_api("https://bestdori.com/api/songs/all.7.json")
            displayed_song_name = ""
            # TODO: optimize this, or maybe search for incomplete matches if there is no exact match
            for key in song_api:
                element = song_api[key]['musicTitle'][1]
                if element is None:
                    element = song_api[key]['musicTitle'][0]
                displayed_song_name = element
                if element == 'R・I・O・T':
                    element = 'Riot'
                if element == 'KIZUNA MUSIC♪':
                    element = 'KIZUNA MUSIC'
                if element == song_name or element.lower() == song_name:
                    song_id = key
                    break

            if song_id not in song_api:
                await ctx.interaction.followup.send(
                    "Couldn't find the song entered, it was possibly entered incorrectly. The song needs to be spelled exactly as it appears in game.",
                    ephemeral=True
                )
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
            await ctx.interaction.followup.send("There was an error fetching the song list from Bestdori.",
                                                ephemeral=True)
        except KeyError:
            await ctx.interaction.followup.send("Failed to process song data",
                                                ephemeral=True)

    async def get_song_meta_output(self, fever: bool, songs: tuple = []):
        song_name_api = await self.fetch_api('https://bestdori.com/api/songs/all.7.json')
        song_meta_api = await self.fetch_api('https://bestdori.com/api/songs/meta/all.5.json')
        song_weight_list = []
        added_songs = []

        if songs:
            # Get APIs

            # Find the IDs for the input
            # So 5.3.2 = [2.7628, 1.0763, 3.3251, 1.488]
            # Means that song (id = 5) on expert (difficulty = 3) on a 7 second skill (duration = 2 + 5) has those meta numbers.
            # First two = non fever, so if the skill is 60% then song score = 2.7628 + 1.0763 * 60%
            for song in songs:
                for x in song_name_api:
                    try:
                        if song.lower() in (song_name_api[x]['musicTitle'][1]).lower():
                            added_songs.append([song_name_api[x]['musicTitle'][1], x])
                            break
                    except:
                        if song.lower() in (song_name_api[x]['musicTitle'][0]).lower():
                            added_songs.append([song_name_api[x]['musicTitle'][0], x])
                            break
            if added_songs:
                for song in added_songs:
                    if "4" in song_meta_api[song[1]]:
                        song_values = song_meta_api[song[1]]["4"]["7"]
                        song_length = song_name_api[song[1]]['length']
                        song_length = strftime("%H:%M:%S", gmtime(song_length))
                        if fever:
                            song_weight_list.append(
                                [song[0] + '(SP)', round(((song_values[2] + song_values[3] * 2) * 1.1) * 100),
                                 song_length])
                        else:
                            song_weight_list.append(
                                [song[0] + '(SP)', round(((song_values[0] + song_values[1] * 2) * 1.1) * 100),
                                 song_length])
                    song_values = song_meta_api[song[1]]["3"]["7"]
                    song_length = song_name_api[song[1]]['length']
                    song_length = strftime("%H:%M:%S", gmtime(song_length))
                    if fever:
                        song_weight_list.append(
                            [song[0], round(((song_values[2] + song_values[3] * 2) * 1.1) * 100), song_length])
                    else:
                        song_weight_list.append(
                            [song[0], round(((song_values[0] + song_values[1] * 2) * 1.1) * 100), song_length])

            # TODO: use a set for song_weight_list to avoid duplicate rows (which may happen with multiple search terms)
            if song_weight_list:
                song_weight_list = sorted(song_weight_list, key=itemgetter(1), reverse=True)

            if fever:
                title = "Song Meta (with Fever)"
            else:
                title = "Song Meta (no Fever)"
            output = ("```" + title + "\n\n" + tabulate(song_weight_list, tablefmt="plain",
                                                        headers=["Song", "Score %", "Length"]) + "```")
        else:
            for x in song_meta_api:
                if "4" in song_meta_api[x]:
                    song_values = song_meta_api[x]["4"]["7"]
                    try:
                        if song_name_api[x]['musicTitle'][1] is not None:
                            song_name = song_name_api[x]['musicTitle'][1]
                        else:
                            song_name = song_name_api[x]['musicTitle'][0]
                    except KeyError:
                        song_name = song_name_api[x]['musicTitle'][0]
                    song_length = song_name_api[x]['length']
                    song_length = strftime("%H:%M:%S", gmtime(song_length))
                    if fever:
                        song_weight_list.append(
                            [song_name + '(SP)', round(((song_values[2] + song_values[3] * 2) * 1.1) * 100),
                             song_length])
                    else:
                        song_weight_list.append(
                            [song_name + '(SP)', round(((song_values[0] + song_values[1] * 2) * 1.1) * 100),
                             song_length])
                song_values = song_meta_api[x]["3"]["7"]
                try:
                    if song_name_api[x]['musicTitle'][1] is not None:
                        song_name = song_name_api[x]['musicTitle'][1]
                    else:
                        song_name = song_name_api[x]['musicTitle'][0]
                except KeyError:
                    song_name = song_name_api[x]['musicTitle'][0]
                song_length = song_name_api[x]['length']
                song_length = strftime("%H:%M:%S", gmtime(song_length))
                if fever:
                    song_weight_list.append(
                        [song_name, round(((song_values[2] + song_values[3] * 2) * 1.1) * 100), song_length])
                else:
                    song_weight_list.append(
                        [song_name, round(((song_values[0] + song_values[1] * 2) * 1.1) * 100), song_length])
            if song_weight_list:
                song_weight_list = sorted(song_weight_list, key=itemgetter(1), reverse=True)
                song_weight_list = song_weight_list[:20]
                if fever:
                    title = "Song Meta (with Fever)"
                else:
                    title = "Song Meta (no Fever)"
                output = ("```" + title + "\n\n" + tabulate(song_weight_list, tablefmt="plain",
                                                            headers=["Song", "Score %", "Length"]) + "```")
        return output

    @game_commands.command(name='songmeta',
                           description='Show song meta info')
    async def song_meta(self,
                        ctx: discord.ApplicationContext,
                        fever: Option(bool, "Whether or not fever is enabled", required=False, default=True),
                        songs: Option(str, "Song names to lookup. Separate multiple song names with a comma.",
                                      required=False)):
        await ctx.interaction.response.defer()
        if songs:
            songs = songs.replace(', ', ',')
            song_list = songs.split(',')
            song_meta = await self.get_song_meta_output(fever, song_list)
            await ctx.interaction.followup.send(song_meta)
        else:
            song_meta = await self.get_song_meta_output(fever)
            await ctx.interaction.followup.send(song_meta)

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
                                                  default=20)):
        await ctx.interaction.response.defer()
        try:
            lb_api = await self.fetch_api(
                f'https://bestdori.com/api/sync/list/player?server={server}&stats={category}&limit={entries}&offset=0')
            total_entries = min(entries, lb_api['count'])
            category_names = {
                'hsr': 'High Score Rating',
                'dtr': 'Band Rating',
                'allPerfectCount': 'All Perfect Count',
                'fullComboCount': 'Full Combo Count',
                'cleared': 'Clear Count',
                'rank': 'Player Rank'
            }
            output = f'Top {total_entries} players for {category_names[category]}:\n'
            results = []
            row_count = 1
            while row_count <= entries:
                for row in lb_api['rows']:
                    if row['user']['nickname']:
                        results.append([str(row_count), row['user']['username'], row['stats'], row['user']['nickname']])
                    else:
                        results.append([str(row_count), row['user']['username'], row['stats']])
                    row_count += 1
            output += "```" + tabulate(results, tablefmt="plain", headers=["#", "Player", "Value", "Bestdori Name"]) + "```"

            if len(output) > 2000:
                output = 'Output is greater than 2000 characters, please select a smaller list of values to return!'
            await ctx.interaction.followup.send(output)
        except HTTPStatusError:
            await ctx.interaction.followup.send("Could not get data from Bestdori API.", ephemeral=True)


def setup(bot):
    bot.add_cog(Game(bot))
