import discord
import traceback
import asyncio
import time

from typing import Union
from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log, db


class Modmail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='modmail',
                      description='Start a modmail. A modmail channel must be configured first before using this command.\nUse %serverconfig modmail [channel]',
                      help='Usage:\n\n%modmail [recipient_id] [message]\nIf you are sending it to a server, the recipient id will be the server id.\nIf you are a mod sending it to a user, the recipient id will be the user id (will also accept mention and name+discriminator)')
    async def modmail(self, ctx, recipient_id: Union[discord.Guild, discord.User], *, content: str):
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

        if isinstance(recipient_id, discord.Guild):
            document = await db.servers.find_one({"server_id": recipient_id.id})
            if document['modmail_channel']:
                embed = gen_embed(name=f'{ctx.author.name}#{ctx.author.discriminator}', icon_url=ctx.author.display_avatar.url,
                                  title='New Modmail',
                                  content=f'{content}\n\nYou may reply to this modmail using the reply function.')
                embed.set_footer(text=f'{ctx.author.id}')
                channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], recipient_id.channels)
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
                await ctx.send(embed=gen_embed(title='Modmail sent',
                                               content='The moderators will review your message and get back to you shortly.'))
            else:
                log.warning("Error: Modmail is Disabled")
                await ctx.send(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))

        elif isinstance(recipient_id, discord.User):
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
                dm_channel = recipient_id.dm_channel
                if recipient_id.dm_channel is None:
                    dm_channel = await recipient_id.create_dm()
                await dm_channel.send(embed=embed)
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
                        attachnum += 1
                await ctx.send(embed=gen_embed(title='Modmail sent',
                                               content=f'Sent modmail to {recipient_id.name}#{recipient_id.discriminator}.'))
            else:
                log.warning("Error: Modmail is Disabled")
                await ctx.send(embed=gen_embed(title='Disabled Command', content='Sorry, modmail is disabled.'))


def setup(bot):
    bot.add_cog(Modmail(bot))
