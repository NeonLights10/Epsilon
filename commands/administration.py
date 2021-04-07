import discord
import traceback
import re
import time
import validators
import datetime

from datetime import timedelta
from typing import Union, Optional
from discord.ext import commands
from formatting.constants import UNITS
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
            log.warning("PermissionError: Insufficient Permissions")
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
                    log.warning("Error: Role Not Found")
                    await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))
                else:
                    log.warning("Error: Invalid input")
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Accepted options: "disable"'))
            else:
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': roleid.id}})
                await ctx.send(embed = gen_embed(title = 'autorole', content = f'Enabled autorole with role {roleid.name} for {ctx.guild.name}'))
        else:
            log.warning("PermissionError: Insufficient Permissions")
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
                    log.warning("Error: Channel Not Found")
                    await ctx.send(embed = gen_embed(title = 'Channel Not Found', content = 'Please doublecheck the id or try a channel mention.'))
                else:
                    log.warning("Error: Invalid input")
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Accepted options: "disable"'))
            else:
                if channel_option == "log":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': channel_id.id}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
                if channel_option == "welcome":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': channel_id.id}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
        else:
            log.warning("PermissionError: Insufficient Permissions")
            await ctx.send(embed = gen_embed(title='Permissions Error', content = 'You do not have permission to run this command.'))

    @commands.command(name = 'welcomeconfig',
                    description = 'Set the welcome message and optional banner. Enclose the message in quotes.',
                    help = 'Usage\n\n^welcomeconfig "[message]" <url>')
    async def welcomeconfig(self, ctx, url: str = None, *, welcome_message):
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        hasperm = False
        if document['modrole']:
            role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
            if role in ctx.author.roles:
                hasperm = True            
        if hasperm or ctx.message.author.guild_permissions.manage_guild:
            clean_welcome_message = re.sub('<@!?&?\d{17,18}>', '[removed mention]', welcome_message)
            if url:
                if validators.url(url):
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_message': welcome_message, 'welcome_banner': url}})
                    embed = gen_embed(title = 'welcomeconfig', content = f"Welcome message set for {ctx.guild.name}: {welcome_message}")
                    embed.set_image(url)
                    await ctx.send(embed = embed)
                else:
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = "Invalid URL. Check the formatting (https:// prefix is required)"))
            else:
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_message': welcome_message}})
                await ctx.send(embed = gen_embed(title = 'welcomeconfig', content = f"Welcome message set for {ctx.guild.name}: {welcome_message}"))
        else:
            log.warning("PermissionError: Insufficient Permissions")
            await ctx.send(embed = gen_embed(title='Permissions Error', content = 'You do not have permission to run this command.'))

    @commands.command(name = 'purge',
                    description = 'Deletes the previous # of messages from the channel. Specifying a user will delete the messages for that user. Specifying a time will delete messages from the past x amount of time. You can also reply to a message to delete messages after the one replied to.',
                    help = 'Usage\n\n^purge <userid/user mention> <num> <time>')
    async def msgpurge(self, ctx, members: commands.Greedy[discord.Member], num: Optional[int], time: Optional[Union[discord.Message, str]]):
        def convert_to_timedelta(s):
                    return timedelta(**{UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val')) for m in re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)})

        async def delete_messages(limit = None, check = None, before = None, after = None):
            try:
                deleted = await ctx.channel.purge(limit = limit, check = check, before = before, after = after)
                if check:
                    await ctx.send(embed = gen_embed(title = 'purge', content = f'The last {len(deleted) - 1} messages by {member.name}#{member.discriminator} were deleted.'))
                else:
                    await ctx.send(embed = gen_embed(title = 'purge', content = f'The last {len(deleted)} messages were deleted.'))
            except discord.Forbidden:
                log.error("PermissionError: Bot does not have sufficient permissions. Check roles?")
                await ctx.send(embed = gen_embed(title = 'purge', content = "It seems like I don't have the permissions to do that. Check your server settings."))

        time = time or ctx.message.reference    
        
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        hasperm = False
        if document['modrole']:
            role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
            if role in ctx.author.roles:
                hasperm = True            
        if hasperm or ctx.message.author.guild_permissions.manage_messages:
            if members:
                for member in members:
                    def user_check(m):
                        return m.author == member
                    if num:
                        if num < 0:
                            log.warning("Error: Invalid input")
                            await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Please pick a number > 0.'))
                        else:
                            if time:
                                after_value = datetime.datetime.utcnow()
                                if isinstance(time, str):
                                    after_value = after_value - convert_to_timedelta(time)
                                elif isinstance(time, discord.MessageReference):
                                    after_value = await ctx.channel.fetch_message(time.message_id)

                                await delete_messages(limit = num + 1, check = user_check, after = after_value)
                                return
                            else:
                                await delete_messages(limit = num + 1, check = user_check)
                                return
                    elif time:
                        after_value = datetime.datetime.utcnow()
                        if isinstance(time, str):
                            after_value = after_value - convert_to_timedelta(time)
                        elif isinstance(time, discord.MessageReference):
                                    after_value = await ctx.channel.fetch_message(time.message_id)

                        await delete_messages(check = user_check, after = after_value)
                        return

            elif num:
                if num < 0:
                    log.warning("Error: Invalid input")
                    await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Please pick a number > 0.'))
                else:
                    if time:
                        after_value = datetime.datetime.utcnow()
                        if isinstance(time, str):
                            after_value = after_value - convert_to_timedelta(time)
                        elif isinstance(time, discord.MessageReference):
                            after_value = await ctx.channel.fetch_message(time.message_id)

                        await delete_messages(limit = num, after = after_value)
                        return

                    else:
                        await delete_messages(limit = num, before = ctx.message)
                        return

            elif time:
                after_value = datetime.datetime.utcnow()
                if isinstance(time, str):
                    after_value = after_value - convert_to_timedelta(time)
                elif isinstance(time, discord.MessageReference):
                            after_value = await ctx.channel.fetch_message(time.message_id)

                await delete_messages(after = after_value)
                return
            else:
                log.warning("missingrequiredargument")
                raise commands.MissingRequiredArgument("eeeeeeeeee")
        else:
            log.warning("PermissionError: Insufficient Permissions")
            await ctx.send(embed = gen_embed(title='Permissions Error', content = 'You do not have permission to run this command.')) 

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