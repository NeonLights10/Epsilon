import json

import discord
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup
from discord.commands.permissions import default_permissions

from httpx import AsyncClient, HTTPStatusError
from httpx_caching import CachingClient

from formatting.embed import gen_embed
from __main__ import log, db

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.character_list = []

    def cog_unload(self):
        pass

    async def fetch_api(self, url):
        api = await self.client.get(url)
        try:
            parsed = api.json()
        except json.decoder.JSONDecodeError:
            return None
        return parsed

    gacha_commands = SlashCommandGroup('gacha', 'Gacha related commands')

    async def character_autocomplete(self,
                                     ctx: discord.ApplicationContext):
        if not self.character_list:
            api_url='https://bestdori.com/api/characters/all.2.json'
            chara_api = await self.fetch_api(api_url)
            for entry in chara_api:
                for entry2 in entry['characterName']:
                    self.character_list.append(entry2.value)
        return [chara for chara in self.character_list if chara.startswith(ctx.value.lower())]

    @discord.slash_command(name='stats',
                           description='Return gacha stats for a particular user. Default user is yourself.')
    async def gacha_stats(self,
                          ctx: discord.ApplicationContext,
                          user: Option(discord.Member, 'User to timeout', required=False),
                          character: Option(str, "Enter a character name to filter by",
                                            default="",
                                            required=False,
                                            autocomplete=character_autocomplete)):
        await ctx.interaction.response.defer()
        #if character, check if valid response
        roll_info = db.gacha.find({"user_id": user.id})
        if roll_info:
            avatar = user.display_avatar.url
            if ctx.author.bot is False:
                two_star_count = roll_info['two_star_count']
                three_star_count = roll_info['three_star_count']
                four_star_count = roll_info['four_star_count']
            else:
                #add response
                return
            total_count = two_star_count + three_star_count + four_star_count
            four_star_rate = f"{round(((four_star_count / total_count) * 100), 2)}%"
            if user:
                if not character:
                    title = f"{user.display_name}'s Roll Stats"
                else:
                    title = f"{user.display_name}'s {character} Roll Stats"
            else:
                if not character:
                    title = f"{ctx.interaction.user.display_name}'s Roll Stats"
                else:
                    title = f"{ctx.interaction.user.display_name}'s {character} Roll Stats"
            embed = gen_embed(name=title)
            embed.set_thumbnail(url=avatar)
            embed.add_field(name='Total Cards Rolled', value="{:,}".format(total_count), inline=True)
            embed.add_field(name='4* Rate', value=four_star_rate, inline=True)
            embed.add_field(name='\u200b', value='\u200b', inline=True)
            embed.add_field(name='2* Rolled', value="{:,}".format(two_star_count), inline=True)
            embed.add_field(name='3* Rolled', value="{:,}".format(three_star_count), inline=True)
            embed.add_field(name='4* Rolled', value="{:,}".format(four_star_count), inline=True)
            await ctx.interaction.followup.send(embed=embed)
        else:
            await ctx.interaction.followup.send(embed=gen_embed(name='gacha',
                                                                content='No stats found for that user'))

