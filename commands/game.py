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

character_names = [
    'Kasumi Toyama',
    'Tae Hanazono',
    'Rimi Ushigome',
    'Saya Yamabuki',
    'Arisa Ichigaya',
    'Ran Mitake',
    'Moca Aoba',
    'Himari Uehara',
    'Tomoe Udagawa',
    'Tsugumi Hazawa',
    'Kokoro Tsurumaki',
    'Kaoru Seta',
    'Hagumi Kitazawa',
    'Kanon Matsubara',
    'Misaki Okusawa',
    'Aya Maruyama',
    'Hina Hikawa',
    'Chisato Shirasagi',
    'Maya Yamato',
    'Eve Wakamiya',
    'Yukina Minato',
    'Sayo Hikawa',
    'Lisa Imai',
    'Ako Udagawa',
    'Rinko Shirokane',
    'Mashiro Kurata',
    'Toko Kirigaya',
    'Nanami Hiromachi',
    'Tsukushi Futaba',
    'Rui Yashio',
    'Rei Wakana',
    'Rokka Asahi',
    'Masuki Sato',
    'Reona Nyubara',
    'Chiyu Tamade',
    'LAYER',  # RAS nicknames below
    'LOCK',
    'MASKING',
    'PAREO',
    'CHU²'
]

school_name_dict = {
    'hanasakigawa_high': "Hanasakigawa Girls' Academy",
    'haneoka_high': "Haneoka Girls' Academy",
    'tsukinomori_high': "Tsukinomori Girls' Academy",
    'geijutsu_high': "Geijutsu Academy",
    'shirayuki_high': "Shirayuki Private Academy",
    'kamogawa_middle': "Kamogawa Central Middle School",
    'celosia_international': "Celosia International Academy"
}


def find_rank(rank: int):
    xp_table = get_xp_table()
    xp = xp_table[rank]
    return xp


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
                5740220, 5942200, 6149280, 6361460, 6578750, 6801150, 7028660, 7261280, 7499010, 7741860, 7989830,
                8242920, 8501130, 8764460, 9032910, 9306480, 9585170, 9868980, 10157910, 10451960, 10751130, 11055420,
                11364830, 11679360, 11999010, 12323780, 12653670, 12988680, 13328810, 13674060, 14024430, 14379920,
                14740530, 15106260, 15477110, 15853080, 16234170, 16620380, 17011710, 17408160, 17809730, 18216420,
                18628230, 19045160, 19467210, 19894380, 20326670, 20764080, 21206610, 21654260, 22107030, 22564920,
                23027930, 23496060, 23969310, 24447680, 24931170, 25419780, 25913510, 26412360, 26916330, 27425420,
                27939630, 28458960, 28983410, 29512980, 30047670, 30587480, 31132410, 31682460, 32237630, 32797920,
                33363330, 33933860, 34509510, 35090280, 35676170, 36267180, 36863310, 37464560, 38070930, 38682420,
                39299030, 39920760, 40547610, 41179580, 41816670, 42458880, 43106210, 43758660, 44416230, 45078920,
                45746730, 46419660, 47097710, 47780880, 48469170, 49162580, 49861110, 50564760, 51273530, 51987420,
                52706430, 53430560, 54159810, 54894180, 55633670, 56378280, 57128010, 57882860, 58642830, 59407920,
                60178130, 60953460, 61733910, 62519480, 63310170, 64105980, 64906910, 65712960, 66524130, 67340420,
                68161830, 68988360, 69820010, 70656780, 71498670, 72345680, 73197810, 74055060, 74917430, 75784920,
                76657530, 77535260, 78418110, 79306080, 80199170, 81097380, 82000710, 82909160, 83822730, 84741420,
                85665230, 86594160, 87528210, 88467380, 89411670, 90361080, 91315610, 92275260, 93240030, 94209920,
                95184930, 96165060, 97150310, 98140680, 99136170, 100136780, 101142510, 102153360, 103169330, 104190420,
                105216630, 106247960, 107284410, 108325980, 109372670, 110424480, 111481410, 112543460, 113610630,
                114682920, 115760330, 116842860, 117930510, 119023280, 120121170, 121224180, 122332310, 123445560,
                124563930, 125687420, 126816030, 127949760, 129088610, 130232580, 131381670, 132535880, 133695210,
                134859660, 136029230, 137203920, 138383730, 139568660, 140758710, 141953880, 143154170, 144359580,
                145570110, 146785760, 148006530, 149232420, 150463430, 151699560, 152940810, 154187180, 155438670,
                156695280, 157957010, 159223860, 160495830, 161772920, 163055130, 164342460, 165634910, 166932480,
                168235170, 169542980, 170855910, 172173960, 173497130, 174825420, 176158830, 177497360, 178841010,
                180189780, 181543670, 182902680, 184266810, 185636060, 187010430, 188389920, 189774530, 191164260,
                192559110, 193959080, 195364170, 196774380, 198189710, 199610160, 201035730, 202466420, 203902230,
                205343160, 206789210, 208240380, 209696670, 211158080, 212624610, 214096260, 215573030, 217054920,
                218541930, 220034060, 221531310, 223033680, 224541170, 226053780, 227571510, 229094360, 230622330,
                232155420, 233693630, 235236960, 236785410, 238338980, 239897670, 241461480, 243030410, 244604460,
                246183630, 247767920, 249357330, 250951860, 252551510, 254156280, 255766170, 257381180, 259001310,
                260626560, 262256930, 263892420, 265533030, 267178760, 268829610, 270485580, 272146670, 273812880,
                275484210, 277160660, 278842230, 280528920, 282220730, 283917660, 285619710, 287326880, 289039170,
                290756580, 292479110, 294206760, 295939530, 297677420, 299420430, 301168560, 302921810, 304680180,
                306443670, 308212280, 309986010, 311764860, 313548830, 315337920, 317132130, 318931460, 320735910,
                322545480, 324360170, 326179980, 328004910, 329834960, 331670130, 333510420, 335355830, 337206360,
                339062010, 340922780, 342788670, 344659680, 346535810, 348417060, 350303430, 352194920, 354091530,
                355993260, 357900110, 359812080, 361729170, 363651380, 365578710, 367511160, 369448730, 371391420,
                373339230, 375292160, 377250210, 379213380, 381181670, 383155080, 385133610, 387117260, 389106030,
                391099920, 393098930, 395103060, 397112310, 399126680, 401146170, 403170780, 405200510, 407235360,
                409275330, 411320420, 413370630, 415425960]

    return xp_table


def get_xp_per_flame(flames_used: int):
    if flames_used == 1:
        xp = 2500
    elif flames_used == 2:
        xp = 3000
    elif flames_used == 3:
        xp = 3500
    return xp


def get_ep_per_flame(flames_used: int):
    if flames_used == 1:
        flames_ep_modifier = 5
    elif flames_used == 2:
        flames_ep_modifier = 10
    else:
        flames_ep_modifier = 15
    return flames_ep_modifier


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
                    except IndexError:
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
            output += "```" + tabulate(results, tablefmt="plain",
                                       headers=["#", "Player", "Value", "Bestdori Name"]) + "```"

            if len(output) > 2000:
                output = 'Output is greater than 2000 characters, please select a smaller list of values to return!'
            await ctx.interaction.followup.send(output)
        except HTTPStatusError:
            await ctx.interaction.followup.send("Could not get data from Bestdori API.", ephemeral=True)

    async def chara_name_autocomplete(self, ctx):
        return [name for name in character_names if ctx.value.lower() in name.lower()]

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
                chara_list_name = r[x]['characterName']
                chara_list_nickname = r[x]['nickname']
                if chara_list_name[1] is not None and character.lower() in chara_list_name[1].lower():
                    chara_id = x
                elif chara_list_name[0] is not None and character.lower() in chara_list_name[0].lower():
                    chara_id = x
                elif chara_list_nickname[1] is not None and character.lower() in chara_list_nickname[1].lower():
                    chara_id = x
                elif chara_list_nickname[0] is not None and character.lower() in chara_list_nickname[0].lower():
                    chara_id = x

            if not chara_id:
                await ctx.interaction.followup.send("Could not find character.", ephemeral=True)
                return

            chara_api = await self.fetch_api(f'https://bestdori.com/api/characters/{int(chara_id)}.json')
            if 'profile' not in chara_api:
                await ctx.interaction.followup.send("Character does not have a profile.", ephemeral=True)
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

            for school_key in school_name_dict:
                if school_key in chara_school:
                    chara_school = school_name_dict[school_key]
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
            await ctx.interaction.followup.send("Could not get data from Bestdori API.", ephemeral=True)

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
                      ep_per_song: Option(int, "EP gained per song", required=True),
                      current_ep: Option(int, "Current event point total", min_value=0, required=True),
                      target_ep: Option(int, "Target event point total", min_value=0, required=True),
                      flames_per_game: Option(int, "Flames used per game", choices=[1, 2, 3], required=True),
                      current_player_rank: Option(int, "Current player rank", min_value=1, max_value=500, required=True),
                      server: Option(str, "Server to get the current event's remaining time",
                                     choices=[OptionChoice('EN', value='1'),
                                              OptionChoice('JP', value='0'),
                                              OptionChoice('TW', value='2'),
                                              OptionChoice('CN', value='3'),
                                              OptionChoice('KR', value='4')],
                                     required=False,
                                     default='1'),
                      hrs_left: Option(float, "Manually input remaining time. Overrides time from 'server' argument.",
                                       required=False),
                      ):
        await ctx.interaction.response.defer()

        if current_player_rank > 500:
            output_string = "Beginning rank can't be over 500."
        else:
            xp_per_flame = get_xp_per_flame(flames_per_game)
            # , timeleft: int = timeLeftInt('en')
            # songs played
            songs_played = (target_ep - current_ep) / ep_per_song

            # beg xp
            if current_player_rank != 500:
                current_xp = find_rank(current_player_rank)

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

            if hrs_left is None:
                event_id = await self.get_current_event_id(server_id)
                hrs_left = await self.get_event_time_left_sec(server_id, event_id) / 3600

            # rankups
            rank_up_amt = end_rank - current_player_rank
            if rank_up_amt <= 0:
                rank_up_amt = 1

            # other stuff
            nat_flames = (32 * (int(hrs_left) / 24))  # assuming 16 hours efficient
            pts_per_refill = ((ep_per_song / flames_per_game) * 10)
            pts_from_rankup = (rank_up_amt * ((ep_per_song / flames_per_game) * 10))
            pts_naturally = (ep_per_song / flames_per_game) * nat_flames

            # time spent
            time_spent = math.floor((songs_played * 150) / 3600)  # seconds
            if time_spent > hrs_left:
                time_spent_str = f'{time_spent} (Warning: event ends in {hrs_left} hours)'
            else:
                time_spent_str = str(time_spent)

            # gems used
            stars_used = ((((target_ep - current_ep) - pts_naturally - pts_from_rankup) / pts_per_refill) * 100)
            if stars_used < 0:
                stars_used = 0
            else:
                stars_used = math.ceil(stars_used / 100.00) * 100

            output_string = ("```" + tabulate(
                [['Stars Used', "{:,}".format(stars_used)], ['Target', "{:,}".format(target_ep)],
                 ['Beginning Rank', current_player_rank], ['Ending Rank', end_rank],
                 ['Songs played', songs_played], ['Hours Spent (approx.)', time_spent]],
                tablefmt="plain") + "```")
        await ctx.interaction.followup.send(output_string)

    @game_commands.command(name='epgain',
                           description='Calculates EP gain for a single game.')
    async def epgain(self,
                     ctx: discord.ApplicationContext,
                     your_score: Option(int),
                     multi_score: Option(int),
                     bp_percent: Option(int),
                     flames_used: Option(int),
                     event_type: Option(int),
                     vs_placement: Option(int)):
        await ctx.interaction.followup.send("Command not implemented.")

    @game_commands.command(name='card',
                           description='Provides embedded image of card with specified filters.')
    async def card_lookup(self,
                          ctx: discord.ApplicationContext):
        await ctx.interaction.followup.send("Command not implemented.")


def setup(bot):
    bot.add_cog(Game(bot))
