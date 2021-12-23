import discord
import traceback
import asyncio
import time

from typing import Union
from discord.ext import commands, tasks
from formatting.embed import gen_embed
from __main__ import log, db

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
        await interaction.response.send_message("Modmail cancelled.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = False
        self.stop()


class PersistentEvent(discord.ui.View):
    def __init__(self, guild, bot):
        super().__init__(timeout=None)
        self.guild = guild
        self.bot = bot

    @discord.ui.button(
        label="Send a modmail!",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_view:sendmodmail",
    )
    async def send_modmail(self, button: discord.ui.Button, interaction: discord.Interaction):
        async def modmail_prompt(listen_channel: discord.DMChannel):
            def check(m):
                return m.author == interaction.user and m.channel == listen_channel

            await listen_channel.send(embed=gen_embed(title='Modmail Message Contents',
                                           content='Please type out your modmail below and send. You can send images by adding an attachement to the message you send.'))
            try:
                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
            except asyncio.TimeoutError:
                await listen_channel.send(embed=gen_embed(title='Modmail Cancelled',
                                               content='The modmail has been cancelled.'))
                return
            return mmsg

        await interaction.response.defer()
        dm_channel = interaction.user.dm_channel
        if not dm_channel:
            dm_channel = await interaction.user.create_dm()
        modmail_content = await modmail_prompt(dm_channel)

        view = Confirm()
        sent_message = await dm_channel.send(embed=gen_embed(title='Are you sure you want to send this?',
                                                          content='Please verify the contents before confirming.'),
                                          view=view)
        await view.wait()
        await sent_message.edit(embed=gen_embed(title='Are you sure you want to send this?',
                                                          content='Please verify the contents before confirming.'),
                                          view=view)

        if view.value:
            document = await db.servers.find_one({"server_id": self.guild.id})
            if document['modmail_channel']:
                embed = gen_embed(name=f'{mmsg.author.name}#{mmsg.author.discriminator}',
                                  icon_url=mmsg.author.display_avatar.url,
                                  title='New Modmail',
                                  content=f'{mmsg.clean_content}\n\nYou may reply to this modmail using the reply function.')
                embed.set_footer(text=f'{mmsg.author.id}')
                channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], self.guild.channels)
                await channel.send(embed=embed)
                if len(ctx.message.attachments) > 0:
                    attachnum = 1
                    for attachment in ctx.message.attachments:
                        embed = gen_embed(name=f'{mmsg.author.name}#{mmsg.author.discriminator}',
                                          icon_url=mmsg.author.display_avatar.url, title='Attachment',
                                          content=f'Attachment #{attachnum}:')
                        embed.set_image(url=attachment.url)
                        embed.set_footer(text=f'{mmsg.author.id}')
                        await channel.send(embed=embed)
                        attachnum += 1
                await channel.send(content=f"{mmsg.author.mention}")
                await dm_channel.send(embed=gen_embed(title='Modmail sent',
                                               content='The moderators will review your message and get back to you shortly.'))
            else:
                log.warning("Error: Modmail is Disabled")
                await dm_channel.send(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))
        else:
            await dm_channel.send(embed=gen_embed(title='Modmail Cancelled',
                                                      content='The modmail has been cancelled.'))

class Modmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.modmail_button.start()

    @tasks.loop(seconds=1.0, count=1)
    async def modmail_button(self):
        document = await db.servers.find_one({"server_id": 432379300684103699})
        pubcord = self.bot.get_guild(432379300684103699)
        channel = pubcord.get_channel(804365790412406814)
        if document['prev_message_modmail']:
            message_id = document['prev_message_modmail']
            prev_message = await channel.fetch_message(int(message_id))
            await prev_message.delete()
            log.info('initial deleted')
        self.view = PersistentEvent(guild=pubcord, bot=self.bot)
        new_message = await channel.send("Send a modmail to us by pressing the button below!", view=self.view)
        log.info('initial posted')
        await db.servers.update_one({"server_id": 432379300684103699}, {"$set": {'prev_message_modmail': new_message.id}})

    @modmail_button.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    @commands.command(name='modmail',
                      description='Start a modmail. A modmail channel must be configured first before using this command.\nUse %serverconfig modmail [channel]',
                      help='Usage:\n\n%modmail [recipient_id] [message]\nIf you are sending it to a server, the recipient id will be the server id.\nIf you are a mod sending it to a user, the recipient id will be the user id (will also accept mention and name+discriminator)')
    async def modmail(self, ctx, recipient_id: commands.Greedy[Union[discord.Guild, discord.User]], *, content: str):
        for rid in recipient_id:
            if isinstance(ctx.channel, discord.TextChannel):
                document = await db.servers.find_one({"server_id": ctx.guild.id})
                role = None
                if document['modrole']:
                    role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                permissions = ctx.channel.permissions_for(ctx.author)
                if role:
                    if role not in ctx.author.roles:
                        if permissions.manage_messages is False:
                            log.warning("Permission Error")
                            await ctx.send(embed=gen_embed(title='Error',
                                                           content='Sorry, modmail does not work in regular text channels! Please use this command in a DM with me.'))
                            log.warning("Error: modmail attempted to be sent from text channel")
                            return
                elif permissions.manage_messages is False:
                    log.warning("Permission Error")
                    await ctx.send(embed=gen_embed(title='Error',
                                                   content='Sorry, modmail does not work in regular text channels! Please use this command in a DM with me.'))
                    log.warning("Error: modmail attempted to be sent from text channel")
                    return

            if isinstance(rid, discord.Guild):
                document = await db.servers.find_one({"server_id": rid.id})
                if document['modmail_channel']:
                    embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}', icon_url=ctx.author.display_avatar.url,
                                      title='New Modmail',
                                      content=f'{content}\n\nYou may reply to this modmail using the reply function.')
                    embed.set_footer(text=f'{ctx.author.id}')
                    channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], rid.channels)
                    await channel.send(embed=embed)
                    if len(ctx.message.attachments) > 0:
                        attachnum = 1
                        for attachment in ctx.message.attachments:
                            embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}',
                                              icon_url=ctx.author.display_avatar.url, title='Attachment',
                                              content=f'Attachment #{attachnum}:')
                            embed.set_image(url=attachment.url)
                            embed.set_footer(text=f'{ctx.author.id}')
                            await channel.send(embed=embed)
                            attachnum += 1
                    await channel.send(content=f"{ctx.author.mention}")
                    await ctx.send(embed=gen_embed(title='Modmail sent',
                                                   content='The moderators will review your message and get back to you shortly.'))
                else:
                    log.warning("Error: Modmail is Disabled")
                    await ctx.send(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))

            elif isinstance(rid, discord.User):
                try:
                    document = await db.servers.find_one({"server_id": ctx.guild.id})
                except AttributeError:
                    await ctx.send(embed=gen_embed(title='Modmail error',
                                                   content="It seems like you're trying to create and send a modmail to a specific user. Please send this from the server and not from DMs."))
                    return
                if document['modmail_channel']:
                    embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url, title='New Modmail',
                                      content=f'{content}\n\nYou may reply to this modmail using the reply function.')
                    embed.set_footer(text=f'{ctx.guild.id}')
                    dm_channel = rid.dm_channel
                    if rid.dm_channel is None:
                        dm_channel = await rid.create_dm()
                    try:
                        await dm_channel.send(embed=embed)
                    except discord.Forbidden:
                        await ctx.send(embed=gen_embed(title='Warning',
                                                       content='This user does not accept DMs. I could not send them the message.'))
                        return
                    if len(ctx.message.attachments) > 0:
                        attachnum = 1
                        for attachment in ctx.message.attachments:
                            embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon.url, title='Attachment',
                                              content=f'Attachment #{attachnum}:')
                            embed.set_image(url=attachment.url)
                            embed.set_footer(text=f'{ctx.guild.id}')
                            try:
                                await dm_channel.send(embed=embed)
                            except discord.Forbidden:
                                await ctx.send(embed=gen_embed(title='Warning',
                                                               content='This user does not accept DMs. I could not send them the message.'))
                                return
                            attachnum += 1
                    await ctx.send(embed=gen_embed(title='Modmail sent',
                                                   content=f'Sent modmail to {rid.name}#{rid.discriminator}.'))
                else:
                    log.warning("Error: Modmail is Disabled")
                    await ctx.send(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))

def setup(bot):
    bot.add_cog(Modmail(bot))
