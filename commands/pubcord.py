import discord
import traceback
import asyncio
import pymongo

from typing import Union, Optional, Literal
from discord.ext import commands, tasks
from formatting.constants import UNITS
from formatting.embed import gen_embed
from __main__ import log, db

class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_boosters.start()

    @tasks.loop(seconds=120)
    async def check_boosters(self):
        log.info('running pubcord booster role parity check')
        pubcord = self.bot.get_guild(432379300684103699)
        emoteserver = self.bot.get_guild(815821301700493323)
        for member in emoteserver.premium_subscribers:
            pubcord_member = pubcord.get_member(member.id)
            if pubcord_member:
                if not pubcord_member.get_role(pubcord.premium_subscriber_role.id):
                    log.info('checking member in emoteserver')
                    roles = member.roles
                    roles.append(pubcord.premium_subscriber_role)
                    await member.edit(roles=roles, reason="Boosting emote server")
        for member in pubcord.premium_subscribers:
            if not member.premium_since:
                log.info('checking member w/o date in pubcord')
                emoteserver_member = emoteserver.get_member(member.id)
                if emoteserver_member:
                    if not emoteserver_member.get_role(emoteserver.premium_subscriber_role.id):
                        roles = member.roles
                        roles.remove(pubcord.premium_subscriber_role)
                        await member.edit(roles=roles, reason="No longer boosting emote server")
        log.info('parity check complete')

    @check_boosters.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(Pubcord(bot))