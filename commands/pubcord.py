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
from __main__ import log, db

class PersistentEvent(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.count = 0

    @discord.ui.button(
        label="What's the current event?",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:currentevent",
    )
    async def currentevent(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='Current Status of EN Bandori',
            content=("Pastel*Palettes Band Story 3 Release\n"
                     "※ Confused about the extended Event Period? "
                     "This is put in place in order to allow the devs additional time in fixing the Android "
                     "crashing bug without having to worry about spending more development time on future Events."
                     )
        )
        embed.set_image(
            url='https://files.s-neon.xyz/share/FHWe1gKaUAAkQHs.jpg')
        embed.add_field(name=f'Current Event',
                        value=("Title Idol\n"
                               "<t:1640739600> to <t:1641884340>\n\n"
                               "**Event Type**: Mission Live\n"
                               "**Attribute**: Powerful <:attrPowerful:432978890064134145>  \n"
                               "**Characters**: Aya, Chisato, Hina, Maya, Eve\n\n"
                               "※The event period above is automatically converted to the timezone set on your system."),
                        inline=False)
        embed.add_field(name='Campaigns',
                        value=("> Collaboration Login Campaign - <:StarGem:432995521892843520> x2500 (1000 first day!)\n"
                               "> <t:1639209600> to <t:1641023940>\n"
                               "\n"
                               "> Worldwide 20M DL Celebration Mission - Earn up to 2000 items (3* Tickets, Stars, Miracle Crystals, etc.)\n"
                               "> <t:1640480400> to <t:1641862800>\n"
                               "\n"
                               "> End of Year Special Present - Rabbit Mashiro & LAYER Pins\n"
                               "> <t:1640505600> to <t:1640937540>\n"
                               "\n"
                               "> New Year's Countdown Login Campaign - <:StarGem:432995521892843520> x50 + Tone Crystals x10 everyday\n"
                               "> <t:1640505600> to <t:1641023940>\n"
                               "\n"),
                        inline=False)
        embed.add_field(name='Campaigns Part 2',
                        value=("Earn <:StarGem:432995521892843520> x3500 for new year!\n\n"
                               "> 2022 New Year's Star Present - <:StarGem:432995521892843520> x1500\n"
                               "> <t:1640937600> to <t:1642233540>\n"
                               "\n"
                               "> 2022 New Year's Login Campaign - <:StarGem:432995521892843520> x1000 + Special Pins\n"
                               "> <t:1641024000> to <t:1642751940>\n"
                               "\n"
                               "> Pastel*Palettes Band Story 3 Release Special Present - <:StarGem:432995521892843520> x1000\n"
                               "> <t:1640739600> to <t:1641776340>\n"
                               "\n"
                               "> Bang Dream! Girls Band Party!☆PICO FEVER! Release Celebration Gift\n"
                               "> Starting <t:1641456000>, weekly on Thursdays until <t:1648108800>"),
                        inline=False)
        embed.add_field(name=f'Gacha',
                        value=("> Interweaving Light Road to Prism Gacha\n"
                               "> <t:1640739600> to <t:1642035540>\n"
                               "\n"
                               "> A Merry Silent Night Gacha [LIMITED]\n"
                               "> A Merry Silent Night Special Set 10 Play Gacha\n"
                               "> <t:1640307600> to <t:1640912340>\n"
                               "\n"
                               "> Special Set 5 Play Gacha\n"
                               "> <t:1640912400> to <t:1642035540>\n"
                               "\n"
                               "> Bang Dream! Girls Band Party!☆PICO FEVER! Fan Appreciation ★4 Limited Member Guaranteed Gacha [LIMITED]\n"
                               "> <t:1641456000> to <t:1642665540>\n"
                               "\n"
                               "> Band Story 3 Pastel*Palettes ★4 Member Guaranteed Gacha\n"
                               "> <t:1640912400> to <t:1642726740>\n"
                               "\n"
                               "> Band Story 3 Afterglow ★4 Member Guaranteed Gacha\n"
                               "> <t:1640048400> to <t:1641776340>\n"
                               ),
                        inline=False)
        embed.add_field(name=f'Gacha Part 2',
                        value=("> 2022 New Year's All Members Free Gacha\n"
                               "> <t:1638493200> to <t:1641776340>\n"
                               "\n"
                               "> 2022 New Year's ★4 Limited Member Guaranteed Gacha [LIMITED]\n"
                               "> <t:1638493200> to <t:1641171540>\n"
                               "\n"
                               "> Come back ★4 Miracle Ticket Set Gacha\n"
                               "> <t:1639184400> onwards, available for 30 days\n"
                               "\n"
                               "> Collab Celebration 1 4* Member Guaranteed Gacha Vol. 1\n"
                               "> Collab Celebration 1 4* Member Guaranteed Gacha Vol. 2\n"
                               "> <t:1639184400> to <t:1641862740>\n"
                               "\n"
                               "This list is subject to change. More information coming soon."),
                        inline=False)
        embed.set_footer(text='Last Updated 12/28/2021')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="My game crashes!",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_view:gamecrash",
    )
    async def gamecrash(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='I have an android and my game keeps crashing! What do I do?',
            content=("The community has come up with a few workarounds for Android users while the issue is being worked on. Please note that these workarounds will not work 100% of the time, and the game can still crash at any moment.\n\n"
                     "※ If you are crashing before downloading the update, download the update on Mobile Data instead of WiFi.  (Please only do this if your data plan is forgiving/unlimited as the update is very large.)\n"
                     "※ If the update is already downloaded, log into the game with Mobile Data. Once you're on the main menu, you are free to switch back to WiFi.\n"
                     "※ Obtain a VM that runs Android 7, which runs perfectly on the update. Please note that the gameplay experience will not be the best in this situation.\n"
                     "※ Use VPNs such as Proton VPN and connect that to JP.\n\n"
                     "If none of these workarounds end up working for you, please be patient as the issue gets fixed.")
        )
        embed.set_footer(text='# of times Evets has posted about this on Twitter: 20+')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.check_boosters.start()
        self.start_currentevent.start()
        self.check_currentevent.start()

    def cog_unload(self):
        self.check_boosters.cancel()
        self.start_currentevent.cancel()
        self.check_currentevent.cancel()

    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                return role in ctx.author.roles
            else:
                return False

        return commands.check(predicate)

    def in_pubcord():
        async def predicate(ctx):
            if ctx.guild.id == 432379300684103699:
                return True
            else:
                return False

        return commands.check(predicate)

    @tasks.loop(seconds=5.0)
    async def check_currentevent(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message']:
            message_id = document['prev_message']
            prev_message = await channel.fetch_message(int(message_id))
            if channel.last_message_id != prev_message.id:
                log.info(f'prev_message: {prev_message.id}')
                if self.view:
                    self.view.stop()
                await prev_message.delete()
                log.info('deleted')
                self.view = PersistentEvent()
                new_message = await channel.send("Access quick links by clicking the buttons below!", view=self.view)
                log.info('posted')
                await db.servers.update_one({"server_id": 432379300684103699},
                                            {"$set": {'prev_message': new_message.id}})

    @tasks.loop(seconds=1.0, count=1)
    async def start_currentevent(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message']:
            message_id = document['prev_message']
            prev_message = await channel.fetch_message(int(message_id))
            await prev_message.delete()
            log.info('initial deleted')
        self.view = PersistentEvent()
        new_message = await channel.send("Access quick links by clicking the buttons below!", view=self.view)
        log.info('initial posted')
        await db.servers.update_one({"server_id": 432379300684103699}, {"$set": {'prev_message': new_message.id}})

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
    @start_currentevent.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    @check_currentevent.before_loop
    async def wait_ready_long(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    @commands.command(name='currentstatus',
                      description='Sends a embed with the latest status on EN Bandori.',
                      help='Usage\n\n%currentstatus')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole(), in_pubcord())
    async def currentstatus(self, ctx, message_id: Optional[str]):
        embed = gen_embed(
            title='Purpose of #announcements-en',
            content='This channel will feature important announcements like events and maintenance for the EN Bandori Server.'
        )
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
    async def delmaintenance(self, ctx, channel: int, message_id: int, end_unix: int):
        channel = await ctx.guild.get_channel(channel)
        emessage = await channel.fetch_message(message_id)
        end_datetime = datetime.datetime.fromtimestamp(end_unix, datetime.timezone.utc)
        end_difference = end_datetime - datetime.datetime.now(datetime.timezone.utc)
        await asyncio.sleep(end_difference.total_seconds())
        await emessage.delete()

def setup(bot):
    bot.add_cog(Pubcord(bot))