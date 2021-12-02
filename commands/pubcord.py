import discord
import traceback
import asyncio
import pymongo
import datetime

from typing import Union, Optional, Literal
from discord.ext import commands, tasks
from discord.commands import user_command, permissions
from formatting.constants import UNITS
from formatting.embed import gen_embed
from __main__ import log, db, PersistentEvent

class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init = False
        self.check_boosters.start()

    def cog_unload(self):
        self.check_boosters.cancel()

    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                return role in ctx.author.roles
            else:
                return False

        return commands.check(predicate)

    @commands.Cog.listener()
    async def on_message(self, message):
        document = await db.servers.find_one({"server_id": 281815539267928064})
        pubcord = self.bot.get_guild(281815539267928064)#432379300684103699)
        channel = pubcord.get_channel(828380651735744512)#913958768105103390)
        if message.channel == channel or not self.init:
            if document['prev_message']:
                message_id = document['prev_message']
                prev_message = await channel.fetch_message(int(message_id))
                await prev_message.delete()
            new_message = await channel.send("Check out the current event by clicking below!", view=PersistentEvent())
            self.init = True
            await db.servers.update_one({"server_id": 281815539267928064}, {"$set": {'prev_message': new_message.id}})

    #@user_command(guild_ids=[432379300684103699], name='Verify User', default_permission=False)
    #@permissions.has_role("Moderator")
    #async def verifyrank(self, ctx, member: discord.Member):
    #    if ctx.guild.get_role(432388746072293387) in ctx.author.roles:
    #        roles = member.roles
    #        verified_role = ctx.guild.get_role(719791739367325706)
    #        if verified_role not in roles:
    #            roles.append(verified_role)
    #            await member.edit(roles=roles)
    #            await ctx.respond(content='Verified user.', ephemeral=True)
    #        else:
    #            await ctx.respond(content='User already verified.', ephemeral=True)
    #    else:
    #        await ctx.respond(content='You do not have access to this command.', ephemeral=True)

    @tasks.loop(seconds=120)
    async def check_boosters(self):
        log.info('running pubcord booster role parity check')
        pubcord = self.bot.get_guild(432379300684103699)
        emoteserver = self.bot.get_guild(815821301700493323)
        pubcord_booster_role = pubcord.get_role(913239378598436966)
        for member in pubcord.premium_subscribers:
            if not member.get_role(913239378598436966):
                log.info('adding member to booster role - boosting main server')
                roles = member.roles
                roles.append(pubcord_booster_role)
                await member.edit(roles=roles, reason="Boosting main server")

        for member in emoteserver.premium_subscribers:
            pubcord_member = pubcord.get_member(member.id)
            if pubcord_member:
                if not pubcord_member.get_role(913239378598436966):
                    log.info('adding member to booster role - boosting emote server')
                    roles = pubcord_member.roles
                    roles.append(pubcord_booster_role)
                    await pubcord_member.edit(roles=roles, reason="Boosting emote server")

        for member in pubcord_booster_role.members:
            emoteserver_member = emoteserver.get_member(member.id)
            if emoteserver_member:
                if emoteserver_member not in emoteserver.premium_subscribers:
                    if member not in pubcord.premium_subscribers:
                        log.info('not boosting either server, removing')
                        roles = member.roles
                        roles.remove(pubcord_booster_role)
                        await member.edit(roles=roles, reason="No longer boosting main OR emote server")
        log.info('parity check complete')

    @check_boosters.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    @commands.command(name='currentstatus',
                      description='Sends a embed with the latest status on EN Bandori.',
                      help='Usage\n\n%currentstatus')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def currentstatus(self, ctx, message_id: Optional[str]):
        embed = gen_embed(
            title='Current Status of EN Bandori',
            content='v4.10.0 will arrive at <t:1638439200>.'
        )
        embed.set_image(url='https://cdn.discordapp.com/attachments/611629664540295191/915809575331069962/Screenshot_20211201-223932_Google_Play_Store.png')
        embed.add_field(name=f'Current Event',
                        value=("Welcome to the Shrine\n"
                               "<t:1638493200> to <t:1639033140>\n\n"
                               "**Event Type**: Live Goals\n"
                               "**Attribute**: Cool <:attrCool:432978841162612756>\n"
                               "**Characters**: Arisa, Kaoru, Yukina, Mashiro, LAYER\n\n"
                               "※The event period above is automatically converted to the timezone set on your system."),
                        inline=False)
        embed.add_field(name=f'Gacha',
                                value=("2022 New Year Dream Festival Gacha\n"
                                       "Gorgeous New Year Parade Gacha [LIMITED]\n\n"
                                       "This list is subject to change. More information coming soon."),
                                inline=False)
        embed.set_footer(text='Last Updated 12/1/2021')
        if message_id:
            emessage = await ctx.channel.fetch_message(int(message_id))
            if emessage:
                await emessage.edit(embed=embed)

            qembed = gen_embed(
                name=None,
                icon_url=None,
                title='Common Q&A We Have Been Seeing',
                content=("**Q:** Are we skipping events?\n"
                        "**A:** No, we are not skipping any events. This is confirmed by our community manager.\n\n"
                        "**Q:** Are we not getting the collab anymore? What is the next event?.\n"
                        "**A:** We will still get the collab, but it is postponed. We don't know what the next event is as the schedule is being shuffled.\n\n"
                        "**Q:** Will we get compensated for this delay?\n"
                        "**A:** Yes, this is confirmed, but the amount is currently unknown.")
            )
            e2message = await ctx.channel.fetch_message(913960026920591380)
            await e2message.edit(embed=qembed)
            await ctx.message.delete()
        else:
            await ctx.send(embed=embed)

    @commands.command(name='maintenance',
                      description='Sends an embed to notify of game maintenance. Needs unix timestamps.',
                      help='Usage\n\n%maintenance [game version (ex: 4.10.0)] [start unix timestamp] [end unix timestamp]\nUse https://www.epochconverter.com/ to convert.')
    async def maintenance(self, ctx, version: str, start_unix: int, end_unix: int):
        embed = gen_embed(
            title='Maintenance Notice',
            content=(f"Maintenance for the version {version} update has begun.\n\n"
                    f"**Maintenance Period**:\n<t:{start_unix}> to <t:{end_unix}>\n\n"
                    "※If maintenance begins during a Live Show, the results may not be recorded.\n"
                    "※The maintenance period above is automatically converted to the timezone set on your system.")
        )
        embed.set_image(url='https://files.s-neon.xyz/share/EwwL0hoUYAADTHm.png')

        start_datetime = datetime.datetime.fromtimestamp(start_unix, datetime.timezone.utc)
        end_datetime = datetime.datetime.fromtimestamp(end_unix, datetime.timezone.utc)
        start_difference = start_datetime - datetime.datetime.now(datetime.timezone.utc)
        end_difference = end_datetime - start_datetime

        await ctx.message.delete()
        await asyncio.sleep(start_difference.total_seconds())
        sent_message = await ctx.send(embed=embed)
        await asyncio.sleep(end_difference.total_seconds())
        await sent_message.delete()

    @commands.command(name='delmaintenance',
                      description='Sends an embed to notify of game maintenance. Needs unix timestamps.',
                      help='Usage\n\n%delmaintenance [message_id] [end_unix]')
    async def delmaintenance(self, ctx, message_id: int, start_unix: int, end_unix: int):
        await ctx.message.delete()
        emessage = await ctx.channel.fetch_message(message_id)
        end_datetime = datetime.datetime.fromtimestamp(end_unix, datetime.timezone.utc)
        end_difference = end_datetime - datetime.datetime.now(datetime.timezone.utc)
        await asyncio.sleep(end_difference.total_seconds())
        await emessage.delete()

def setup(bot):
    bot.add_cog(Pubcord(bot))