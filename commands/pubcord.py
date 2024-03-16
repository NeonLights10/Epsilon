import time
import asyncio
import datetime

from httpx import AsyncClient
from httpx_caching import CachingClient

import discord
from discord.ext import commands, tasks
from discord.commands import Option, SlashCommandGroup
from discord.commands.permissions import default_permissions

from formatting.embed import gen_embed
from __main__ import log, db
from commands.errorhandler import CheckOwner


class AnnouncementButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, custom_id: str, content: discord.Embed):
        super().__init__(
            label=label,
            style=style,
            custom_id=custom_id)
        self.count = 0
        self.content = content

    async def callback(self, interaction: discord.Interaction):
        self.count += 1
        log.info(f'Quicklink/Announcement Button {self.custom_id} interaction {self.count}')
        await interaction.response.send_message(embed=self.content, ephemeral=True)


class AnnouncementBulletin(discord.ui.View):
    def __init__(self, content=None):
        super().__init__(timeout=None)
        self.count = {}
        for announcement in content:
            new_button = AnnouncementButton(announcement['label'],
                                            announcement['style'],
                                            announcement['custom_id'],
                                            announcement['content'])
            self.add_item(new_button)


class SpecialRoleButton(discord.ui.Button):
    def __init__(self, label: str, custom_id: str, role_id):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=custom_id)
        self.count = 0
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        role = interaction.guild.get_role(self.role_id)
        if interaction.user.get_role(self.role_id):
            await interaction.user.remove_roles(role, reason='Self-assign special role')
            await interaction.followup.send(content=f'Removed the role "{role.name}" from your user profile.',
                                            ephemeral=True)
        else:
            await interaction.user.add_roles(role, reason='Self-assign special role')
            await interaction.followup.send(content=f'Added the role "{role.name}" to your user profile.',
                                            ephemeral=True)
            self.count += 1
            log.info(f'Total members added special role in {interaction.guild.name}: {self.count}')


class SpecialRole(discord.ui.View):
    def __init__(self, label, guild_id, role):
        super().__init__(timeout=None)
        self.count = 0
        new_button = SpecialRoleButton(label, f'{guild_id}:specialrole', role.id)
        self.add_item(new_button)


async def get_next_event():
    current_time = time.time() * 1000

    url = 'https://bestdori.com/api/events/all.5.json'
    client = AsyncClient(follow_redirects=True)
    client = CachingClient(client)

    r = await client.get(url)
    api = r.json()
    event_start_dates = {}
    for event in api:
        if api[event]['startAt'][1]:
            event_start_dates[event] = api[event]['startAt'][1]
    res_key, res_val = min(event_start_dates.items(), key=lambda x: abs(current_time - float(x[1])))
    log.info(f'Current event ID: {res_key}')
    return res_key


class Pubcord(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.views = {}
        self.view_anni = None
        self.check_count = 0
        self.check_boosters.start()
        self.init_announcementbulletins.start()
        self.check_announcementbulletins.start()
        self.update_pubcord_quicklinks.start()

    def cog_unload(self):
        self.check_boosters.cancel()
        self.init_announcementbulletins.cancel()
        self.check_announcementbulletins.cancel()
        self.update_pubcord_quicklinks.cancel()

    @staticmethod
    def is_owner():
        async def predicate(ctx) -> bool:
            if isinstance(ctx, discord.ApplicationContext):
                if ctx.interaction.user.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()
            else:
                if ctx.author.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()

        return commands.check(predicate)

    @staticmethod
    async def generate_current_event(force=False) -> discord.Embed | None:
        current_time = time.time() * 1000
        current_event_id = await get_next_event()

        client = AsyncClient(follow_redirects=True)
        client = CachingClient(client)

        events_url = f'https://bestdori.com/api/events/{current_event_id}.json'
        r_event = await client.get(events_url)
        event_data = r_event.json()

        event_name = event_data['eventName'][1]
        event_start = event_data['startAt'][1]
        if current_time > float(event_start) and not force:
            return
        event_end = event_data['endAt'][1]
        event_type = event_data['eventType']
        match event_type:
            case "mission_live":
                event_type = "Mission Live"
            case "versus":
                event_type = "VS Live"
            case "live_try":
                event_type = "Live Goals"
            case "challenge":
                event_type = "Challenge Live"
            case "festival":
                event_type = "Team Live Festival"
            case "medley":
                event_type = "Medley Live"
        event_attribute = event_data['attributes'][0]['attribute']
        event_characters = []
        for entry in event_data['characters']:
            char_id = entry['characterId']
            character_url = f'https://bestdori.com/api/characters/{char_id}.json'
            r_char = await client.get(character_url)
            char_data = r_char.json()
            event_characters.append(char_data['firstName'][1])
        event_gacha = []
        event_songs = []

        song_url = f'https://bestdori.com/api/songs/all.5.json'
        r_song = await client.get(song_url)
        song_data = r_song.json()
        for key, song in song_data.items():
            if song['publishedAt'][1]:
                if float(event_start) <= float(song['publishedAt'][1]) < float(event_end):
                    difficulty = []
                    for diff, val in song['difficulty'].items():
                        difficulty.append(str(val['playLevel']))

                    band_id = song['bandId']
                    band_url = f'https://bestdori.com/api/bands/all.1.json'
                    r_band = await client.get(band_url)
                    band_data = r_band.json()
                    s = {
                        'title': song['musicTitle'][1],
                        'band': band_data[str(band_id)]['bandName'][1],
                        'difficulty': difficulty
                    }
                    event_songs.append(s)

        gacha_url = f'https://bestdori.com/api/gacha/all.5.json'
        r_gacha = await client.get(gacha_url)
        gacha_data = r_gacha.json()
        for key, gacha in gacha_data.items():
            if gacha['publishedAt'][1]:
                if (float(event_start) <= float(gacha['publishedAt'][1]) < float(event_end)
                        or float(event_start) <= float(gacha['closedAt'][1]) <= float(event_end)
                        or float(gacha['closedAt'][1]) > float(event_end)):
                    if float(gacha['closedAt'][1]) < 4102462800000:
                        g = {
                            'title': gacha['gachaName'][1],
                            'type': gacha['type'],
                            'start': int(gacha['publishedAt'][1]),
                            'end': int(gacha['closedAt'][1])
                        }
                        event_gacha.append(g)

        embed_post = gen_embed(
            title='What is going on in EN Bandori?',
            content='Find out the latest happenings for events, gacha, and songs!')

        attribute_emoji = ''
        match event_attribute:
            case 'happy':
                attribute_emoji = '<:attrHappy:432978959957753905>'
            case 'pure':
                attribute_emoji = '<:attrPure:432978922892820495>'
            case 'cool':
                attribute_emoji = '<:attrCool:432978841162612756>'
            case 'powerful':
                attribute_emoji = '<:attrPowerful:432978890064134145>'

        embed_post.add_field(name='Current Event',
                             value=(f"{event_name}\n"
                                    f"<t:{int(int(event_start) / 1000)}> to <t:{int(int(event_end) / 1000)}>\n"
                                    f"**Event Type**: {event_type}\n"
                                    f"**Attribute**: {event_attribute.capitalize()} {attribute_emoji}\n"
                                    f"**Characters**: {', '.join(event_characters)}\n"
                                    "※ The event period above is automatically converted to the timezone set on your"
                                    " system."),
                             inline=False)

        gacha_count = 1
        gacha_formatted = ''
        for entry in event_gacha:
            if gacha_count >= 5:
                embed_post.add_field(name='Gacha',
                                     value=gacha_formatted,
                                     inline=False)
                gacha_formatted = ''
                gacha_count = 1
            gacha_title = entry['title']
            gacha_type = entry['type'].capitalize()
            gacha_start = int(entry['start'] / 1000)
            gacha_end = int(entry['end'] / 1000)
            gacha_formatted += f'> {gacha_title} ({gacha_type})\n> <t:{gacha_start}> to <t:{gacha_end}>\n\n'
            gacha_count += 1
        if gacha_count != 1:
            if gacha_formatted == '':
                gacha_formatted = 'None'
            embed_post.add_field(name='Gacha',
                                 value=gacha_formatted,
                                 inline=False)

        songs_formatted = ''
        for entry in event_songs:
            band_emoji = '?'
            match entry['band']:
                case "Poppin'Party":
                    band_emoji = '<:PopipaLogo:432981132414287872>'
                case "Afterglow":
                    band_emoji = '<:AfterglowLogo:432981108338982922>'
                case "Hello, Happy World!":
                    band_emoji = '<:HHWLogo:432981119437242388>'
                case "Pastel＊Palettes":
                    band_emoji = '<:PasupareLogo:432981125455937536>'
                case "Roselia":
                    band_emoji = '<:RoseliaLogo:432981139788005377>'
                case "RAISE A SUILEN":
                    band_emoji = '<:RASLogo:721150392271896616>'
                case "Morfonica":
                    band_emoji = '<:MorfonicaLogo:682986271462654054>'
                case _:
                    band_emoji = '<:StarGem:432995521892843520>'
            song_title = entry['title']
            difficulty_string = " | ".join(entry['difficulty'])
            songs_formatted += f'{band_emoji} {song_title}\n{difficulty_string}\n\n'

        if songs_formatted == "":
            songs_formatted = "No new songs"
        embed_post.add_field(name='New Songs',
                             value=songs_formatted,
                             inline=False)

        current_t = datetime.datetime.now(datetime.timezone.utc)
        embed_post.set_footer(text=f'Last Updated {current_t.strftime("%m/%d/%y")}')
        return embed_post

    @tasks.loop(seconds=1.0, count=1)
    async def init_announcementbulletins(self):
        # pubcord currently hardcoded, eventually expand feature (todo)
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390) # 913958768105103390
        if document['prev_message']:
            message_id = document['prev_message']
            try:
                prev_message = await channel.fetch_message(int(message_id))
                await prev_message.delete()
                log.info('previous announcement bulletin deleted')
            except discord.NotFound:
                pass

        newcontent_embed = await self.generate_current_event(force=True)
        newcontent_content = {
            'label': 'New Event/Songs/Gacha Info',
            'style': discord.ButtonStyle.green,
            'custom_id': f'{pubcord.id}:newcontent',
            'content': newcontent_embed
        }
        gamecrash_embed = gen_embed(
            title='Upcoming Event Schedule',
            content=("Due to technical reasons and a longer preparation time for the required version update, "
                     "certain affected events will be pushed back to a later date."))
        gamecrash_embed.set_footer(text='Updated 3/10/24')
        gamecrash_embed.add_field(name='March 17', value='<:AfterglowLogo:432981108338982922><:attrPure:432978922892820495>  Medley Live Event [Afterlight '
                                                         '~Though Dark Shadows Fall~]('
                                                         '<https://bestdori.com/info/events/229/Our-Afterglow-Despite'
                                                         '-Even-the-Darkest-Shadows>)', inline=False)
        gamecrash_embed.add_field(name='March 27', value='<:PasupareLogo:432981125455937536><:attrPure:432978922892820495> Mission Live Event [Bloom in the '
                                                         'Wilds, O Flowery Maidens]('
                                                         '<https://bestdori.com/info/events/231/Bloom-in-the'
                                                         '-Wasteland-Maidens-of-Flower>)', inline=False)
        gamecrash_content = {
            'label': 'Upcoming Event Schedule',
            'style': discord.ButtonStyle.primary,
            'custom_id': f'{pubcord.id}:gamecrash',
            'content': gamecrash_embed
        }

        view_content = [newcontent_content, gamecrash_content]
        self.views[str(pubcord.id)] = AnnouncementBulletin(view_content)
        new_message = await channel.send("Access quick links by clicking the buttons below!",
                                         view=self.views[str(pubcord.id)])
        log.info('initial posted')
        await db.servers.update_one({"server_id": 432379300684103699}, {"$set": {'prev_message': new_message.id}})

    @tasks.loop(seconds=5.0)
    async def check_announcementbulletins(self):
        # pubcord currently hardcoded, eventually expand feature (todo)
        self.check_count += 1
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message']:
            message_id = document['prev_message']
            try:
                prev_message = await channel.fetch_message(int(message_id))
                # log.info(f'Channel last message id: {channel.last_message_id}')
                # log.info(f'Previous message id: {prev_message.id}')
                if channel.last_message_id != prev_message.id:
                    log.info(f'prev_message: {prev_message.id}')
                    await prev_message.delete()
                    log.info(f'deleted previous announcement bulletin for {pubcord.name}')

                    new_message = await channel.send("Access quick links by clicking the buttons below!",
                                                     view=self.views[str(pubcord.id)])
                    log.info('posted')
                    await db.servers.update_one({"server_id": 432379300684103699},
                                                {"$set": {'prev_message': new_message.id}})
            except discord.NotFound:
                log.info(f'could not find previous announcement bulletin for {pubcord.name}')

                new_message = await channel.send("Access quick links by clicking the buttons below!",
                                                 view=self.views[str(pubcord.id)])
                log.info('posted')
                await db.servers.update_one({"server_id": 432379300684103699},
                                            {"$set": {'prev_message': new_message.id}})
            except discord.Forbidden:
                log.error('Permission Error while attempting to delete stale announcement bulletin')
            except discord.HTTPException:
                pass

    @tasks.loop(hours=24)
    async def update_pubcord_quicklinks(self):
        log.info(f'Updating quicklinks - check count is currently {self.check_count}')
        new_embed = await self.generate_current_event()
        if isinstance(new_embed, discord.Embed):
            view = self.views['432379300684103699']
            old_embed = view.children[0].content
            view.children[0].content = new_embed
            if old_embed.image.url:
                new_embed.set_image(url=old_embed.image.url)

            document = await db.servers.find_one({"server_id": 432379300684103699})
            pubcord = self.bot.get_guild(432379300684103699)
            channel = pubcord.get_channel(913958768105103390)
            if document['prev_message']:
                message_id = document['prev_message']
                try:
                    prev_message = await channel.fetch_message(int(message_id))
                    log.info(f'prev_message: {prev_message.id}')
                    await prev_message.delete()
                    log.info(f'deleted previous announcement bulletin for {pubcord.name}')
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    log.error('Permission Error while attempting to delete stale announcement bulletin')
                    pass
                except discord.HTTPException:
                    pass
            new_message = await channel.send("Access quick links by clicking the buttons below!",
                                             view=self.views[str(pubcord.id)])
            log.info(f'posted announcement bulletin for {pubcord.name}')
            await db.servers.update_one({"server_id": 432379300684103699},
                                        {"$set": {'prev_message': new_message.id}})

    @tasks.loop(seconds=120)
    async def check_boosters(self):
        log.info('Running Pubcord Booster Role Parity Check')
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        emoteserver = self.bot.get_guild(815821301700493323)
        pubcord_booster_role = pubcord.get_role(913239378598436966)
        for member in pubcord.premium_subscribers:
            if not member.get_role(913239378598436966):
                log.info('Adding member to booster role - boosting main server')
                roles = member.roles
                roles.append(pubcord_booster_role)
                await member.edit(roles=roles, reason="Boosting main server")

        for member in emoteserver.premium_subscribers:
            pubcord_member = pubcord.get_member(member.id)
            if pubcord_member:
                if not pubcord_member.get_role(913239378598436966):
                    log.info('Adding member to booster role - boosting emote server')
                    roles = pubcord_member.roles
                    roles.append(pubcord_booster_role)
                    await pubcord_member.edit(roles=roles, reason="Boosting emote server")

        for member in pubcord_booster_role.members:
            emoteserver_member = emoteserver.get_member(member.id)
            if emoteserver_member:
                if emoteserver_member not in emoteserver.premium_subscribers:
                    if member not in pubcord.premium_subscribers:
                        boosting = False
                        if not boosting:
                            log.info('Not boosting either server, removing')
                            roles = member.roles
                            roles.remove(pubcord_booster_role)
                            await member.edit(roles=roles, reason="No longer boosting main OR emote server")
            else:
                if member not in pubcord.premium_subscribers:
                    boosting = False
                    if not boosting:
                        log.info('Not boosting either server, removing')
                        roles = member.roles
                        roles.remove(pubcord_booster_role)
                        await member.edit(roles=roles, reason="No longer boosting main OR emote server")

        log.info('Parity Check Complete')

    @check_boosters.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()
        while not self.bot.ready:
            await asyncio.sleep(2)
        pubcord_chunk = self.bot.get_guild(432379300684103699)
        emoteserver_chunk = self.bot.get_guild(815821301700493323)
        log.info('Chunking pubcord members...')
        await pubcord_chunk.chunk()
        await emoteserver_chunk.chunk()
        log.info('Chunking complete')

    @init_announcementbulletins.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()
        while not self.bot.ready:
            await asyncio.sleep(2)

    @check_announcementbulletins.before_loop
    async def wait_ready_long(self):
        await self.bot.wait_until_ready()
        while not self.bot.ready:
            await asyncio.sleep(2)
        await asyncio.sleep(10)

    @update_pubcord_quicklinks.before_loop
    async def wait_ready_long(self):
        await self.bot.wait_until_ready()
        while not self.bot.ready:
            await asyncio.sleep(2)
        await asyncio.sleep(20)

    task_maintenance = SlashCommandGroup('tasks', 'Task maintenenace')

    @task_maintenance.command(name='check',
                              description='DEV ONLY')
    @is_owner()
    async def checktasks(self,
                         ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='Current Pubcord Task Status',
                            content=(f'```Check Boosters | Iteration {self.check_boosters.current_loop}\n'
                                     f'  Failed: {self.check_boosters.failed()}\n'
                                     f'  Is Running: {self.check_boosters.is_running()}\n\n'
                                     f'Check Announcement Bulletin | Iteration {self.check_announcementbulletins.current_loop}\n'
                                     f'  Failed: {self.check_announcementbulletins.failed()}\n'
                                     f'  Is Running: {self.check_announcementbulletins.is_running()}\n\n'
                                     f'Update Quicklinks | Iteration {self.update_pubcord_quicklinks.current_loop}\n'
                                     f'  Failed: {self.update_pubcord_quicklinks.failed()}\n'
                                     f'  Is Running: {self.update_pubcord_quicklinks.is_running()}```')))

    @task_maintenance.command(name='restart',
                              description='DEV ONLY')
    @is_owner()
    async def restarttasks(self,
                           ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer()
        if self.check_boosters.failed():
            self.check_boosters.restart()
        if self.check_announcementbulletins.failed():
            self.check_announcementbulletins.restart()
        if self.update_pubcord_quicklinks.failed():
            self.update_pubcord_quicklinks.restart()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='tasks restart',
                            content=f'Tasks restarted.'),
            ephemeral=True)

    @discord.slash_command(name='spselfassign',
                           description='Special Role Self-Assign',
                           guild_ids=[432379300684103699])
    @default_permissions(manage_roles=True)
    async def spselfassign(self,
                           ctx: discord.ApplicationContext,
                           role: Option(discord.SlashCommandOptionType.role, 'Role to set for self-assign'),
                           channel: Option(discord.SlashCommandOptionType.channel, 'Channel to post button in')):
        await ctx.interaction.response.defer()
        if self.view_anni:
            self.view_anni.stop()
        self.view_anni = SpecialRole(role.name, ctx.interaction.guild_id, role)
        await channel.send(embed=gen_embed(title=f'{role.name} Role',
                                           content='Click the button below to add the role. '
                                                   'Click it again to remove it.'),
                           view=self.view_anni)
        await ctx.interaction.followup.send(embed=gen_embed(title='Special Self Assign',
                                                            content='Special role self assign has been created!'))

    @discord.slash_command(name='hololive',
                           description='Hololive Announcement',
                           guild_ids=[432379300684103699])
    @default_permissions(manage_roles=True)
    async def hololive(self,
                       ctx: discord.ApplicationContext):
        await ctx.respond(content=('<:hololive:1011477576558055465> <:hololive:1011477576558055465>'
                                    ' ***THE HOLOLIVE COLLAB HAS:*** '
                                    '<:hololive:1011477576558055465> <:hololive:1011477576558055465> \n'
                                    '⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️ ⬇️\n'
                                    '<a:siren:101147757820545115> ***__`NO EVENT, NO GACHA BANNER`__*** <a:siren:1011477577820545115>\n'
                                    '⬆️ ⬆️ ⬆️ ⬆️ ⬆️ ⬆️ ⬆️ ⬆️ ⬆️ ⬆️\n'
                                    '**ONLY COSTUMES AND COVERS**\n'
                                    '**AND SOME OTHER COOL COSMETIC THINGS**\n'
                                    '<a:mc_fire:1011477578860736512> <a:mc_fire:1011477578860736512>'
                                    '<a:mc_fire:1011477578860736512> <a:mc_fire:1011477578860736512>'
                                    '<a:mc_fire:1011477578860736512> <a:mc_fire:1011477578860736512>'
                                    '<a:mc_fire:1011477578860736512> <a:mc_fire:1011477578860736512>'
                                    '<a:mc_fire:1011477578860736512> <a:mc_fire:1011477578860736512>'
                                    '<a:mc_fire:1011477578860736512>'))

    @discord.slash_command(name='embedimage',
                           description='Set the embed image for the new content quicklink',
                           guild_ids=[432379300684103699])
    @default_permissions(manage_guild=True)
    async def embedimage(self,
                         ctx: discord.ApplicationContext,
                         url: Option(str, 'URL of image')):
        await ctx.interaction.response.defer(ephemeral=True)
        view = self.views[str(ctx.guild_id)]
        view.children[0].content.set_image(url=url)

        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message']:
            message_id = document['prev_message']
            try:
                prev_message = await channel.fetch_message(int(message_id))
                log.info(f'prev_message: {prev_message.id}')
                await prev_message.delete()
                log.info(f'deleted previous announcement bulletin for {pubcord.name}')
            except discord.NotFound:
                pass
            except discord.Forbidden:
                log.error('Permission Error while attempting to delete stale announcement bulletin')
        new_message = await channel.send("Access quick links by clicking the buttons below!",
                                         view=self.views[str(pubcord.id)])
        log.info(f'posted announcement bulletin for {pubcord.name}')
        await db.servers.update_one({"server_id": 432379300684103699},
                                    {"$set": {'prev_message': new_message.id}})
        await ctx.interaction.followup.send('New content embed has been updated with new image!',
                                            ephemeral=True)

    @discord.slash_command(name='verify',
                           description='Verify your account to access the server.',
                           guild_ids=[432379300684103699])
    async def verify(self,
                         ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=False)
        pubcord = self.bot.get_guild(432379300684103699)
        role = pubcord.get_role(719791739367325706)
        await ctx.user.add_roles(role)
        await ctx.interaction.followup.send(embed=gen_embed(title='Verified',
                                                            content=(f'{ctx.user.mention} has been added'
                                                                     f' to role {role.mention}')),
                                            ephemeral=True)


def setup(bot):
    bot.add_cog(Pubcord(bot))
