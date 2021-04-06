import discord
import traceback
import re
import time

from typing import Union
from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log, db

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'setmodrole', 
                    description = 'Sets the moderator role for this server. Only mods have access to administration commands.',
                    help = 'Usage:\n\n^setmodrole [role id/role mention]')
    async def setmodrole(self, ctx, roleid: discord.Role):
        isowner = await self.bot.is_owner(ctx.message.author)
        if ctx.message.author.guild_permissions.administrator or isowner:
            roleid = roleid or ctx.message.role_reactions[0]
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modrole': roleid.id}})
        else:
            await ctx.send(embed = gen_embed(title = 'Permissions Error', content = 'You must have administrator rights to run this command.'))

    @setmodrole.error
    async def setmodrole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))

    @commands.command(name = 'autorole',
                    description = 'Sets a role to be added whenever a user joins the server.',
                    help = 'Usage\n\n^autorole [role id/role mention or disable]')
    async def autorole(self, ctx, roleid: Union[discord.Role, str]):
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        hasperm = False
        if document['modrole']:
            role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
            if role in ctx.author.roles:
                hasperm = True          
        if hasperm or ctx.message.author.guild_permissions.manage_roles:
            roleid = roleid or ctx.message.role_reactions[0]
            if isinstance(roleid, str):
                roleid = roleid.lower()
                if roleid == "disable":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': None}})
                    await ctx.send(embed = gen_embed(title = 'autorole', content = f'Disabled autorole for {ctx.guild.name}'))
                elif not discord.utils.find(lambda r: r.id == roleid, ctx.guild.roles):
                    await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))
                else:
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Accepted options: "disable"'))
            else:
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': roleid.id}})
                await ctx.send(embed = gen_embed(title = 'autorole', content = f'Enabled autorole with role {roleid.name} for {ctx.guild.name}'))
        else:
            await ctx.send(embed = gen_embed(title='Permissions Error', content = 'You do not have permission to run this command.'))

    @autorole.error
    async def autorole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))

    @commands.command(name = 'channelconfig',
                    description = 'Set channel for logs and welcome messages.',
                    help = 'Usage\n\n^channelconfig [log/welcome] [channel id/channel mention]')
    async def channelconfig(self, ctx, channel_option: str, channel_id: Union[discord.TextChannel, str]):
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        hasperm = False
        if document['modrole']:
            role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
            if role in ctx.author.roles:
                hasperm = True            
        if hasperm or ctx.message.author.guild_permissions.manage_guild:
            valid_options = {'log', 'welcome'}
            if channel_option not in valid_options:
                await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Accepted options: "log" "welcome"'))
                return

            channel_id = channel_id or ctx.message.channel_mentions[0]
            channel_option = channel_option.lower()
            if isinstance(channel_id, str):
                channel_id = channel_id.lower()
                if channel_id == "disable":
                    if channel_option == "log":
                        await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': None}})
                        await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Disabled logging for {ctx.guild.name}'))
                    elif channel_option == "welcome":
                        await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': None}})
                        await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Disabled welcome messages for {ctx.guild.name}'))
                elif not discord.utils.find(lambda c: c.id == channel_id, ctx.guild.text_channels):
                    await ctx.send(embed = gen_embed(title = 'Channel Not Found', content = 'Please doublecheck the id or try a channel mention.'))
                else:
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Accepted options: "disable"'))
            else:
                if channel_option == "log":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': channel_id.id}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
                if channel_option == "welcome":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': channel_id.id}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        document = await db.servers.find_one({"server_id": message.guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                if not message.author.id == self.bot.user.id and message.author.bot == False:
                    if re.match('^\{}'.format(self.bot.command_prefix), message.content) == None:
                        cleanMessage = re.sub('<@!?&?\d{17,18}>', '[removed mention]', message.content)
                        logChannel = message.guild.get_channel(msglog)
                        content = discord.Embed(colour = 0x1abc9c)
                        content.set_author(name = f"{message.author.name}#{message.author.discriminator}", icon_url = message.author.avatar_url)
                        content.set_footer(text = f"UID: {message.author.id} | {time.ctime()}")
                        content.title = f"Message deleted in #{message.channel.name}"
                        content.description = f"**Message Content:** {cleanMessage}"
                        if len(message.attachments) > 0:
                            content.add_field(name = "Attachment:", value = "\u200b")
                            content.set_image(url = message.attachments[0].proxy_url)
                        await logChannel.send(embed = content)
        except: pass

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        document = await db.servers.find_one({"server_id": messages[0].guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                for message in messages:
                    if not message.author.id == self.bot.user.id and message.author.bot == False:
                        if re.match('^\{}'.format(self.bot.command_prefix), message.content) == None:
                            cleanMessage = re.sub('<@!?&?\d{17,18}>', '[removed mention]', message.content)
                            logChannel = message.guild.get_channel(msglog)
                            content = discord.Embed(colour = 0x1abc9c)
                            content.set_author(name = f"{message.author.name}#{message.author.discriminator}", icon_url = message.author.avatar_url)
                            content.set_footer(text = f"UID: {message.author.id} | {time.ctime()}")
                            content.title = f"Message deleted in #{message.channel.name}"
                            content.description = f"**Message Content:** {cleanMessage}"
                            if len(message.attachments) > 0:
                                content.add_field(name = "Attachment:", value = "\u200b")
                                content.set_image(url = message.attachments[0].proxy_url)
                            await logChannel.send(embed = content)
        except: pass

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        document = await db.servers.find_one({"server_id": before.guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                if not before.author.id == self.bot.user.id and before.author.bot == False:
                    if not before.content == after.content:
                        logChannel = before.guild.get_channel(msglog)
                        content = discord.Embed(colour = 0x1abc9c)
                        content.set_author(name = f"{before.author.name}#{before.author.discriminator}", icon_url = before.author.avatar_url)
                        content.set_footer(text = f"UID: {before.author.id} | {time.ctime()}")
                        content.title = f"Message edited in #{before.channel.name}"
                        content.description = f"**Before:** {before.clean_content}\n**After:** {after.clean_content}"
                        await logChannel.send(embed = content)
        except: pass

def setup(bot):
    bot.add_cog(Administration(bot))