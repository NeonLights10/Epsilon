import discord
import traceback
import re
import time
import validators
import datetime
import asyncio
import pymongo

from dateutil.relativedelta import relativedelta
from datetime import timedelta
from typing import Union, Optional
from discord.ext import commands
from formatting.constants import UNITS
from formatting.embed import gen_embed
from __main__ import log, db

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
            return role in ctx.author.roles
        return commands.check(predicate)

    def is_owner():
        async def predicate(ctx):
            is_owner = await self.bot.is_owner(ctx.message.author)
            return is_owner
        return commands.check(predicate)

    @commands.command(name = 'setmodrole', 
                    description = 'Sets the moderator role for this server. Only mods have access to administration commands.',
                    help = 'Usage:\n\n^setmodrole [role id/role mention]')
    @commands.check_any(commands.has_guild_permissions(administrator = True), is_owner())
    async def setmodrole(self, ctx, roleid: discord.Role):
        roleid = roleid or ctx.message.role_reactions[0]
        await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modrole': roleid.id}})

    @setmodrole.error
    async def setmodrole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))

        elif isinstance(error, commands.CheckAnyFailure):
            log.warning("PermissionError: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Permissions Error', content = 'You must have administrator rights to run this command.'))

    @commands.command(name = 'autorole',
                    description = 'Sets a role to be added whenever a user joins the server.',
                    help = 'Usage\n\n^autorole [role id/role mention or disable]')
    @commands.check_any(commands.has_guild_permissions(manage_roles = True), has_modrole())
    async def autorole(self, ctx, roleid: Union[discord.Role, str]):
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
                await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Valid options: "disable"'))
        else:
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': roleid.id}})
            await ctx.send(embed = gen_embed(title = 'autorole', content = f'Enabled autorole with role {roleid.name} for {ctx.guild.name}'))

    @autorole.error
    async def autorole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Role Not Found', content = 'Please doublecheck the id or try a role mention.'))

        elif isinstance(error, commands.CheckAnyFailure):
            log.warning("PermissionError: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = 'Permissions Error', content = 'You must have server permissions or moderator role to run this command.'))

    @commands.command(name = 'channelconfig',
                    description = 'Set channel for logs and welcome messages.',
                    help = 'Usage\n\n^channelconfig [log/welcome/modmail] [channel id/channel mention] OR [disable] to turn off')
    @commands.check_any(commands.has_guild_permissions(manage_guild = True), has_modrole())
    async def channelconfig(self, ctx, channel_option: str, channel_id: Union[discord.TextChannel, str]):
        valid_options = {'log', 'welcome', 'modmail'}
        channel_option = channel_option.lower()
        if channel_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed = gen_embed(title = 'Input Error', content = f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        channel_id = channel_id or ctx.message.channel_mentions[0]
        if isinstance(channel_id, str):
            channel_id = channel_id.lower()
            if channel_id == "disable":
                if channel_option == "log":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': None}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Disabled logging for {ctx.guild.name}'))
                elif channel_option == "welcome":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': None}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Disabled welcome messages for {ctx.guild.name}'))
                elif channel_option == "modmail":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modmail_channel': None}})
                    await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Disabled modmail for {ctx.guild.name}'))

            elif not discord.utils.find(lambda c: c.id == channel_id, ctx.guild.text_channels):
                log.warning("Error: Channel Not Found")
                await ctx.send(embed = gen_embed(title = 'Channel Not Found', content = 'Please doublecheck the id or try a channel mention.'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Valid options: "disable"'))
        else:
            if channel_option == "log":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': channel_id.id}})
                await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
            elif channel_option == "welcome":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': channel_id.id}})
                await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
            elif channel_option == "modmail":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modmail_channel': channel_id.id}})
                await ctx.send(embed = gen_embed(title = 'channelconfig', content = f'Enabled modmail in channel {channel_id.mention} for {ctx.guild.name}'))

    @commands.command(name = 'welcomeconfig',
                    description = 'Set the welcome message and optional banner. Enclose the message in quotes.',
                    help = 'Usage\n\n^welcomeconfig "[message]" <url>')
    @commands.check_any(commands.has_guild_permissions(manage_guild = True), has_modrole())
    async def welcomeconfig(self, ctx, url: str = None, *, welcome_message):
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

    @commands.command(name = 'serverconfig',
                    description = 'Set various server config settings.',
                    help = 'Available settings - max_strike, fun')
    @commands.check_any(commands.has_guild_permissions(manage_guild = True), has_modrole())
    async def serverconfig(self, ctx, config_option: str, value: Union[int, str]):
        valid_options = {'max_strike', 'fun'}
        valid_values = {'enable', 'disable'}
        config_option = config_option.lower()
        value = value.lower()
        if config_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed = gen_embed(title = 'Input Error', content = f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        if config_option == 'max_strike':
            if value > 0:
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'max_strike': value}})
                await ctx.send(embed = gen_embed(title = 'serverconfig', content = f'Changed the max number of strikes to {value}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Please make sure the number > 0'))
        if config_option == 'fun':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'fun': True}})
                    await ctx.send(embed = gen_embed(title = 'serverconfig', content = f'Fun commands have been enabled for {ctx.guild.name}'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'fun': False}})
                    await ctx.send(embed = gen_embed(title = 'serverconfig', content = f'Fun commands have been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed = gen_embed(title = 'Input Error', content = 'That is not a valid option for this parameter. Valid values: "enable" "disable"'))

    @commands.command(name = 'purgeid',
                    description = 'Deletes a specific message based on message id.',
                    help = 'Usage\n\n^purgeid <message id>')
    @commands.check_any(commands.has_guild_permissions(manage_messages = True), has_modrole())
    async def msgpurgeid(self, ctx, msg_id: int):
        def id_check(m):
                return m.id == msg_id
        
        deleted = await ctx.channel.purge(check = id_check)
        await ctx.send(embed = gen_embed(title = 'purgeid', content = f'Message {msg_id} deleted.'))

    @commands.command(name = 'purge',
                    description = 'Deletes the previous # of messages from the channel. Specifying a user will delete the messages for that user. Specifying a time will delete messages from the past x amount of time. You can also reply to a message to delete messages after the one replied to.',
                    help = 'Usage\n\n^purge <user id/user mention/user name + discriminator (ex: name#0000)> <num> <time/message id>\n(Optionally, you can reply to a message with the command and it will delete ones after that message)')
    @commands.check_any(commands.has_guild_permissions(manage_messages = True), has_modrole())
    async def msgpurge(self, ctx, members: commands.Greedy[discord.Member], num: Optional[int], time: Optional[Union[discord.Message, str]]):
        def convert_to_timedelta(s):
                    return timedelta(**{UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val')) for m in re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)})

        async def delete_messages(limit = None, check = None, before = None, after = None):
            deleted = await ctx.channel.purge(limit = limit, check = check, before = before, after = after)
            if check:
                await ctx.send(embed = gen_embed(title = 'purge', content = f'The last {len(deleted)} messages by {member.name}#{member.discriminator} were deleted.'))
            else:
                await ctx.send(embed = gen_embed(title = 'purge', content = f'The last {len(deleted)} messages were deleted.'))

        time = time or ctx.message.reference
        
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
                        else:
                            await delete_messages(limit = num + 1, check = user_check)
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
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            await ctx.send(embed = gen_embed(title = "Invalid parameter(s) entered", content = f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))

    @commands.command(name = 'addrole',
                    description = 'Creates a new role. You can also specify members to add to the role when it is created.',
                    help = 'Usage\n\n^addrole <user mentions/user ids> <role name>')
    @commands.check_any(commands.has_guild_permissions(manage_roles = True), has_modrole())
    async def addrole(self, ctx, members: commands.Greedy[discord.Member], *, role_name: str):
        role_permissions = ctx.guild.default_role
        role_permissions = role_permissions.permissions

        role = await ctx.guild.create_role(name = role_name, permissions = role_permissions, colour = discord.Colour.blue(), mentionable=True, reason=f"Created by {ctx.author.name}#{ctx.author.discriminator}")
        await ctx.send(embed = gen_embed(title = 'addrole', content = f'Created role {role.name}.'))
        
        await role.edit(position = 0)

        if members:
            for member in members:
                await member.add_roles(role)
            await ctx.send(embed = gen_embed(title = 'addrole', content = f'Added members to role {role.name}.'))

    @commands.command(name = 'removerole',
                    description = 'Deletes a role.',
                    help = 'Usage\n\n^removerole <role name/role mention>')
    @commands.check_any(commands.has_guild_permissions(manage_roles = True), has_modrole())
    async def removerole(self, ctx, *, role_name: Union[discord.Role, str]):
        role_name = role_name or ctx.message.role_mentions
        await role.delete(reason=f'Deleted by {ctx.author.name}#{ctx.author.discriminator}')
        await ctx.send(embed = gen_embed(title = 'removerole', content = 'Role has been removed.'))

    #adduser
    #removeuser
    @commands.command(name = 'mute',
                    description = 'Mute user(s) for a certain amount of time.',
                    help = 'Ysage\n\n^mute [user mentions/user ids] <time> <reason>')
    @commands.check_any(commands.has_guild_permissions(mute_members = True), has_modrole())
    async def mute(self, ctx, members: commands.Greedy[discord.Member], time: Optional[int], *, reason: Optional[str])

    @commands.command(name = 'kick',
                    description = 'Kick user(s) from the server.',
                    help = 'Usage\n\n^kick [user mentions/user ids] <reason>')
    @commands.check_any(commands.has_guild_permissions(kick_members = True), has_modrole())
    async def cmd_kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: Optional[str]):
        kicked = ""
        for member in members:
            await ctx.guild.kick(member, reason = reason)
            kicked = kicked + f'{member.name}#{member.discriminator} '
        await ctx.send(embed = gen_embed(title = 'kick', content = f'{kicked}has been kicked.\nReason: {reason}'))

    @commands.command(name = 'ban',
                    description = 'Ban user(s) from the server.',
                    help = 'Usage\n\n^ban [user mentions/user ids] <reason>')
    @commands.check_any(commands.has_guild_permissions(ban_members = True), has_modrole())
    async def cmd_ban(self, ctx, users: commands.Greedy[discord.User], *, reason: Optional[str]):
        banned = ""
        for user in users:
            await ctx.guild.ban(user, reason = reason)
            banned = banned + f'{member.name}#{member.discriminator} '
        await ctx.send(embed = gen_embed(title = 'ban', content = f'{banned}has been kicked.\nReason: {reason}'))

    @commands.command(name = 'strike',
                    description = 'Strike a user. After a certain number of strikes, the user is automatically banned. Default is 3, can be changed using severconfig',
                    help = 'Usage\n\n^warn [user mentions/user ids/user name + discriminator (ex: name#0000)] <reason>')
    @commands.check_any(commands.has_guild_permissions(ban_members = True), has_modrole())
    async def strike(self, ctx, members: commands.Greedy[discord.Member], message_link: str, *, reason):
        time = datetime.datetime.utcnow()

        if not validators.url(message_link):
            await ctx.send(embed = gen_embed(title = 'Input Error', content = "Invalid URL. Check the formatting (https:// prefix is required)"))
            return
        for member in members:
            dm_channel = member.dm_channel
            if member.dm_channel is None:
                dm_channel = await member.create_dm()

            post = {
                'time': time,
                'server_id': ctx.guild.id,
                'user_name': f'{member.name}#{member.discriminator}',
                'user_id': member.id,
                'message_link': message_link,
                'reason': reason
            }
            await db.warns.insert_one(post)

            dm_embed = gen_embed(name = ctx.guild.name, icon_url = ctx.guild.icon_url, title='You have been given a strike', content = f'Reason: {reason}')
            dm_embed.set_footer(text = time.ctime())
            await dm_channel.send(embed = dm_embed)

            embed = gen_embed(name = f'{member.name}#{member.discriminator}', icon_url = member.avatar_url, title='Strike recorded', content = f'{ctx.author.name}#{ctx.author.discriminator} gave a strike to {member.name}#{member.discriminator} | {member.id}')
            embed.add_field(name = 'Reason', value = f'{reason}\n\n[Go to message/evidence]({message_link})')
            embed.set_footer(text = time.ctime())
            await ctx.send(embed = embed)

            #check for number of strikes
            expire_date = time + relativedelta(months=-2)
            query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date}}
            results = await db.warns.count_documents(query)
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if results >= document['max_strike']:
                max_strike = document['max_strike']
                await ctx.guild.ban(member, reason = f'You have accumulated {max_strike} strikes and therefore will be banned from the server.')

    @commands.command(name = 'lookup',
                    description = 'Lookup strikes for a user. Returns all currently active strikes.',
                    help = 'Usage\n\n^lookup [user mention/user id]')
    @commands.check_any(commands.has_guild_permissions(view_audit_log = True), has_modrole())
    async def lookup(self, ctx, member: discord.Member):
        time = datetime.datetime.utcnow()

        expire_date = time + relativedelta(months=-2)
        query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date}}
        results = db.warns.find(query).sort('time', pymongo.DESCENDING)
        num_strikes = await db.warns.count_documents(query)
        expired_query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$lt': expire_date}}
        expired_results = db.warns.find(expired_query).sort('time', pymongo.DESCENDING)

        embed = gen_embed(name = f'{member.name}#{member.discriminator}', icon_url = member.avatar_url, title='Strike Lookup', content= f'Found {num_strikes} active strikes for this user.')
        async for document in results:
            stime = document['time']
            reason = document['reason']
            message_link = document['message_link']
            embed.add_field(name = f'Strike | {stime.ctime()}', value = f'Reason: {reason}\n[Go to message/evidence]({message_link})', inline = False)
        async for document in expired_results:
            stime = document['time']
            reason = document['reason']
            message_link = document['message_link']
            embed.add_field(name = f'Strike (EXPIRED) | {stime.ctime()}', value = f'Reason: {reason}\n[Go to message/evidence]({message_link})', inline = False)
        embed.set_footer(text = f'UID: {member.id}')
        await ctx.send(embed = embed)

    @commands.command(name = 'slowmode',
                    description = 'Enables slowmode for the channel you are in. Time is in seconds.',
                    help = 'Usage\n\n^slowmode [time]')
    @commands.check_any(commands.has_guild_permissions(manage_channels = True), has_modrole())
    async def slowmode(self, ctx, time : int):
        await ctx.channel.edit(slowmode_delay = 0)
        await ctx.send(embed = gen_embed(title = 'slowmode', content = f'Slowmode has been enabled in {ctx.channel.name}\n({time} seconds)'))

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

    @commands.command(name = 'exec',
                    description = 'exec',
                    help = 'dev only')
    @commands.check(is_owner())
    async def cmd_debug(self, ctx, *, data):
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith('```') and data.endswith('```'):
            data = '\n'.join(data.rstrip('`\n').split('\n')[1:])

        code = data.strip('` \n')

        scope = globals().copy()
        scope.update({'self': self})

        try:
            result = eval(code, scope)
        except:
            try:
                exec(code, scope)
            except Exception as e:
                traceback.print_exc(chain=False)
                await ctx.send("{}: {}".format(type(e).__name__, e))

        if asyncio.iscoroutine(result):
            result = await result

def setup(bot):
    bot.add_cog(Administration(bot))