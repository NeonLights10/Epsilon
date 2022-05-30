import discord
import asyncio

from discord.ext import commands, tasks
from discord.commands import Option
from formatting.embed import gen_embed, embed_splitter
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
        await interaction.response.defer()
        # await interaction.response.send_message("Confirming", ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        log.info('Workflow cancelled')
        await interaction.response.send_message("Modmail cancelled.", ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = False
        self.stop()


class ModmailButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Send a modmail!",
        style=discord.ButtonStyle.primary,
        custom_id="modmailbutton:sendmodmail",
    )
    async def send_modmail(self, button: discord.ui.Button, interaction: discord.Interaction):
        async def modmail_prompt(listen_channel: discord.DMChannel):
            def check(m):
                return m.author == interaction.user and m.channel == listen_channel

            try:
                await listen_channel.send(embed=gen_embed(title='Modmail Message Contents',
                                                          content='Please type out your modmail below and send. You can send images by adding an attachement to the message you send.'))
            except discord.Forbidden:
                raise RuntimeError('Forbidden 403 - could not send direct message to user.')

            try:
                mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
            except asyncio.TimeoutError:
                await listen_channel.send(embed=gen_embed(title='Modmail Cancelled',
                                                          content='The modmail has been cancelled.'))
                return None
            return mmsg

        await interaction.response.defer()
        log.info('Begin modmail interaction workflow')
        dm_channel = interaction.user.dm_channel
        if not dm_channel:
            dm_channel = await interaction.user.create_dm()
        modmail_content = await modmail_prompt(dm_channel)

        if modmail_content:
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
            await sent_message.delete()

            if view.value:
                log.info('Workflow confirm, compilation and send logic start')
                document = await db.servers.find_one({"server_id": interaction.guild.id})
                if document['modmail_channel']:
                    embed = gen_embed(name=f'{modmail_content.author.name}#{modmail_content.author.discriminator}',
                                      icon_url=modmail_content.author.display_avatar.url,
                                      title='New Modmail',
                                      content=f'{modmail_content.clean_content}\n\nYou may reply to this modmail using the reply function.')
                    embed.set_footer(text=f'{modmail_content.author.id}')
                    channel = discord.utils.find(lambda c: c.id == document['modmail_channel'],
                                                 interaction.guild.channels)
                    await embed_splitter(embed=embed, destination=channel, footer=str(modmail_content.author.id))
                    if len(modmail_content.attachments) > 0:
                        attachnum = 1
                        valid_media_type = ['image/jpeg', 'image/png', 'image/svg+xml', 'image/avif', 'image/heif',
                                            'image/bmp', 'image/gif', 'image/vnd.mozilla.apng', 'image/tiff']
                        for attachment in modmail_content.attachments:
                            if attachment.content_type in valid_media_type:
                                embed = gen_embed(
                                    name=f'{modmail_content.author.name}#{modmail_content.author.discriminator}',
                                    icon_url=modmail_content.author.display_avatar.url, title='Attachment',
                                    content=f'Attachment #{attachnum}:')
                                embed.set_image(url=attachment.url)
                                embed.set_footer(text=f'{modmail_content.author.id}')
                                await channel.send(embed=embed)
                                attachnum += 1
                            else:
                                await dm_channel.send(content=f'Attachment #{attachnum} is not a supported media type.')
                                await channel.send(embed=gen_embed(
                                    name=f'{modmail_content.author.name}#{modmail_content.author.discriminator}',
                                    icon_url=modmail_content.author.display_avatar.url, title='Attachment Failed',
                                    content=f'The user attempted to send an attachement that is not a supported media type ({attachment.content_type}).'))
                                attachnum += 1
                    if len(modmail_content.stickers) > 0:
                        for sticker in modmail_content.stickers:
                            embed = gen_embed(
                                name=f'{modmail_content.author.name}#{modmail_content.author.discriminator}',
                                icon_url=modmail_content.author.display_avatar.url,
                                title='Sticker',
                                content=f'Attached sticker:')
                            embed.set_image(url=sticker.url)
                            embed.set_footer(text=f'{modmail_content.author.id}')
                            try:
                                await channel.send(embed=embed)
                            except discord.Forbidden:
                                await dm_channel.send(embed=gen_embed(title='Warning',
                                                                      content='I ran into a permission error while '
                                                                              'sending the sticker.'))
                                break
                    await channel.send(content=f"{modmail_content.author.mention}")
                    await dm_channel.send(embed=gen_embed(title='Modmail sent',
                                                          content='The moderators will review your message and get back to you shortly.'))
                else:
                    log.warning("Error: Modmail is Disabled")
                    await dm_channel.send(
                        embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))


class Modmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.view = None
        self.modmail_button.start()

    @tasks.loop(minutes=30)
    async def modmail_button(self):
        async for document in db.servers.find({'modmail_button_channel': {'$ne': True}}):
            if document['modmail_button_channel']:
                server = self.bot.get_guild(document['server_id'])
                channel = server.get_channel(document['modmail_button_channel'])
                if button_message_id := document['prev_message_modmail']:
                    last_message_id = channel.last_message_id
                    try:
                        prev_button_message = await channel.fetch_message(int(button_message_id))
                        if int(button_message_id) != last_message_id:
                            await prev_button_message.delete()
                            log.info('initial deleted')
                            await self.init_modmail_button(server.id)
                        else:
                            self.view = ModmailButton(bot=self.bot)
                            await prev_button_message.edit("Send a modmail to us by pressing the button below.",
                                                           view=self.view)
                    except discord.NotFound:
                        await self.init_modmail_button(server.id)
                else:
                    await self.init_modmail_button(server.id)

    async def init_modmail_button(self, server_id):
        document = await db.servers.find_one({"server_id": server_id})
        server = self.bot.get_guild(document['server_id'])
        if document['modmail_button_channel']:
            channel = server.get_channel(document['modmail_button_channel'])
            self.view = ModmailButton(bot=self.bot)
            new_message = await channel.send("Send a modmail to us by pressing the button below.", view=self.view)
            log.info('initial posted')
            await db.servers.update_one({"server_id": server_id},
                                        {"$set": {'prev_message_modmail': new_message.id}})

    @modmail_button.before_loop
    async def wait_ready(self):
        # log.info('wait till ready')
        await self.bot.wait_until_ready()

    async def modmail_prompt(self, ctx: discord.ApplicationContext):
        listen_channel = ctx.interaction.channel

        def check(m):
            return m.author == ctx.interaction.user and m.channel == listen_channel

        sent_message = await listen_channel.send(embed=gen_embed(title='Modmail Message Contents',
                                                                 content='Please type out your modmail below and send. You can send images by adding an attachement to the message you send.'))

        try:
            mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
        except asyncio.TimeoutError:
            await ctx.respond(embed=gen_embed(title='Modmail Cancelled',
                                              content='The modmail has been cancelled.'))
            return None
        await sent_message.delete()
        return mmsg

    @discord.slash_command(name='modmail',
                           description='Start a modmail. A modmail channel must be configured first.\nUse %serverconfig modmail [channel]')
    async def modmail(self,
                      ctx: discord.ApplicationContext,
                      recipient: Option(discord.User, "User to send modmail to")):
        if not ctx.interaction.response.is_done():
            await ctx.interaction.response.defer()
        modmail_content = await self.modmail_prompt(ctx)

        if modmail_content:
            log.info('Message detected from user')
            view = Confirm()
            sent_message = await ctx.interaction.followup.send(
                embed=gen_embed(title='Are you sure you want to send this?',
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
            await sent_message.delete()

            if view.value:
                # if isinstance(ctx.channel, discord.TextChannel):
                #     document = await db.servers.find_one({"server_id": ctx.guild.id})
                #     role = None
                #     if document['modrole']:
                #         role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                #     permissions = ctx.channel.permissions_for(ctx.author)
                #     if role:
                #         if role not in ctx.author.roles:
                #             if permissions.manage_messages is False:
                #                 log.warning("Permission Error")
                #                 await ctx.send(embed=gen_embed(title='Error',
                #                                                content='Sorry, modmail does not work in regular text channels! Please use this command in a DM with me.'))
                #                 log.warning("Error: modmail attempted to be sent from text channel")
                #                 return
                #     elif permissions.manage_messages is False:
                #         log.warning("Permission Error")
                #         await ctx.send(embed=gen_embed(title='Error',
                #                                        content='Sorry, modmail does not work in regular text channels! Please use this command in a DM with me.'))
                #         log.warning("Error: modmail attempted to be sent from text channel")
                #         return

                try:
                    document = await db.servers.find_one({"server_id": ctx.interaction.guild_id})
                except AttributeError:
                    await ctx.respond(embed=gen_embed(title='Modmail error',
                                                      content="It seems like you're trying to create and send a modmail to a specific user. Please send this from the server and not from DMs."))
                    return
                if document['modmail_channel']:
                    embed = gen_embed(name=f'{ctx.interaction.guild.name}', icon_url=ctx.interaction.guild.icon.url,
                                      title='New Modmail',
                                      content=f'{modmail_content.clean_content}\n\nYou may reply to this modmail using the reply function.')
                    embed.set_footer(text=f'{ctx.interaction.guild.id}')
                    dm_channel = recipient.dm_channel
                    if recipient.dm_channel is None:
                        dm_channel = await recipient.create_dm()
                    try:
                        await embed_splitter(embed=embed, destination=dm_channel, footer=str(ctx.interaction.guild.id))
                    except discord.Forbidden:
                        await ctx.respond(embed=gen_embed(title='Warning',
                                                          content='This user does not accept DMs. I could not send them the message.'))
                        return
                    if len(modmail_content.attachments) > 0:
                        attachnum = 1
                        valid_media_type = ['image/jpeg', 'image/png', 'image/svg+xml', 'image/avif', 'image/heif',
                                            'image/bmp', 'image/gif', 'image/vnd.mozilla.apng', 'image/tiff']
                        for attachment in modmail_content.attachments:
                            if attachment.content_type in valid_media_type:
                                embed = gen_embed(name=f'{ctx.interaction.guild.name}',
                                                  icon_url=ctx.interaction.guild.icon.url,
                                                  title='Attachment',
                                                  content=f'Attachment #{attachnum}:')
                                embed.set_image(url=attachment.url)
                                embed.set_footer(text=f'{ctx.interaction.guild_id}')
                                attachnum += 1
                                try:
                                    await dm_channel.send(embed=embed)
                                except discord.Forbidden:
                                    await ctx.send(embed=gen_embed(title='Warning',
                                                                   content='This user does not accept DMs. I could not send them the attachment.'))
                                    break
                            else:
                                await ctx.respond(
                                    content=f'Attachment #{attachnum} is not a supported media type ({attachment.content_type}).')
                                attachnum += 1
                    if len(modmail_content.stickers) > 0:
                        for sticker in modmail_content.stickers:
                            embed = gen_embed(name=f'{ctx.interaction.guild.name}',
                                              icon_url=ctx.interaction.guild.icon.url,
                                              title='Sticker',
                                              content=f'Attached sticker:')
                            embed.set_image(url=sticker.url)
                            embed.set_footer(text=f'{ctx.interaction.guild_id}')
                            try:
                                await dm_channel.send(embed=embed)
                            except discord.Forbidden:
                                await ctx.send(embed=gen_embed(title='Warning',
                                                               content='This user does not accept DMs. I could not send them the sticker.'))
                                break
                    await ctx.respond(embed=gen_embed(title='Modmail sent',
                                                      content=f'Sent modmail to {recipient.name}#{recipient.discriminator}.'))
                else:
                    log.warning("Error: Modmail is Disabled")
                    await ctx.respond(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))


def setup(bot):
    bot.add_cog(Modmail(bot))
