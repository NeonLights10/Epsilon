import json
import os
import time
import math
import re
import datetime
import uuid

from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from tabulate import tabulate

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageFont import truetype
from os import path
from pathlib import Path
from operator import itemgetter

import discord
from discord import ui
from discord.ext import commands

from discord.commands import Option, OptionChoice, SlashCommandGroup
from discord import default_permissions

from formatting.embed import gen_embed

from __main__ import log, db


def unformat_name(name):
    return re.sub(r'\[[0-9a-fA-F]{6}\]|\[/?[a-z]\]', '', name)


class MonthlyPlayerView(discord.ui.DesignerView):


    message = None


    def __init__(self, player_pages, user_id):
        super().__init__(timeout=300)
        self._player_pages = player_pages
        self._user_id = user_id
        self._current_page = 0
        self._build()


    def _build(self):
        self.clear_items()
        player = self._player_pages[self._current_page]

        container = ui.Container(colour=discord.Colour.blurple())
        container.add_section(
            ui.TextDisplay(f"## {player['name']}"),
            ui.TextDisplay(f"-# ID: {player['id']}"),
            ui.TextDisplay(f"### Current Rank: {player['rank']}"),
            accessory=ui.Thumbnail(f"attachment://{player['profile_icon']}"),
        )
        container.add_separator()

        container.add_text(f"**Points:** {player['points']}")
        container.add_text(f"**Level:** {player['level']}")
        container.add_text(f"**Description:**\n{player['description']}")
        container.add_separator()

        container.add_gallery(
            discord.MediaGalleryItem(f"attachment://{player['band_image'][0]}")
        )
        container.add_separator()

        container.add_text(f"-# **Updated on:** {player['updated_on']}")
        container.add_separator()

        container.add_item(self._build_page_row())
        self.add_item(container)


    def _build_page_row(self):
        row = ui.ActionRow()
        row.add_button(
            label="<<",
            custom_id="first",
            style=discord.ButtonStyle.gray,
            disabled=self._current_page == 0,
        )
        row.add_button(
            label="<",
            custom_id="prev",
            style=discord.ButtonStyle.blurple,
            disabled=self._current_page == 0,
        )
        row.add_button(
            label=f"{self._current_page + 1}/{len(self._player_pages)}",
            custom_id="indicator",
            style=discord.ButtonStyle.gray,
            disabled=True,
        )
        row.add_button(
            label=">",
            custom_id="next",
            style=discord.ButtonStyle.blurple,
            disabled=self._current_page == len(self._player_pages) - 1,
        )
        row.add_button(
            label=">>",
            custom_id="last",
            style=discord.ButtonStyle.gray,
            disabled=self._current_page == len(self._player_pages) - 1,
        )
        return row
    

    def current_files(self):
        page = self._player_pages[self._current_page]
        return [
            discord.File(f"data/img/icons/base_icons/{page['profile_icon']}", filename=f'{page['profile_icon']}'),
            discord.File(page['band_image'][1], filename=page['band_image'][0])
        ]
    

    async def interaction_check(self, interaction: discord.Interaction) -> bool: 
        if self._user_id != interaction.user.id:
            return False
        
        cid = interaction.custom_id
        if cid == "first":
            self._current_page = 0
        elif cid == "prev":
            self._current_page -= 1
        elif cid == "next":
            self._current_page += 1
        elif cid == "last":
            self._current_page = len(self._player_pages) - 1
        self._build()
        await interaction.response.edit_message(view=self, files=self.current_files())
        return False
    

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Container):
                for child in item.items:
                    if isinstance(child, discord.ui.ActionRow):
                        for button in child.children:
                            button.disabled = True

        await self.message.edit(view=self, files=self.current_files())
        


class Monthly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncClient(follow_redirects=True)
        self.client = CachingClient(self.client)


    async def fetch_api(self, url):
        api = await self.client.get(url)
        return api.json()


    # taken from game.py and adjusted to fit the needs and new Pillow version; not an exact duplicate due to different format 
    async def generate_band_and_titles_image(self, band: list, titles: list, titles_api):
        icon_paths = []
        for band_member in sorted(band, key=lambda member: member['member_position']):
            icon_path = ""
            if band_member['trainingStatus']:
                icon_path = f"data/img/icons/full_icons/{band_member['member_id']}_trained.png"
            else:
                icon_path = f"data/img/icons/full_icons/{band_member['member_id']}.png"

            if path.exists(icon_path):
                icon_paths.append(icon_path)
            else: # use empty frame as placeholder
                icon_paths.append("data/img/2star.png")

        images = [Image.open(x) for x in icon_paths]
        widths, heights = zip(*(i.size for i in images))
        total_width = sum(widths)
        max_height = max(heights) * 2
        new_im = Image.new('RGBA', (int(total_width), max_height))
        x_offset = 0
        for im in images:
            new_im.paste(im, (x_offset, 0))
            x_offset += im.size[0]

        tier = ''
        if len(titles) == 2:
            x_offset = 0
            for title_id in titles:
                image_contents = []
                title_info = titles_api[str(title_id)]
                event_title = f"data/img/titles/en/{title_info['baseImageName'][1]}.png"
                image_contents.append(event_title)
                event = Image.open(image_contents[0])
                event = event.resize((368, 80), Image.Resampling.LANCZOS).convert("RGBA")
                new_im.paste(event, (x_offset, 250), event)

                tier = title_info['rank'][1]
                if tier != 'none' and tier != 'normal' and tier != 'extra':
                    tier_title = f'data/img/titles/en/event_point_{tier}.png'
                    image_contents.append(tier_title)
                    tier = Image.open(image_contents[1])
                    tier = tier.resize((368, 80), Image.Resampling.LANCZOS).convert("RGBA")
                    new_im.paste(tier, (x_offset, 250), tier)
                elif tier == 'normal' or tier == 'extra':
                    tier_title = f'data/img/titles/en/try_clear_{tier}.png'
                    image_contents.append(tier_title)
                    tier = Image.open(image_contents[1])
                    tier = tier.resize((368, 80), Image.Resampling.LANCZOS).convert("RGBA")
                    new_im.paste(tier, (x_offset, 250), tier)
                x_offset += 525
        else:
            x_offset = 250
            image_contents = []
            title_info = titles_api[str(titles[0])]
            event_title = f"data/img/titles/en/{title_info['baseImageName'][1]}.png"
            image_contents.append(event_title)
            event = Image.open(image_contents[0])
            event = event.resize((368, 80), Image.Resampling.LANCZOS).convert("RGBA")
            new_im.paste(event, (x_offset, 250), event)

            tier = title_info['rank'][1]
            if tier != 'none':
                tier_title = f'data/img/titles/en/event_point_{tier}.png'
                image_contents.append(tier_title)
                tier = Image.open(image_contents[1])
                tier = tier.resize((368, 80), Image.Resampling.LANCZOS).convert("RGBA")
                new_im.paste(tier, (x_offset, 250), tier)

        file_name = f'{str(uuid.uuid4())}.png'
        saved_file_path = f'data/img/imgTmp/{file_name}'
        if not path.exists('data/img/imgTmp/'):
            filepath = Path('data/img/imgTmp/')
            filepath.mkdir(parents=True, exist_ok=True)
        new_im.save(saved_file_path)
        return file_name, saved_file_path


    async def find_monthly_ranking_id(self, year: int, month: int):  
        start = datetime(year, month, 1, tzinfo=timezone.utc)   
        end = start + relativedelta(months=1)  
        # This may be a bit performance heavy, but necessary to get accurate result
        # If it becomes an issue down the line, we can replace this with a different solution
        # Either a pre-computed table for mapping monthly_ranking_id <==> year + month
        # Or just hardcore the ID to be a constant (5 + month difference from month1)
        pipeline = [
            {
                "$group": {
                    "_id": "$monthly_ranking_id",
                    "first_timestamp": {"$min": "$timestamp"}
                }
            },
            {
                "$match": {
                    "first_timestamp": {
                        "$gte": start,
                        "$lt": end
                    }
                }
            },
            {
                "$sort": {
                    "first_timestamp": 1
                }
            },
            {
                "$limit": 1
            }
        ]

        result = await db.monthlyRankings.aggregate(pipeline).to_list(length=1)
        return result[0]["_id"] if result else None
    

    async def get_highest_timestamp(self, ranking_id):
        ts_doc = await db.monthlyRankings.find_one(
            {"monthly_ranking_id": ranking_id},
            sort=[("timestamp", -1)],
            projection={"timestamp": 1, "final_record": 1, "_id": 0}
        )

        if ts_doc:
            return ts_doc["timestamp"], ts_doc['final_record']
        else:
            return None, None


    async def fetch_ranking_entries(self, ranking_id, timestamp):
        return await db.monthlyRankings.find(
            {
                "monthly_ranking_id": ranking_id,
                "timestamp": timestamp
            },
            sort=[("rank", 1)]
        ).to_list(length=None)


    async def fetch_players(self, player_ids):
        return await db.players.find(
            {"id": {"$in": player_ids}}
        ).to_list(length=None)


    async def get_monthly_ranking_data(self, ctx: discord.ApplicationContext, year: int, month: int, ranking_period: str):
        ranking_id = await self.find_monthly_ranking_id(year, month)
        if not ranking_id:
            await ctx.respond(
                embed=gen_embed(title='No data available',
                                content=f'{ranking_period} has no monthly ranking data available.'))
            return None, None, None
        
        fresh_ts, final_record = await self.get_highest_timestamp(ranking_id)
        if not fresh_ts:
            await ctx.respond(
                embed=gen_embed(title='No data available',
                                content=f'{ranking_period} has no monthly ranking data available.'))
            return None, None, None
        
        ranking_data = await self.fetch_ranking_entries(ranking_id, fresh_ts)
        player_data = await self.fetch_players([r['player_id'] for r in ranking_data])

        return fresh_ts, ranking_data, player_data


    async def tabulate_monthly_ranking(self, ctx: discord.ApplicationContext, ranking_period: str, fresh_ts: datetime, ranking_data: list, player_data: list):
        p_map = {p['id']: p for p in player_data}
        entries = [[r['rank'], r['points'], p_map[r['player_id']]['level'], r['player_id'], unformat_name(p_map[r['player_id']]['name'])] for r in ranking_data]
        table = tabulate(entries, tablefmt="plain", headers=["#", "Points", "Level", "ID", "Player"])
        output = ("```" + "  Ranking month: " + ranking_period + "\n  Last updated:  " + fresh_ts.strftime("%Y-%m-%d %H:%M:%S %Z%z") + "\n\n" + table + "```")
        await ctx.respond(output)


    async def get_profile_icon(self, player):
        if 'profileCard' in player and 'cardId' in player['profileCard']:
            card_id = player['profileCard']['cardId']
            if player['profileCard']['illustration'] == 'after_training':
                profile_picture = f"{card_id}_trained.png"
            else:
                profile_picture = f"{card_id}.png"
        else:
            ab = player['activeBand']
            center = [card for card in ab if card['member_position'] == 3]
            if center['trainingStatus']:
                profile_picture = f"{center['member_id']}_trained.png"
            else:
                profile_picture = f"{center['member_id']}.png"

        return profile_picture


    async def cards_monthly_ranking_player_dict(self, rank: dict, player: dict, updated_on, titles_api):
        icon_name = await self.get_profile_icon(player)
        band_name, band_path = await self.generate_band_and_titles_image(player['activeBand'], player['titleIds'], titles_api)

        return {
            'id': player['id'],
            'name': unformat_name(player['name']),
            'rank': rank['rank'],
            'points': rank['points'],
            'level': player['level'],
            'description': player['description'],
            'updated_on': updated_on.strftime("%Y-%m-%d %H:%M:%S %Z%z"),
            'profile_icon': icon_name,
            'band_image': (band_name, band_path)
        }


    async def cards_monthly_ranking(self, ctx: discord.ApplicationContext, ranking_period: str, fresh_ts: datetime, ranking_data: list, player_data: list):
        p_map = {p['id']: p for p in player_data}
        if len(ranking_data) == 0:
            await ctx.respond(
                embed=gen_embed(title='No data available',
                                content=f'{ranking_period} has no monthly ranking data available.'))
            return
        
        max_rank = min(max([r['rank'] for r in ranking_data]), 10)
        titles_api = await self.fetch_api('https://bestdori.com/api/degrees/all.3.json')
        player_pages = []

        for i in range(1, max_rank + 1):
            ranks = [r for r in ranking_data if r['rank'] == i]
            rank = ranks[0]
            player = p_map[rank['player_id']]
            player_obj = await self.cards_monthly_ranking_player_dict(rank, player, fresh_ts, titles_api)
            player_pages.append(player_obj)

        view = MonthlyPlayerView(player_pages, ctx.author.id)
        msg = await ctx.respond(view=view, files=view.current_files())
        if isinstance(msg, (discord.Message, discord.WebhookMessage)):
            view.message = msg
        elif isinstance(msg, discord.Interaction):
            view.message = await msg.original_response()


    async def format_monthly_ranking(self, ctx: discord.ApplicationContext, format: str, ranking_period: str, fresh_ts: datetime, ranking_data: list, player_data: list):
        match format:
            case 'table':
                await self.tabulate_monthly_ranking(ctx, ranking_period, fresh_ts, ranking_data, player_data)
            case 'cards':
                await self.cards_monthly_ranking(ctx, ranking_period, fresh_ts, ranking_data, player_data)
            case 2:
                await ctx.respond(
                    embed=gen_embed(title='Unknown format',
                                    content=f'Output format {format} is not supported.'))


    month_commands = SlashCommandGroup('monthly', 'Monthly Ranking commands')


    @month_commands.command(name='current',
                          description='Returns monthly ranking top 10 and cutoffs for the current month')
    async def monthly_current(self,
                  ctx: discord.ApplicationContext,
                  format: Option(str, "Choose the output format for the ranking",
                                          choices=[OptionChoice('Compact', value='table'),
                                                   OptionChoice('Profiles', value='cards')],
                                          required=False,
                                          default='table')):
        
        await ctx.interaction.response.defer()
        now_ts = datetime.now(timezone.utc)
        ranking_period = datetime(now_ts.year, now_ts.month, 1, tzinfo=timezone.utc).strftime("%B %Y")   
        fresh_ts, ranking_data, player_data = await self.get_monthly_ranking_data(ctx, now_ts.year, now_ts.month, ranking_period)
        if ranking_data:
            await self.format_monthly_ranking(ctx, format, ranking_period, fresh_ts, ranking_data, player_data)


    @month_commands.command(name='previous',
                          description='Returns monthly ranking top 10 and cutoffs for the previous month')
    async def monthly_previous(self,
                  ctx: discord.ApplicationContext,
                  format: Option(str, "Choose the output format for the ranking",
                                          choices=[OptionChoice('Compact', value='table'),
                                                   OptionChoice('Profiles', value='cards')],
                                          required=False,
                                          default='table')):
        
        await ctx.interaction.response.defer()
        ts = datetime.now(timezone.utc) - relativedelta(months=1)
        ranking_period = datetime(ts.year, ts.month, 1, tzinfo=timezone.utc).strftime("%B %Y")   
        fresh_ts, ranking_data, player_data = await self.get_monthly_ranking_data(ctx, ts.year, ts.month, ranking_period)
        if ranking_data:
            await self.format_monthly_ranking(ctx, format, ranking_period, fresh_ts, ranking_data, player_data)


    @month_commands.command(name='history',
                          description='Returns monthly ranking top 10 and cutoffs for a specified month')
    async def monthly_history(self,
                  ctx: discord.ApplicationContext,
                  year: Option(int, "Ranking Year", min_value=2026, max_value=2050,
                                     required=True),
                  month: Option(int, "Ranking Month",
                                          choices=[OptionChoice('January', value=1),
                                                   OptionChoice('February', value=2),
                                                   OptionChoice('March', value=3),
                                                   OptionChoice('April', value=4),
                                                   OptionChoice('May', value=5),
                                                   OptionChoice('June', value=6),
                                                   OptionChoice('July', value=7),
                                                   OptionChoice('August', value=8),
                                                   OptionChoice('September', value=9),
                                                   OptionChoice('October', value=10),
                                                   OptionChoice('November', value=11),
                                                   OptionChoice('December', value=12)],
                                          required=True),
                  format: Option(str, "Choose the output format for the ranking",
                                          choices=[OptionChoice('Compact', value='table'),
                                                   OptionChoice('Profiles', value='cards')],
                                          required=False,
                                          default='table')):
        
        await ctx.interaction.response.defer()
        ranking_period = datetime(year, month, 1, tzinfo=timezone.utc).strftime("%B %Y")   
        fresh_ts, ranking_data, player_data = await self.get_monthly_ranking_data(ctx, year, month, ranking_period)
        if ranking_data:
            await self.format_monthly_ranking(ctx, format, ranking_period, fresh_ts, ranking_data, player_data)
        

def setup(bot):
    bot.add_cog(Monthly(bot))
