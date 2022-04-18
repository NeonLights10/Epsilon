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
        label="New Event/Campaigns/Gacha/Songs",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:currentevent",
    )
    async def currentevent(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='What is going on in EN Bandori?',
            content=('※ Congratulations ENdori on 4 years!'))
        embed.set_image(
            url='https://files.s-neon.xyz/share/sayaagaming.png')
        embed.add_field(name=f'Current Event',
                        value=("Backstage Pass 4\n"
                               "<t:1649984400> to <t:1650524340>\n\n"
                               "**Event Type**: Live Goals\n"
                               "**Attribute**: Pure <:attrPure:432978922892820495>\n"
                               "**Characters**: Sayaa, Tomoe, Kanon, Maya, Ako, Tsukushi, MASKING (Drummers)\n\n"
                               "※ The event period above is automatically converted to the timezone set on your system."),
                        inline=False)
        embed.add_field(name='Campaigns',
                        value=("> 4th Anniversary Present - x4000 <:StarGem:432995521892843520> & x100 Tone Crystal\n"
                               "> <t:1649984400> to <t:1651737540>\n\n"
                               "> 4th Anniversary Login Campaign - x200 <:StarGem:432995521892843520> per day\n"
                               "> <t:1649984400> to <t:1651737540>"),
                        inline=False)
        embed.add_field(name=f'Miracle Tickets',
                        value=("> 4th Anniversary! ★4 Miracle Ticket Set Gacha\n"
                               "> ※ Get ONE (1) ★4 Miracle Ticket, Paid <:StarGem:432995521892843520> x2500 \n"
                               "> <t:1649379600> to <t:1651885140>\n"
                               "\n"
                               "> 4th Anniversary! ★4 Miracle Ticket Set Gacha\n"
                               "> ※ Get ONE (1) ★4 Miracle Ticket, Paid <:StarGem:432995521892843520> x2500 \n"
                               "> <t:1649984400> to <t:1652576340>\n"
                               "\n"
                               "> 4th Anniversary! Limited ★4 Miracle Ticket Set Gacha\n"
                               "> ※ Get ONE (1) LIMITED ★4 Miracle Ticket, Paid <:StarGem:432995521892843520> x2500 \n"
                               "> <t:1650416400> to <t:1653008340>\n"
                               ),
                        inline=False)
        embed.add_field(name=f'Gacha',
                        value=("> Girls Band Life! 4 Gacha\n"
                               "> Girls Band Life! PLUS Gacha\n"
                               "> <t:1650330000> to <t:1650675540>\n"
                               "\n"
                               "> 4th Anniversary! Free 10 Play a Day Gacha [FREE]\n"
                               "> ※ Play up to 7 times"
                               "> <t:1650009600> to <t:1652601540>\n"
                               "\n"
                               "> 4th Anniversary ★4 Limited Member Guaranteed Gacha [LIMITED]\n"
                               "> <t:1649984400> to <t:1652576340>\n"
                               "\n"
                               "> 4th Anniversary 1 ★4 Member Guaranteed! Gacha Vol. 1\n"
                               "> 4th Anniversary 1 ★4 Member Guaranteed! Gacha Vol. 2\n"
                               "> <t:1649984400> to <t:1652576340>\n"
                               "\n"
                               "> 4th Anniversary Step Up Gacha\n"
                               "> Paid <:StarGem:432995521892843520> x250|700|1000|1750, get stickers!\n"
                               "> <t:1649984400> to <t:1650873540\n"
                               "\n"
                               "This list is subject to change. More information coming soon."),
                        inline=False)
        embed.add_field(name=f'New Songs',
                        value=("<:PasupareLogo:432981125455937536> Into the Night\n"
                               "9 | 14 | 19 | 26\n\n"
                               "<:PopipaLogo:432981132414287872> Yesterday\n"
                               "7 | 12 | 17 | 24\n\n"
                               "<:AfterglowLogo:432981108338982922> Samurai Heart (Some Like It Hot!!)\n"
                               "8 | 14 | 20 | 26\n\n"
                               "<:HHWLogo:432981119437242388> SHINY DAYS\n"
                               "7 | 12 | 17 | 23\n\n"
                               "<:MorfonicaLogo:682986271462654054> Agehachou\n"
                               "7 | 13 | 18 | 25 | 23\n\n"
                               "<:RASLogo:721150392271896616> DAYBREAK FRONTLINE\n"
                               "7 | 13 | 19 | 26\n\n"
                               "<:RoseliaLogo:432981139788005377> Sycnhrogazer\n"
                               "9 | 15 | 20 | 26"),
                        inline=False)
        embed.set_footer(text='Last Updated 4/18/2022')
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
            content=("Good news! The **version 4.10.3** update should fix the crashing issue for Android users. If you are still having issues, you can try the workarounds below.\n\n"
                     "※ Clear the cache in Android settings and restart the phone; then clear cache in game and restart.\n"
                     "※ Delete your Google ad ID (if you don't have one, make a new one and then delete it).\n"
                     "※ Use a VPN to connect from Japan/Singapore using mobile data."
                     ))
        embed.set_footer(text='Updated 3/10/22')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Version 5.6.0 Changelog",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_view:changelog",
    )
    async def changelog(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='v5.6.0 Changelog',
            content=(
                "This update is a bulk update, containing everything from v5.0.0 to v5.6.0 in the Japanese Version.\n"
                "Remember to update the app in your respective app store while the game is in maintenance!")
        )
        embed.add_field(name=f'SP Notes (Direction Flicks/Curve Notes)',
                        value=("The following songs will be given new SP charts with these notes (UTC):\n"
                               "> **Roki** - Apr. 15\n"
                               "> **Fuwa-Fuwa Time** - Apr. 15\n"
                               "> **Maware! Setsugetsuka** - Apr. 17\n"
                               "> **Daylight** - Apr. 18\n"
                               "> **EXPOSE - Burn Out!!!** - Apr. 19\n"
                               "> **R** - Apr. 20\n"
                               "> **Setsuna Trip** - Apr. 21\n"
                               "※ SP Notes will launch with skins and the ability to change how high the effects are."),
                        inline=False)
        embed.add_field(name=f'Beginner Panel Missions',
                        value="Upon maintenance end, a set of 5 beginner missions will be available! All players will be able to clear them.",
                        inline=False)
        embed.add_field(name=f'Rank Updates',
                        value=("※ Player Rank cap up to 400\n"
                               "※ Band Rank cap up to 50\n"
                               "※ Band Area Item level cap up to 7"),
                        inline=False)
        embed.add_field(name=f'New Character Titles',
                        value=("Over 100 new titles will be added for reading a member's card stories and getting more cards of that member.\n"
                               "**※ These missions are set to be added in May 21.**"),
                        inline=False)
        embed.add_field(name=f'Preparations',
                        value=("※ Preparation for Birthday Gachas\n"
                               "※ Preparation for Team Live Festival Event type\n"
                               "※ Preparation for Medley Live Event type"),
                        inline=False)
        embed.add_field(name=f'Miscellaneous Changes',
                        value=("※ Option to use 0 Live Boosts added\n"
                               "※ Added retry option in Free Live\n"
                               "※ Option to turn on/off all MVs\n"
                               "※ Lightweight Mode updated to have adjustable brightness and background (Up to 30% brightness)\n"
                               "※ Note Speed max up to 12.0\n"
                               "※ Live Boosts will now be consumed at the end of a live\n"
                               "※ ALL PERFECT animation/EX missions/sorting added\n"
                               "※ FAST/SLOW timing option added\n"
                               "※ Area Item confirmation when setting a main band\n"
                               "※ Multi-Live Stamps are usable while loading into a live"),
                        inline=False)
        embed.set_footer(text='Last Updated 4/18/2022.')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AnniversaryRole(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.count = 0

    @discord.ui.button(
        label="Backstage Pass 4",
        emoji=discord.PartialEmoji.from_str("<:apstar:963127616456499280>"),
        style=discord.ButtonStyle.primary,
        custom_id="persistent_view:anniversaryrole",
    )
    async def anniversaryrole(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        role = interaction.guild.get_role(963122511317459064)
        if interaction.user.get_role(963122511317459064):
            await interaction.user.remove_roles(role, reason='Self-assign anniversary role')
            await interaction.followup.send(content='Removed the role "Backstage Pass 4" from your user profile.',
                                            ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason='Self-assign anniversary role')
            await interaction.followup.send(content='Added the role "Backstage Pass 4" to your user profile.', ephemeral=True)

class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.view_anni = None
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
            else:
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

    @commands.command(name='bs4selfassign',
                      description='Internal only')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    @commands.check(in_pubcord())
    async def bs4selfassign(self, ctx, channel: discord.TextChannel):
        if self.view_anni:
            self.view_anni.stop()
        self.view_anni = AnniversaryRole()
        await channel.send(embed=gen_embed(title='Backstage Pass 4 Role',
                                           content='Click the button below to add the role. Click it again to remove it.'),
                           view=self.view_anni)


    @commands.command(name='currentstatus',
                      description='Sends a embed with the latest status on EN Bandori.',
                      help='Usage\n\n%currentstatus')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    @commands.check(in_pubcord())
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