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
            content=('※ Active changes to the event schedule are in effect. Check "Upcoming Schedule and DF Changes" for more info.'))
        embed.set_image(
            url='https://files.s-neon.xyz/share/FOmgOpXVgAMA1xm.png')
        embed.add_field(name=f'Current Event',
                        value=("Analysis of Harmony and Change\n"
                               "<t:1648602000> to <t:1649141940>\n\n"
                               "**Event Type**: Live Goals\n"
                               "**Attribute**: Pure <:attrPure:432978922892820495>\n"
                               "**Characters**: Mashiro, Touko, Nanami, Tsukushi, Rui\n\n"
                               "※The event period above is automatically converted to the timezone set on your system."),
                        inline=False)
        embed.add_field(name='Campaigns',
                        value=("> 10M DL Celebration Login Campaign - 50 <:StarGem:432995521892843520> per day for 10 days\n"
                               "> <t:1647763200> to <t:1649491199>\n"),
                        inline=False)
        embed.add_field(name=f'Gacha',
                        value=("> Library Lit in Tranquility Gacha\n"
                               "> 1 Time Special! Library Lit in Tranqulity Gacha\n"
                               "> <t:1648602000> to <t:1649293140>\n"
                               "\n"
                               "> Band Story 3 Poppin'Party ★4 Member Guaranteed Gacha\n"
                               "> <t:1647046800> to <t:1649638740>\n"
                               "\n"
                               "> Event Bonus Members & Types Gacha\n"
                               "> <t:1648774800> to <t:1649293140>\n"
                               "\n"
                               "This list is subject to change. More information coming soon."),
                        inline=False)
        embed.add_field(name=f'New Songs',
                        value=("<:MorfonicaLogo:682986271462654054> Sonorous - Release during event\n"
                               "7 | 13 | 18 | 25"),
                        inline=False)
        embed.set_footer(text='Last Updated 3/29/2022')
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
        label="Upcoming Schedule & DF Changes",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_view:schedule",
    )
    async def schedule(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='Notice - Upcoming Schedule, v5.0.0 Delays, & Dreamfest/Birthday Gacha Info',
            content=(
                "WDue to the previous optimization work for Android issues, the next major update (v5.0) will unfortunately be pushed back to a later date on the accelerated schedule.\n"
                "As such, certain events & features that relied on the version update will be rescheduled.\n\n"
                "The event schedule has been adjusted accordingly, and upcoming birthday gachas will also be delayed separately to after the 5.0 update.")
        )
        embed.add_field(name=f'Upcoming Schedule - Dates are in UTC',
                        value=("> A Stroll Colored by Sakura: March 4 - March 10\n"
                               "> Live Beyond: March 12 - March 18\n"
                               "> Embracing Your Lost and Confused Self: March 20 - March 28\n"
                               "> Analysis of Harmony and Change: March 30 - April 5\n"
                               "> Little Rose Harmony: April 7 - April 13\n"
                               "> Backstage Pass 4: April 15\n"
                               "※ Event title translations are subject to change."),
                        inline=False)
        embed.add_field(name=f'What will happen to Dream Festivals?',
                        value="Dream Festivals are currently set to be connected to their corresponding Event. With this in mind, expect a Dream Festival on March 20, and April 15.",
                        inline=False)
        embed.add_field(name=f'What happens to Birthday Gachas?',
                        value=("Birthday Gachas will be moved to take place after the 5.0 update gets released. These will **NOT** be pushed back an entire year.\n"
                              "The exact date as to when these Birthday Gachas will take place is currently unknown, outside of 'after the 5.0 update'.\n\n"
                              "The following Birthday Gachas are affected:\n"
                              "> Hina Hikawa Birthday Gacha\n"
                              "> Sayo Hikawa Birthday Gacha\n"
                              "> Rimi Ushigome Birthday Gacha\n"
                              "> PAREO Birthday Gacha\n"
                              "> Chisato Shirasagi Birthday Gacha\n"
                              "> Ran Mitake Birthday Gacha"),
                        inline=False)
        embed.set_footer(text='Last Updated 3/3/2022.')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PersistentPlace(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.count = 0

    @discord.ui.button(
        label="Coordinates",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:placecoordinates",
    )
    async def coordinates(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='Location Coordinates?',
            content=('1285,127\n'
                     'https://www.reddit.com/r/place/?cx=1297&cy=138&px=29'))
        embed.set_image(
            url='https://media.discordapp.net/attachments/959919689994240070/959997442286301225/unknown.png')
        embed.set_footer(text='r/place 2022')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Template",
        style=discord.ButtonStyle.green,
        custom_id="persistent_view:placetemplate",
    )
    async def template(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = gen_embed(
            title='Template',
            content=('See below!'))
        embed.set_image(
            url='https://media.discordapp.net/attachments/959919689994240070/960005529554538496/kasumi.png')
        embed.set_footer(text='r/place 2022')
        self.count += 1
        log.info(f'Quick Link Interaction {self.count}')
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.view_place = None
        self.check_boosters.start()
        self.start_currentevent.start()
        self.check_currentevent.start()
        self.start_place.start()
        self.check_place.start()

    def cog_unload(self):
        self.check_boosters.cancel()
        self.start_currentevent.cancel()
        self.check_currentevent.cancel()
        self.start_place.cancel()
        self.check_place.cancel()

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

    @tasks.loop(seconds=10.0)
    async def check_place(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(959919689994240070)
        if document['prev_message_place']:
            message_id = document['prev_message_place']
            prev_message = await channel.fetch_message(int(message_id))
            if channel.last_message_id != prev_message.id:
                log.info(f'prev_message_place: {prev_message.id}')
                if self.view_place:
                    self.view_place.stop()
                await prev_message.delete()
                log.info('deleted')
                self.view_place = PersistentPlace()
                new_message = await channel.send("Get coordinates and template by clicking the buttons below!", view=self.view_place)
                log.info('posted')
                await db.servers.update_one({"server_id": 432379300684103699},
                                            {"$set": {'prev_message_place': new_message.id}})

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

    @tasks.loop(seconds=1.0, count=1)
    async def start_place(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(959919689994240070)
        if document['prev_message_place']:
            message_id = document['prev_message_place']
            prev_message = await channel.fetch_message(int(message_id))
            await prev_message.delete()
            log.info('initial deleted')
        self.view_place = PersistentPlace()
        new_message = await channel.send("Get coordinates and template by clicking the buttons below!", view=self.view_place)
        log.info('initial posted')
        await db.servers.update_one({"server_id": 432379300684103699}, {"$set": {'prev_message_place': new_message.id}})

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