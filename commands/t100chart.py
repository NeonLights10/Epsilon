import discord
import traceback
import asyncio
import pymongo
import datetime
import pytz

from typing import Union, Optional, Literal
from datetime import timedelta
from discord.ext import commands, tasks
from formatting.constants import UNITS
from formatting.embed import gen_embed, embed_splitter
from __main__ import log, db

class PersistentEvent(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Send t100 Screenshot",
        style=discord.ButtonStyle.secondary,
        custom_id="persistent_view:t100charthub",
    )
    async def currentevent(self, button: discord.ui.Button, interaction: discord.Interaction):
        async def message_content_prompt(listen_channel: discord.DMChannel):
            def check(m):
                return m.author == interaction.user and m.channel == listen_channel

            await listen_channel.send(embed=gen_embed(title='Send a t100 Screenshot',
                                                      content='Please attach your screenshots below and send. You can send images by adding an attachement to the message you send.'))
            try:
                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
            except asyncio.TimeoutError:
                await listen_channel.send(embed=gen_embed(title='Sending Cancelled',
                                                          content='The operation has been cancelled.'))
                return None
            return mmsg

        await interaction.response.defer()
        log.info('Begin screenshot interaction workflow')
        dm_channel = interaction.user.dm_channel
        if not dm_channel:
            dm_channel = await interaction.user.create_dm()
        message_content = await message_content_prompt(dm_channel)

        if message_content:
            log.info('Message detected from user')
            view = Confirm()
            sent_message = await dm_channel.send(embed=gen_embed(title='Are you sure you want to send this?',
                                                                 content='Please verify the contents before confirming.'),
                                                 view=view)
            timeout = await view.wait()
            if timeout:
                log.info('Confirmation view timed out')
                for item in view.children:
                    item.disabled = True
                    await sent_message.edit(embed=gen_embed(title='Are you sure you want to send this?',
                                                            content='Please verify the contents before confirming.'),
                                            view=view)
                    return
            await sent_message.edit(embed=gen_embed(title='Are you sure you want to send this?',
                                                    content='Please verify the contents before confirming.'),
                                    view=view)

            if view.value:
                log.info('Workflow confirm, compilation and send logic start')
                document = await db.servers.find_one({"server_id": 616088522100703241})
                if document['modmail_channel']:
                    embed = gen_embed(name=f'{message_content.author.name}#{message_content.author.discriminator}',
                                      icon_url=message_content.author.display_avatar.url,
                                      title='New Screenshot',
                                      content=f'{message_content.clean_content}\n\nYou may reply to these messages using the reply function.')
                    embed.set_footer(text=f'{message_content.author.id}')
                    server = discord.utils.find(lambda s: s.id == 616088522100703241, self.bot.guilds)
                    channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], server.channels)
                    await embed_splitter(embed=embed, destination=channel, footer=str(message_content.author.id))
                    if len(message_content.attachments) > 0:
                        attachnum = 1
                        valid_media_type = ['image/jpeg', 'image/png', 'image/svg+xml', 'image/avif', 'image/heif',
                                            'image/bmp', 'image/gif', 'image/vnd.mozilla.apng', 'image/tiff']
                        for attachment in message_content.attachments:
                            if attachment.content_type in valid_media_type:
                                embed = gen_embed(
                                    name=f'{message_content.author.name}#{message_content.author.discriminator}',
                                    icon_url=message_content.author.display_avatar.url, title='Attachment',
                                    content=f'Attachment #{attachnum}:')
                                embed.set_image(url=attachment.url)
                                embed.set_footer(text=f'{message_content.author.id}')
                                await channel.send(embed=embed)
                                attachnum += 1
                            else:
                                await dm_channel.send(content=f'Attachment #{attachnum} is not a supported media type.')
                                await channel.send(embed=gen_embed(
                                    name=f'{message_content.author.name}#{message_content.author.discriminator}',
                                    icon_url=message_content.author.display_avatar.url, title='Attachment Failed',
                                    content=f'The user attempted to send an attachement that is not a supported media type.'))
                                attachnum += 1
                    await channel.send(content=f"{message_content.author.mention}")
                    await dm_channel.send(embed=gen_embed(title='Screenshots sent',
                                                          content='Thank your for your contribution!'))
                else:
                    log.warning("Error: This feature is Disabled")
                    await dm_channel.send(embed=gen_embed(title='Disabled Command', content='Sorry, this feature is disabled.'))

# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        #await interaction.response.send_message("Confirming", ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        log.info('Workflow cancelled')
        await interaction.response.send_message("Operation cancelled.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = False
        self.stop()

class Collection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.sendscreenshot_button.start()
        self.checkscreenshot_button.start()
        self.check_removescreenshot_button.start()

    def cog_unload(self):
        self.sendscreenshot_button.cancel()
        self.checkscreenshot_button.cancel()
        self.check_removescreenshot_button.cancel()


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

    @tasks.loop(seconds=1.0, count=1)
    async def sendscreenshot_button(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        end_of_event_tz = document['end_of_event'].replace(tzinfo=datetime.timezone.utc)
        if document['prev_message_screenshot']:
            if end_of_event_tz < datetime.datetime.now(datetime.timezone.utc):
                message_id = document['prev_message_screenshot']
                prev_message = await channel.fetch_message(int(message_id))
                await prev_message.delete()
                log.info('initial deleted')
        if end_of_event_tz < datetime.datetime.now(datetime.timezone.utc):
            self.view = PersistentEvent(bot=self.bot)
            if document['prev_message_screenshot']:
                missing = document['missing']
            else:
                missing = "1-100"
            new_message = await channel.send(f"We’re collecting T100 ranking screenshots for the most recent event.\nMissing: {missing}", view=self.view)
            log.info('initial posted')
            await db.servers.update_one({"server_id": 432379300684103699}, {"$set": {'prev_message_screenshot': new_message.id, 'missing': missing}})

    @tasks.loop(seconds=300)
    async def checkscreenshot_button(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if not document['prev_message_screenshot']:
            end_of_event_tz = document['end_of_event'].replace(tzinfo=datetime.timezone.utc)
            current_timedelta = end_of_event_tz - datetime.datetime.now(datetime.timezone.utc)
            if end_of_event_tz < datetime.datetime.now(datetime.timezone.utc) and current_timedelta < timedelta(days=2):
                self.view = PersistentEvent(bot=self.bot)
                missing = "1-100"
                new_message = await channel.send(
                    f"We’re collecting T100 ranking screenshots for the most recent event.\nMissing: {missing}",
                    view=self.view)
                log.info('initial posted')
                await db.servers.update_one({"server_id": 432379300684103699},
                                            {"$set": {'prev_message_screenshot': new_message.id, 'missing': missing}})

    @tasks.loop(seconds=300)
    async def check_removescreenshot_button(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message_screenshot']:
            end_of_event_tz = document['end_of_event'].replace(tzinfo=datetime.timezone.utc)
            current_timedelta = end_of_event_tz - datetime.datetime.now(datetime.timezone.utc)
            if current_timedelta > timedelta(days=2):
                message_id = document['prev_message_screenshot']
                prev_message = await channel.fetch_message(int(message_id))
                await prev_message.delete()
                log.info('event timestamp exceeded, screenshot button deleted')
                await db.servers.update_one({"server_id": 432379300684103699},
                                            {"$set": {'prev_message_screenshot': None}})

    @sendscreenshot_button.before_loop
    @check_removescreenshot_button.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    @checkscreenshot_button.before_loop
    async def wait_ready_long(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)

    #command to set end of event
    @commands.command(name='endofevent',
                      description='Set the end of event for automated operations.',
                      help='Usage:\n\n%endofevent <unix_timestamp>')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole(), in_pubcord())
    async def endofevent(self, ctx, unix_timestamp: int):
        end_date = datetime.datetime.fromtimestamp(unix_timestamp, datetime.timezone.utc)
        await db.servers.update_one({"server_id": 432379300684103699},
                                    {"$set": {'end_of_event': end_date}})
        await ctx.send(f'End of event set to <t:{unix_timestamp}>')

    #command to edit missing
    @commands.command(name='missing',
                      description='Change the description for missing t100 screenshots. Only type in the numbers missing (see example below)',
                      help='Usage:\n\n%missing 1-10, 20-40')
    @commands.has_role(925458802734678066)
    async def missing(self, ctx, *, description: str):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(913958768105103390)
        if document['prev_message_screenshot']:
            message_id = document['prev_message_screenshot']
            prev_message = await channel.fetch_message(int(message_id))
            await prev_message.edit(content=f"We’re collecting T100 ranking screenshots for the most recent event.\nMissing: {description}")
            await ctx.send(embed=gen_embed(title='missing',
                                           content=f'Updated message content:\n\nMissing: {missing}.'))
        else:
            await ctx.send(embed=gen_embed(title='missing',
                                           content='The message is not currently up! Cannot change description.'))

def setup(bot):
    bot.add_cog(Collection(bot))