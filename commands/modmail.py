import discord
import asyncio
import time

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
        await interaction.response.send_message("Confirming", ephemeral=True)
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


class Modmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def modmail_prompt(self, interaction: discord.Interaction):
        listen_channel = interaction.channel

        def check(m):
            return m.author == interaction.user and m.channel == listen_channel

        sent_message = await interaction.response.send_message(embed=gen_embed(title='Modmail Message Contents',
                                                  content='Please type out your modmail below and send. You can send images by adding an attachement to the message you send.'))

        try:
            mmsg = await self.bot.wait_for('message', check=check, timeout=300.0)
        except asyncio.TimeoutError:
            await interaction.channel.send(embed=gen_embed(title='Modmail Cancelled',
                                                      content='The modmail has been cancelled.'))
            return None
        await sent_message.delete()
        return mmsg

    @discord.slash_command(name='modmail',
                           description='Start a modmail. A modmail channel must be configured first.\nUse %serverconfig modmail [channel]')
    async def modmail(self,
                      ctx: discord.ApplicationContext,
                      recipient: Option(discord.User, "User to send modmail to")):
        await ctx.interaction.response.defer()
        modmail_content = await self.modmail_prompt(ctx.interaction)

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
            await sent_message.edit(embed=gen_embed(title='Are you sure you want to send this?',
                                                    content='Please verify the contents before confirming.'),
                                    view=view)

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
                    embed = gen_embed(name=f'{ctx.interaction.guild.name}', icon_url=ctx.interaction.guild.icon.url, title='New Modmail',
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
                                embed = gen_embed(name=f'{ctx.interaction.guild.name}', icon_url=ctx.interaction.guild.icon.url,
                                                  title='Attachment',
                                                  content=f'Attachment #{attachnum}:')
                                embed.set_image(url=attachment.url)
                                embed.set_footer(text=f'{ctx.interaction.guild.id}')
                                attachnum += 1
                                try:
                                    await dm_channel.send(embed=embed)
                                except discord.Forbidden:
                                    await ctx.send(embed=gen_embed(title='Warning',
                                                                   content='This user does not accept DMs. I could not send them the message.'))
                                    return
                            else:
                                await ctx.respond(
                                    content=f'Attachment #{attachnum} is not a supported media type ({attachment.content_type}).')
                                attachnum += 1

                    await ctx.respond(embed=gen_embed(title='Modmail sent',
                                                   content=f'Sent modmail to {recipient.name}#{recipient.discriminator}.'))
                else:
                    log.warning("Error: Modmail is Disabled")
                    await ctx.respond(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))


def setup(bot):
    bot.add_cog(Modmail(bot))
