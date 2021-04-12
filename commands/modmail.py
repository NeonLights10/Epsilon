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

    @commands.command(name = 'modmail',
                    description = 'Start a modmail. A modmail channel must be configured first before using this command.\nUse \%serverconfig modmail [channel]',
                    help = 'Usage:\n\n\%modmail [recipient_id] [message]\nIf you are sending it to a server, the recipient id will be the server id.\nIf you are a mod sending it to a user, the recipient id will be the user id (will also accept mention and name+discriminator)')
    async def modmail(self, ctx, recipient_id: Union[discord.Guild, discord.User], *, content: str):

        if isinstance(recipient_id, discord.Guild):
            document = await db.servers.find_one({"server_id": recipient_id.id})
            if document['modmail_channel']:
                embed = gen_embed(name = f'{ctx.author.name}#{ctx.author.discriminator}', icon_url = ctx.author.avatar_url, title = 'New Modmail', content = f'{content}\n\nYou may reply to this modmail using the reply function.')
                embed.set_footer(text = f'{ctx.author.id}')
                channel = discord.utils.find(lambda c: c.id == document['modmail_channel'], recipient_id.channels)
                await channel.send(embed = embed)
                await ctx.send(embed = gen_embed(title = 'Modmail sent', content = 'The moderators will review your message and get back to you shortly.'))
            else:
                log.warning("Error: Modmail is Disabled")
                await ctx.send(embed = gen_embed(title = 'Disabled Command', content = 'Sorry, modmail is disabled.'))

        elif isinstance(recipient_id, discord.User):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                embed = gen_embed(name = f'{ctx.author.name}#{ctx.author.discriminator}', icon_url = ctx.author.avatar_url, title = 'New Modmail', content = f'{content}\n\nYou may reply to this modmail using the reply function.')
                embed.set_footer(text = f'{ctx.guild.id}')
                dm_channel = recipient_id.dm_channel
                if recipient_id.dm_channel is None:
                    dm_channel = await recipient_id.create_dm()
                await dm_channel.send(embed = embed)
                await ctx.send(embed = gen_embed(title = 'Modmail sent', content = f'Sent modmail to {recipient_id.name}#{recipient_id.discriminator}.'))
            else:
                log.warning("Error: Modmail is Disabled")
                await ctx.send(embed = gen_embed(title = 'Disabled Command', content = 'Sorry, modmail is disabled.'))

def setup(bot):
    bot.add_cog(Modmail(bot))