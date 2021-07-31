import discord
import traceback
import re
import time
import validators
import datetime
import asyncio
import pymongo
import emoji as zemoji

from dateutil.relativedelta import relativedelta
from datetime import timedelta
from typing import Union, Optional, Literal
from discord.ext import commands
from formatting.constants import UNITS
from formatting.embed import gen_embed
from bson.objectid import ObjectId
from __main__ import log, db, prefix_list, prefix


class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def convert_emoji(argument):
        return zemoji.demojize(argument)

    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                return role in ctx.author.roles
            else:
                return False

        return commands.check(predicate)

    def convert_severity(argument):
        if str(argument) == '1':
            return '1'
        elif str(argument) == '2':
            return '2'
        elif str(argument) == '3':
            return '3'
        else:
            raise discord.ext.commands.BadArgument()

    def is_owner():
        async def predicate(ctx):
            if ctx.message.author.id == 133048058756726784:
                return True
            else:
                return False

        return commands.check(predicate)

    @commands.command(name='setprefix',
                      description='Sets the command prefix that the bot will use for this server.',
                      help='Usage:\n\n%setprefix !')
    @commands.check_any(commands.has_guild_permissions(administrator=True), is_owner())
    async def setprefix(self, ctx, prefix: str):
        await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'prefix': prefix}})
        # ensure the list kept in memory is updated, since we can't pull again from the database
        prefix_list[ctx.guild.id] = prefix
        await ctx.send(embed=gen_embed(title='Prefix set', content=f'Set prefix to {prefix}'))

    @setprefix.error
    async def setprefix_error(self, ctx, error):
        if isinstance(error, commands.CheckAnyFailure):
            log.warning("PermissionError: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(embed=gen_embed(title='Permissions Error',
                                           content='You must have administrator rights to run this command.'))

        elif isinstance(error, commands.BadArgument):
            log.warning("Bad Argument - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(embed=gen_embed(title="Invalid type of parameter entered",
                                           content="Are you sure you entered the right parameter?"))

    @commands.command(name='setmodrole',
                      description='Sets the moderator role for this server. Only mods have access to administration commands.',
                      help='Usage:\n\n%setmodrole [role id/role mention]')
    @commands.check_any(commands.has_guild_permissions(administrator=True), is_owner())
    async def setmodrole(self, ctx, roleid: discord.Role):
        roleid = roleid or ctx.message.role_reactions[0]
        await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modrole': roleid.id}})
        await ctx.send(embed=gen_embed(title='Mod role set', content=f'Set mod role to {roleid.name}'))

    @setmodrole.error
    async def setmodrole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title='Role Not Found', content='Please doublecheck the id or try a role mention.'))

        elif isinstance(error, commands.CheckAnyFailure):
            log.warning("PermissionError: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(embed=gen_embed(title='Permissions Error',
                                           content='You must have administrator rights to run this command.'))

    @commands.command(name='autorole',
                      description='Sets a role to be added whenever a user joins the server.',
                      help='Usage\n\n%autorole [role id/role mention or disable]')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def autorole(self, ctx, roleid: Union[discord.Role, str]):
        roleid = roleid or ctx.message.role_reactions[0]
        if isinstance(roleid, str):
            roleid = roleid.lower()
            if roleid == "disable":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': None}})
                await ctx.send(embed=gen_embed(title='autorole', content=f'Disabled autorole for {ctx.guild.name}'))
            elif not discord.utils.find(lambda r: r.id == roleid, ctx.guild.roles):
                log.warning("Error: Role Not Found")
                await ctx.send(
                    embed=gen_embed(title='Role Not Found', content='Please doublecheck the id or try a role mention.'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid options: "disable"'))
        else:
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'autorole': roleid.id}})
            await ctx.send(embed=gen_embed(title='autorole',
                                           content=f'Enabled autorole with role {roleid.name} for {ctx.guild.name}'))

    @autorole.error
    async def autorole_error(self, ctx, error):
        if isinstance(error, commands.RoleNotFound):
            log.warning("RoleNotFound: error when adding mod role - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title='Role Not Found', content='Please doublecheck the id or try a role mention.'))

        elif isinstance(error, commands.CheckAnyFailure):
            log.warning("PermissionError: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(embed=gen_embed(title='Permissions Error',
                                           content='You must have server permissions or moderator role to run this command.'))

    @commands.command(name='blacklist',
                      description='Add a channel to the blacklist (Kanon will not save message IDs from these channels for fun commands. That means she cannot accidently leak any messages from these channels.)',
                      help='Usage\n\n%blacklist [add/remove] [channel id/channel mention]')
    async def blacklist(self, ctx, channel_option: str, channel_id: commands.Greedy[discord.TextChannel]):
        valid_options = {'add', 'remove', 'delete'}
        channel_option = channel_option.lower()
        if channel_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        document = await db.servers.find_one({"server_id": ctx.guild.id})
        blacklist = document['blacklist']
        if channel_option == 'add':
            channels_added = ""
            for channel in channel_id:
                if channel.id not in blacklist:
                    blacklist.append(channel.id)
                    channels_added += f"{channel.mention} "
                else:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This channel is already blacklisted!'))
                    return
                await db.msgid.delete_many({"channel_id": channel.id})
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'blacklist': blacklist}})
            await ctx.send(embed=gen_embed(title='blacklist',
                                           content=f'Blacklisted channel {channels_added} for {ctx.guild.name}'))
        elif channel_option == 'remove' or 'delete':
            channels_removed = ""
            for channel in channel_id:
                if channel.id in blacklist:
                    blacklist.remove(channel.id)
                    channels_removed += f"{channel.mention} "
                else:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This channel is not blacklisted!'))
                    return
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'blacklist': blacklist}})
            await ctx.send(embed=gen_embed(title='blacklist',
                                           content=f'Unblacklisted channel {channels_removed} for {ctx.guild.name}'))

    @commands.command(name='whitelist',
                      description='Add a channel to the whitelist (Kanon will only listen to messages/commands in these channels.)',
                      help='Usage\n\n%whitelist [add/remove] [channel id/channel mention]')
    async def whitelist(self, ctx, channel_option: str, channel_id: commands.Greedy[discord.TextChannel]):
        valid_options = {'add', 'remove', 'delete'}
        channel_option = channel_option.lower()
        if channel_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        document = await db.servers.find_one({"server_id": ctx.guild.id})
        whitelist = document['whitelist']
        if channel_option == 'add':
            channels_added = ""
            for channel in channel_id:
                if channel.id not in whitelist:
                    whitelist.append(channel.id)
                    channels_added += f"{channel.mention} "
                else:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This channel is already whitelisted!'))
                    return
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'whitelist': whitelist}})
            await ctx.send(embed=gen_embed(title='whitelist',
                                           content=f'Whitelisted channel {channels_added} for {ctx.guild.name}'))
        elif channel_option == 'remove' or 'delete':
            channels_removed = ""
            for channel in channel_id:
                if channel.id in whitelist:
                    whitelist.remove(channel.id)
                    channels_removed += f"{channel.mention} "
                else:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This channel is not whitelisted!'))
                    return
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'whitelist': whitelist}})
            await ctx.send(embed=gen_embed(title='whitelist',
                                           content=f'Unwhitelisted channel {channels_removed} for {ctx.guild.name}'))

    @commands.command(name='channelconfig',
                      description='Set channel for logs and welcome messages.',
                      help='Usage\n\n%channelconfig [log/welcome/modmail] [channel id/channel mention] OR [disable] to turn off')
    @commands.check_any(commands.has_guild_permissions(manage_guild=True), has_modrole())
    async def channelconfig(self, ctx, channel_option: str, channel_id: Union[discord.TextChannel, str]):
        valid_options = {'log', 'welcome', 'modmail', 'announcements'}
        channel_option = channel_option.lower()
        if channel_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        channel_id = channel_id or ctx.message.channel_mentions[0]
        if isinstance(channel_id, str):
            channel_id = channel_id.lower()
            if channel_id == "disable":
                if channel_option == "log":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': None}})
                    await ctx.send(
                        embed=gen_embed(title='channelconfig', content=f'Disabled logging for {ctx.guild.name}'))
                elif channel_option == "welcome":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': None}})
                    await ctx.send(embed=gen_embed(title='channelconfig',
                                                   content=f'Disabled welcome messages for {ctx.guild.name}'))
                elif channel_option == "modmail":
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modmail_channel': None}})
                    await ctx.send(
                        embed=gen_embed(title='channelconfig', content=f'Disabled modmail for {ctx.guild.name}'))
                elif channel_option == "announcements":
                    await ctx.send(embed=gen_embed(title='channelconfig',
                                                   content=f'Cannot disable announcements.'))

            elif not discord.utils.find(lambda c: c.id == channel_id, ctx.guild.text_channels):
                log.warning("Error: Channel Not Found")
                await ctx.send(embed=gen_embed(title='Channel Not Found',
                                               content='Please doublecheck the id or try a channel mention.'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid options: "disable"'))
        else:
            if channel_option == "log":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_channel': channel_id.id}})
                await ctx.send(embed=gen_embed(title='channelconfig',
                                               content=f'Enabled logging in channel {channel_id.mention} for {ctx.guild.name}'))
            elif channel_option == "welcome":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_channel': channel_id.id}})
                await ctx.send(embed=gen_embed(title='channelconfig',
                                               content=f'Enabled welcomes in channel {channel_id.mention} for {ctx.guild.name}'))
            elif channel_option == "modmail":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'modmail_channel': channel_id.id}})
                await ctx.send(embed=gen_embed(title='channelconfig',
                                               content=f'Enabled modmail in channel {channel_id.mention} for {ctx.guild.name}'))
            elif channel_option == "announcements":
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'announcement_channel': channel_id.id}})
                await ctx.send(embed=gen_embed(title='channelconfig',
                                               content=f'Enabled announcements in channel {channel_id.mention} for {ctx.guild.name}'))

    @commands.command(name='welcomeconfig',
                      description='Set the welcome message and optional banner.',
                      help='Usage\n\n%welcomeconfig "[message]" <url>')
    @commands.check_any(commands.has_guild_permissions(manage_guild=True), has_modrole())
    async def welcomeconfig(self, ctx, url: str = None, *, welcome_message: str):
        clean_welcome_message = re.sub('<@!?&?\d{17,18}>', '[removed mention]', welcome_message)
        if url:
            if validators.url(url):
                await db.servers.update_one({"server_id": ctx.guild.id},
                                            {"$set": {'welcome_message': welcome_message, 'welcome_banner': url}})
                embed = gen_embed(title='welcomeconfig',
                                  content=f"Welcome message set for {ctx.guild.name}: {welcome_message}")
                embed.set_image(url=url)
                await ctx.send(embed=embed)
            else:
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content="Invalid URL. Check the formatting (https:// prefix is required)"))
        else:
            await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'welcome_message': welcome_message}})
            await ctx.send(embed=gen_embed(title='welcomeconfig',
                                           content=f"Welcome message set for {ctx.guild.name}: {welcome_message}"))

    @commands.command(name='serverconfig',
                      description='Set various server config settings.',
                      help='Usage\n\n%serverconfig [option] [enable/disable]\nAvailable settings - fun (commands from fun cog), log_joinleave (log joins and leaves), log_kbm (log kicks, bans, and mutes), log_strikes (log strikes), chat (enables/disables chat function')
    @commands.check_any(commands.has_guild_permissions(manage_guild=True), has_modrole())
    async def serverconfig(self, ctx, config_option: str, value: str):
        valid_options = {'fun', 'log_joinleave', 'log_kbm', 'log_strikes', 'chat'}
        valid_values = {'enable', 'disable'}
        config_option = config_option.lower()
        value = value.lower()
        if config_option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        if config_option == 'fun':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'fun': True}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Fun commands have been enabled for {ctx.guild.name}'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'fun': False}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Fun commands have been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))
        elif config_option == 'chat':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'chat': True}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Chat function has been enabled for {ctx.guild.name}. Remember to blacklist channels you do not want Kanon to listen to.'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'chat': False}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Chat function has been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))
        elif config_option == 'log_joinleave':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_joinleaves': True}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging member joining and leaving has been enabled for {ctx.guild.name}'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_joinleaves': False}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging member joining and leaving has been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))
        elif config_option == 'log_kbm':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_kbm': True}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging kicks, bans, and mutes has been enabled for {ctx.guild.name}'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_kbm': False}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging kicks, bans, and mutes has been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))
        elif config_option == 'log_strikes':
            if value in valid_values:
                if value == 'enable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_joinleaves': True}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging strikes been enabled for {ctx.guild.name}'))
                if value == 'disable':
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'log_joinleaves': False}})
                    await ctx.send(embed=gen_embed(title='serverconfig',
                                                   content=f'Logging strikes has been disabled for {ctx.guild.name}'))
            else:
                log.warning("Error: Invalid input")
                await ctx.send(embed=gen_embed(title='Input Error',
                                               content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))

    @commands.command(name='purgeid',
                      description='Deletes a specific message based on message id.',
                      help='Usage\n\n%purgeid <message id>')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def msgpurgeid(self, ctx, msg_id: int):
        def id_check(m):
            return m.id == msg_id

        deleted = await ctx.channel.purge(check=id_check)
        await ctx.send(embed=gen_embed(title='purgeid', content=f'Message {msg_id} deleted.'))

    @commands.command(name='purge',
                      description='Deletes the previous # of messages from the channel. Specifying a user will delete the messages for that user. Specifying a time will delete messages from the past x amount of time. You can also reply to a message to delete messages after the one replied to.',
                      help='Usage\n\n%purge <user id/user mention/user name + discriminator (ex: name#0000)> <num> <time/message id>\n(Optionally, you can reply to a message with the command and it will delete ones after that message)')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def msgpurge(self, ctx, members: commands.Greedy[discord.Member], num: Optional[int],
                       time: Optional[Union[discord.Message, str]]):
        def convert_to_timedelta(s):
            return timedelta(**{UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val')) for m in
                                re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)})

        async def delete_messages(limit=None, check=None, before=None, after=None):
            deleted = await ctx.channel.purge(limit=limit, check=check, before=before, after=after)
            if check:
                sent = await ctx.send(embed=gen_embed(title='purge',
                                                      content=f'The last {len(deleted)} messages by {member.name}#{member.discriminator} were deleted.'))
                await ctx.message.delete()
                await sent.delete(delay=5)
            else:
                sent = await ctx.send(
                    embed=gen_embed(title='purge', content=f'The last {len(deleted)} messages were deleted.'))
                await ctx.message.delete()
                await sent.delete(delay=5)

        time = time or ctx.message.reference

        if members:
            for member in members:
                def user_check(m):
                    return m.author == member

                if num:
                    if num < 0:
                        log.warning("Error: Invalid input")
                        await ctx.send(embed=gen_embed(title='Input Error',
                                                       content='That is not a valid option for this parameter. Please pick a number > 0.'))

                    else:
                        if time:
                            after_value = datetime.datetime.utcnow()
                            if isinstance(time, str):
                                after_value = after_value - convert_to_timedelta(time)
                            elif isinstance(time, discord.MessageReference):
                                after_value = await ctx.channel.fetch_message(time.message_id)

                            await delete_messages(limit=num, check=user_check, after=after_value)
                        else:
                            await delete_messages(limit=num, check=user_check)
                elif time:
                    after_value = datetime.datetime.utcnow()
                    if isinstance(time, str):
                        after_value = after_value - convert_to_timedelta(time)
                    elif isinstance(time, discord.MessageReference):
                        after_value = await ctx.channel.fetch_message(time.message_id)

                    await delete_messages(check=user_check, after=after_value)
            return
        elif num:
            if num < 0:
                log.warning("Error: Invalid input")
                sent = await ctx.send(embed=gen_embed(title='Input Error',
                                                      content='That is not a valid option for this parameter. Please pick a number > 0.'))
                await ctx.message.delete()
                await sent.delete(delay=5)
            else:
                if time:
                    after_value = datetime.datetime.utcnow()
                    if isinstance(time, str):
                        after_value = after_value - convert_to_timedelta(time)
                    elif isinstance(time, discord.MessageReference):
                        after_value = await ctx.channel.fetch_message(time.message_id)

                    await delete_messages(limit=num, after=after_value)
                    return

                else:
                    await delete_messages(limit=num, before=ctx.message)
                    return
        elif time:
            after_value = datetime.datetime.utcnow()
            if isinstance(time, str):
                after_value = after_value - convert_to_timedelta(time)
            elif isinstance(time, discord.MessageReference):
                after_value = await ctx.channel.fetch_message(time.message_id)

            await delete_messages(before=ctx.message, after=after_value)
            return
        else:
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            sent = await ctx.send(embed=gen_embed(title="Invalid parameter(s) entered",
                                                  content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            await ctx.message.delete()
            await sent.delete(delay=5)

    @commands.command(name='addrole',
                      description='Creates a new role. You can also specify members to add to the role when it is created.',
                      help='Usage\n\n%addrole <user mentions/user ids/user name + discriminator (ex: name#0000)> <role name>')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def addrole(self, ctx, members: commands.Greedy[discord.Member], *, role_name: str):
        role_permissions = ctx.guild.default_role
        role_permissions = role_permissions.permissions

        role = await ctx.guild.create_role(name=role_name, permissions=role_permissions, colour=discord.Colour.blue(),
                                           mentionable=True,
                                           reason=f"Created by {ctx.author.name}#{ctx.author.discriminator}")
        await ctx.send(embed=gen_embed(title='addrole', content=f'Created role {role.name}.'))

        await role.edit(position=1)

        if members:
            for member in members:
                await member.add_roles(role)
            await ctx.send(embed=gen_embed(title='addrole', content=f'Added members to role {role.name}.'))

    @commands.command(name='removerole',
                      description='Deletes a role.',
                      help='Usage\n\n%removerole <role name/role mention>')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def removerole(self, ctx, *, role_name: Union[discord.Role, str]):
        role_name = role_name or ctx.message.role_mentions
        await role.delete(reason=f'Deleted by {ctx.author.name}#{ctx.author.discriminator}')
        await ctx.send(embed=gen_embed(title='removerole', content='Role has been removed.'))

    @commands.command(name='adduser',
                      description='Adds user(s) to a role.',
                      help='Usage\n\n%adduser [user mentions/user ids/user name + discriminator (ex: name#0000)] [role name/role mention/role id]')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def adduser(self, ctx, members: commands.Greedy[discord.Member], *, role: discord.Role):
        added = ''
        for member in members:
            await member.add_roles(role)
            added = added + f'{member.mention} '
        await ctx.send(embed=gen_embed(title='adduser', content=f'{added} has been added to role {role.name}.'))

    @commands.command(name='removeuser',
                      description='Removes user(s) from a role.',
                      help='Usage\n\n%removeuser [user mentions/user ids/user name + discriminator (ex: name#0000)] [role name/role mention/role id]')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def removeuser(self, ctx, members: commands.Greedy[discord.Member], *, role: discord.Role):
        removed = ''
        for member in members:
            await member.remove_roles(role)
            removed = removed + f'{member.mention} '
        await ctx.send(
            embed=gen_embed(title='removeuser', content=f'{removed} has been removed from role {role.name}.'))

    @commands.command(name='setupverify',
                      description='Sets up verification role for the server.',
                      help='Usage\n\n%setupverify [channel mention/channel id] [emoji] <message>\n\n If no message is specified, a default message will be used.')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def setupverify(self, ctx, value: str, channel: Optional[discord.TextChannel], emoji: Optional[Union[discord.Emoji, convert_emoji]], *, embed_message: Optional[str]):
        valid_values = {'enable', 'disable'}
        post = []
        value = value.lower()
        if value in valid_values:
            if value == 'disable':
                document = await db.servers.find_one({"server_id": ctx.guild.id})
                await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'verify': []}})
                if document['verify']:
                    rchannel = self.bot.get_channel(document['verify'][0])
                    rmessage = await rchannel.fetch_message(document['verify'][2])
                    await rmessage.delete()
                    newpermissions = ctx.guild.roles[0].permissions
                    newpermissions.update(read_messages=True, send_messages=True)
                    await ctx.guild.roles[0].edit(reason='Disabling verification', permissions=newpermissions)
                    await ctx.send(embed=gen_embed(title='setupverify',
                                                   content=f'Verification has been disabled for {ctx.guild.name}'))
                else:
                    await ctx.send(embed=gen_embed(title='setupverify',
                                                   content=f'Verification is not enabled!'))
            if value == 'enable':
                if emoji and channel:
                    post.append(channel.id)
                    if isinstance(emoji, discord.Emoji):
                        post.append(f"<:{emoji.name}:{emoji.id}>")
                    else:
                        # the only reason I can't just accept the raw emoji is because of the order of parameters and also because i don't want to accept whole strings
                        emoji = zemoji.emojize(emoji)
                        emojilist = zemoji.emoji_lis(emoji)
                        if len(emojilist) > 0:
                            emoji = emojilist[0]['emoji']
                            post.append(emoji)
                        else:
                            log.warning('Error: Invalid Input')
                            await ctx.send(embed=gen_embed(title='Input Error',
                                                           content=f'Could not recognize emoji or no emoji was given.'))
                            return

                    newpermissions = ctx.guild.roles[0].permissions
                    newpermissions.update(read_messages = False, send_messages = False)
                    await ctx.guild.roles[0].edit(reason='Enabling verification', permissions=newpermissions)
                    role = discord.utils.find(lambda r: r.name == 'Verified', ctx.guild.roles)
                    if role:
                        verified = role
                        await role.edit(reason='Enabling verification with existing role',
                                        permissions=discord.Permissions(read_messages=True, send_messages=True))
                    else:
                        verified = await ctx.guild.create_role(name='Verified', permissions=discord.Permissions(read_messages=True, send_messages=True))
                    for achannel in ctx.guild.text_channels:
                        channelpermissions = achannel.overwrites_for(ctx.guild.roles[0])
                        if channelpermissions:
                            if channelpermissions.read_messages:
                                await achannel.set_permissions(ctx.guild.roles[0], overwrite=None)
                            elif not channelpermissions.read_messages:
                                await achannel.set_permissions(verified, overwrite=discord.PermissionOverwrite(read_messages = False, add_reactions = False))
                    await channel.set_permissions(ctx.guild.roles[0], overwrite=discord.PermissionOverwrite(read_messages = True, add_reactions = True))



                    if embed_message:
                        if len(embed_message) < 1024:
                            embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                                 title=f'Verification',
                                                 content=embed_message)
                            rmessage = await channel.send(embed=embed)
                            post.append(rmessage.id)
                            await rmessage.add_reaction(emoji)
                        else:
                            log.warning('Error: Reason too long')
                            await ctx.send(embed=gen_embed(title='Max character limit reached',
                                                           content=f'Your reason message is too long ({len(reason) - 1024} characters over limit). Please shorten the message to fit it in the embed.'))
                            return
                    else:
                        embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                          title=f'Verification',
                                          content='In order to access this server, you must react to this message. By reacting to this message, you are agreeing to the rules of this server and Discord TOS.')
                        rmessage = await channel.send(embed=embed)
                        post.append(rmessage.id)
                        await rmessage.add_reaction(emoji)
                    await db.servers.update_one({"server_id": ctx.guild.id}, {"$set": {'verify': post}})
                    await ctx.send(embed=gen_embed(title='setupverify',
                                                   content=f'Verification has been set up in {ctx.guild.name}.'))
                else:
                    log.warning("Missing Required Argument")
                    params = ' '.join([x for x in ctx.command.clean_params])
                    sent = await ctx.send(embed=gen_embed(title="Invalid parameter(s) entered",
                                                          content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
                    return
        else:
            log.warning("Error: Invalid input")
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content='That is not a valid option for this parameter. Valid values: "enable" "disable"'))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        rmessage = await channel.fetch_message(payload.message_id)
        document = await db.servers.find_one({"server_id": rmessage.guild.id})
        if document['verify']:
            if document['verify'][2] == rmessage.id:
                extracted_emoji = None
                remoji = None
                raw_emoji = document['verify'][1]
                if re.search('\d{18}', raw_emoji):
                    extracted_emoji = re.search('\d{18}', raw_emoji).group()
                    extracted_emoji = discord.utils.get(rmessage.guild.emojis, id=int(extracted_emoji))
                    remoji = discord.utils.get(rmessage.guild.emojis, id=payload.emoji.id)
                if not extracted_emoji:
                    extracted_emoji = raw_emoji
                    remoji = payload.emoji.name

                if extracted_emoji == remoji:
                    role = discord.utils.find(lambda r: r.name == 'Verified', rmessage.guild.roles)
                    await payload.member.add_roles(role)

    @commands.command(name='mute',
                      description='Mute user(s) for a certain amount of time.',
                      help='Usage\n\n%mute [user mentions/user ids/user name + discriminator (ex: name#0000)] <time> <reason>')
    @commands.check_any(commands.has_guild_permissions(mute_members=True), has_modrole())
    async def mute(self, ctx, members: commands.Greedy[discord.Member], mtime: Optional[str] = None, *,
                   reason: Optional[str]):
        def convert_to_seconds(s):
            return int(timedelta(**{
                UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val'))
                for m in re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)
            }).total_seconds())

        async def modmail_enabled():
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                return True
            else:
                return False

        mutedRole = discord.utils.get(ctx.guild.roles, name="Muted")

        if not mutedRole:
            mutedRole = await ctx.guild.create_role(name="Muted")

            for channel in ctx.guild.channels:
                await channel.set_permissions(mutedRole, speak=False, send_messages=False)

        muted = ""
        for member in members:
            await member.add_roles(mutedRole)

            dm_channel = member.dm_channel
            if member.dm_channel is None:
                dm_channel = await member.create_dm()

            if mtime:
                seconds = convert_to_seconds(mtime)
                m = await modmail_enabled()
                dm_embed = None
                if m:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted for {seconds} seconds',
                                         content=f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                else:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted for {seconds} seconds',
                                         content=f'Reason: {reason}')
                dm_embed.set_footer(text=time.ctime())
                try:
                    await dm_channel.send(embed=dm_embed)
                except discord.errors.Forbidden:
                    await ctx.send(embed = gen_embed(title='Warning', content = 'This user does not accept DMs. I could not send them the message, but I will proceed with muting the user.'))

                embed = gen_embed(title='mute', content=f'{member.mention} has been muted. \nReason: {reason}')
                await ctx.send(embed=embed)
                document = await db.servers.find_one({"server_id": ctx.guild.id})
                if document['log_channel'] and document['log_kbm']:
                    msglog = int(document['log_channel'])
                    logChannel = member.guild.get_channel(msglog)
                    await logChannel.send(embed=embed)

                await asyncio.sleep(seconds)
                await member.remove_roles(mutedRole)
                return
            else:
                m = await modmail_enabled()
                dm_embed = None
                if m:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted.',
                                         content=f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                    dm_embed.set_footer(text=ctx.guild.id)
                else:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted.', content=f'Reason: {reason}')
                    dm_embed.set_footer(text=time.ctime())
                try:
                    await dm_channel.send(embed=dm_embed)
                except discord.errors.Forbidden:
                    await ctx.send(embed = gen_embed(title='Warning', content = 'This user does not accept DMs. I could not send them the message, but I will proceed with muting the user.'))
                muted = muted + f'{member.mention} '

            await ctx.send(embed=gen_embed(title='mute', content=f'{muted} has been muted. \nReason: {reason}'))

    @commands.command(name='unmute',
                      description='Unmute a user',
                      help='Usage\n\n %unmute [user mentions/user ids/user name + discriminator (ex: name#0000)]')
    @commands.check_any(commands.has_guild_permissions(mute_members=True), has_modrole())
    async def unmute(self, ctx, members: commands.Greedy[discord.Member]):
        mutedRole = discord.utils.get(ctx.guild.roles, name="Muted")

        unmuted = ""
        for member in members:
            await member.remove_roles(mutedRole)
            unmuted = unmuted + f'{member.mention} '

        await ctx.send(embed=gen_embed(title='unmute', content=f'{unmuted}has been unmuted.'))

    @commands.command(name='kick',
                      description='Kick user(s) from the server.',
                      help='Usage\n\n%kick [user mentions/user ids/user name + discriminator (ex: name#0000)] <reason>')
    @commands.check_any(commands.has_guild_permissions(kick_members=True), has_modrole())
    async def cmd_kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: Optional[str]):
        async def modmail_enabled():
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                return True
            else:
                return False

        if not members:
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            sent = await ctx.send(embed=gen_embed(title="Invalid parameter(s) entered",
                                                  content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            return
        kicked = ""
        for member in members:
            dm_channel = member.dm_channel
            if member.dm_channel is None:
                dm_channel = await member.create_dm()

            m = await modmail_enabled()
            dm_embed = None
            if m:
                dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been kicked',
                                     content=f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                dm_embed.set_footer(text=ctx.guild.id)
            else:
                dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been kicked',
                                     content=f'Reason: {reason}')
                dm_embed.set_footer(text=time.ctime())
            try:
                await dm_channel.send(embed=dm_embed)
            except:
                await ctx.send(embed=gen_embed(title='Warning',
                                               content='This user does not accept DMs or there was an issue with sending DMs. I could not send them the message, but I will proceed with kicking the user.'))

            await ctx.guild.kick(member, reason=reason[:511])
            kicked = kicked + f'{member.name}#{member.discriminator} '

        embed = gen_embed(title='kick', content=f'{kicked}has been kicked.\nReason: {reason}')
        await ctx.send(embed=embed)
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        if document['log_channel'] and document['log_kbm']:
            msglog = int(document['log_channel'])
            logChannel = member.guild.get_channel(msglog)
            await logChannel.send(embed=embed)

    @commands.command(name='ban',
                      description='Ban user(s) from the server.',
                      help='Usage\n\n%ban [user mentions/user id/user name + discriminator (ex: name#0000)] <reason>')
    @commands.check_any(commands.has_guild_permissions(ban_members=True), has_modrole())
    async def cmd_ban(self, ctx, users: commands.Greedy[discord.User], *, reason: Optional[str]):
        async def modmail_enabled():
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                return True
            else:
                return False

        if not users:
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            sent = await ctx.send(embed=gen_embed(title="Invalid parameter(s) entered",
                                                  content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            return
        banned = ""
        for user in users:
            if ctx.guild.get_member(user.id):
                dm_channel = user.dm_channel
                if user.dm_channel is None:
                    dm_channel = await user.create_dm()

                m = await modmail_enabled()
                dm_embed = None
                if m:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been banned',
                                         content=f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                    dm_embed.set_footer(text=ctx.guild.id)
                else:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been banned',
                                         content=f'Reason: {reason}')
                dm_embed.set_footer(text=time.ctime())
                try:
                    await dm_channel.send(embed=dm_embed)
                except:
                    await ctx.send(embed = gen_embed(title='Warning', content = 'This user does not accept DMs or there was an issue sending DM. I will proceed with banning the user.'))
            if reason:
                await ctx.guild.ban(user, reason=reason[:511])
            else:
                await ctx.guild.ban(user)
            banned = banned + f'{user.name}#{user.discriminator} '

        embed = gen_embed(title='ban', content=f'{banned}has been banned.\nReason: {reason}')
        await ctx.send(embed=embed)
        document = await db.servers.find_one({"server_id": ctx.guild.id})
        if document['log_channel'] and document['log_kbm']:
            msglog = int(document['log_channel'])
            logChannel = member.guild.get_channel(msglog)
            await logChannel.send(embed=embed)

    @commands.command(name='strike',
                      description='Strike a user. After 3 strikes, the user is automatically banned.',
                      help='Usage\n\n%strike [severity] [user mentions/user ids/user name + discriminator (ex: name#0000)] [message_link] <reason>\nExample: `%strike 1 Example#0000 https://example.com This is your first strike. Reason is blah blah.`')
    @commands.check_any(commands.has_guild_permissions(ban_members=True), has_modrole())
    async def strike(self, ctx, severity: convert_severity, members: commands.Greedy[discord.Member], message_link: str,
                     *, reason):
        def convert_to_seconds(s):
            return int(timedelta(**{
                UNITS.get(m.group('unit').lower(), 'seconds'): int(m.group('val'))
                for m in re.finditer(r'(?P<val>\d+)(?P<unit>[smhdw]?)', s, flags=re.I)
            }).total_seconds())

        async def modmail_enabled():
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modmail_channel']:
                return True
            else:
                return False

        async def mutetime(attempts = 1):
            def check(m):
                return m.author == ctx.author

            await ctx.send(embed=gen_embed(title='Mute Duration',
                                           content='How long do you want to mute the user? Accepted format: ##[smhdw] (these correspond to seconds, minutes, hours, days, weeks)\n Example: 3d 6h -> 3 days, 6 hours'))
            msg = await self.bot.wait_for('message', check=check)
            if re.match(r'(\d+)([smhdw]?)', msg.clean_content, flags=re.I):
                return msg.clean_content
            elif attempts > 3:
                # exit out so we don't crash in a recursive loop due to user incompetency
                raise discord.ext.commands.BadArgument()
            else:
                await ctx.send(embed=gen_embed(title='Mute Duration',
                                               content="Sorry, I didn't catch that or it was an invalid format."))
                attempts += 1
                return await mutetime(attempts)

        time = datetime.datetime.utcnow()
        searchtime = time + relativedelta(seconds=3)
        if len(members) < 1:
            log.warning("Missing Required Argument")
            params = ' '.join([x for x in ctx.command.clean_params])
            await ctx.send(embed=gen_embed(title="Invalid or missing member(s) to strike",
                                           content=f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))
            return
        if not validators.url(message_link):
            log.warning('Error: Invalid Input')
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content="Invalid or missing message link. Check the formatting (https:// prefix is required)"))
            return
        if len(reason) >= 1024:
            log.warning('Error: Reason too long')
            await ctx.send(embed=gen_embed(title='Max character limit reached',
                                           content=f'Your reason message is too long ({len(reason) - 1024} characters over limit). Please shorten the message to fit it in the embed.'))
            return

        m = await modmail_enabled()
        if m:
            embed_message = f'Reason: {reason}\nMessage Link: {message_link}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.'
            if len(embed_message) > 1024:
                log.warning('Error: Reason too long')
                await ctx.send(embed=gen_embed(title='Max character limit reached',
                                               content=f'Your reason message is too long ({len(embed_message) - 1024} characters over limit). Please shorten the message to fit it in the embed.'))
        else:
            embed_message = f'Reason: {reason}\nMessage Link: {message_link}'
            if len(embed_message) > 1024:
                log.warning('Error: Reason too long')
                await ctx.send(embed=gen_embed(title='Max character limit reached',
                                               content=f'Your reason message is too long ({len(embed_message) - 1024} characters over limit). Please shorten the message to fit it in the embed.'))

        if severity == '2':
            msg = await mutetime()
            mtime = convert_to_seconds(msg)
            mutedRole = discord.utils.get(ctx.guild.roles, name="Muted")

            if not mutedRole:
                mutedRole = await ctx.guild.create_role(name="Muted")

                for channel in ctx.guild.channels:
                    await channel.set_permissions(mutedRole, speak=False, send_messages=False)

        for member in members:
            dm_channel = member.dm_channel
            if member.dm_channel is None:
                dm_channel = await member.create_dm()

            # move this out to a separate method
            post = {
                'time': time,
                'server_id': ctx.guild.id,
                'user_name': f'{member.name}#{member.discriminator}',
                'user_id': member.id,
                'moderator': ctx.author.name,
                'message_link': message_link,
                'reason': reason
            }
            if severity == '1':
                await db.warns.insert_one(post)
            elif severity == '2':
                await db.warns.insert_one(post)
                #this is stupid and i hate it but it is what it is
                npost = {
                    'time': time + relativedelta(seconds=1),
                    'server_id': ctx.guild.id,
                    'user_name': f'{member.name}#{member.discriminator}',
                    'user_id': member.id,
                    'moderator': ctx.author.name,
                    'message_link': message_link,
                    'reason': reason
                }
                await db.warns.insert_one(npost)
            elif severity == '3':
                await db.warns.insert_one(post)
                npost = {
                    'time': time + relativedelta(seconds=1),
                    'server_id': ctx.guild.id,
                    'user_name': f'{member.name}#{member.discriminator}',
                    'user_id': member.id,
                    'moderator': ctx.author.name,
                    'message_link': message_link,
                    'reason': reason
                }
                await db.warns.insert_one(npost)
                nnpost = {
                    'time': time + relativedelta(seconds=2),
                    'server_id': ctx.guild.id,
                    'user_name': f'{member.name}#{member.discriminator}',
                    'user_id': member.id,
                    'moderator': ctx.author.name,
                    'message_link': message_link,
                    'reason': reason
                }
                await db.warns.insert_one(nnpost)

            dm_embed = None
            if m:
                dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                     title='You have been given a strike',
                                     content=embed_message)
            else:
                dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                     title='You have been given a strike',
                                     content=embed_message)
            dm_embed.set_footer(text=ctx.guild.id)
            try:
                await dm_channel.send(embed=dm_embed)
            except discord.errors.Forbidden:
                await ctx.send(embed=gen_embed(title='Warning',
                                               content='This user does not accept DMs. I could not send them the message, but I will proceed with striking the user.'))

            if len(ctx.message.attachments) > 0:
                attachnum = 1
                for attachment in ctx.message.attachments:
                    embed = gen_embed(name=f'{ctx.guild.name}', icon_url=ctx.guild.icon_url, title='Attachment',
                                      content=f'Attachment #{attachnum}:')
                    embed.set_image(url = attachment.url)
                    embed.set_footer(text=f'{ctx.guild.id}')
                    await dm_channel.send(embed=embed)
                    attachnum += 1

            embed = gen_embed(name=f'{member.name}#{member.discriminator}', icon_url=member.avatar_url,
                              title='Strike recorded',
                              content=f'{ctx.author.name}#{ctx.author.discriminator} gave a strike to {member.name}#{member.discriminator} | {member.id}')
            embed.add_field(name='Severity', value=f'{severity} strike(s)', inline=False)
            embed.add_field(name='Reason', value=f'{reason}\n\n[Go to message/evidence]({message_link})', inline=False)
            embed.set_footer(text=time.ctime())
            await ctx.send(embed=embed)
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['log_channel'] and document['log_strikes']:
                msglog = int(document['log_channel'])
                logChannel = member.guild.get_channel(msglog)
                await logChannel.send(embed=embed)

            valid_strikes = []  # probably redundant but doing it anyways to prevent anything stupid
            results = await check_strike(ctx, member, time=searchtime, valid_strikes=valid_strikes)
            log.info(results)

            # ban check should always come before mute
            if len(results) >= document['max_strike']:
                max_strike = document['max_strike']
                dm_channel = member.dm_channel
                if member.dm_channel is None:
                    dm_channel = await user.create_dm()

                m = await modmail_enabled()
                dm_embed = None
                if m:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been banned',
                                         content=f'Reason: {reason}\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                    dm_embed.set_footer(text=ctx.guild.id)
                else:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url, title='You have been banned',
                                         content=f'Reason: {reason}')
                    dm_embed.set_footer(text=time.ctime())
                try:
                    await dm_channel.send(embed=dm_embed)
                except discord.errors.Forbidden:
                    await ctx.send(embed=gen_embed(title='Warning',
                                                   content='This user does not accept DMs. I could not send them the message, but I will proceed with striking and banning the user.'))
                await ctx.guild.ban(member,
                                    reason=f'You have accumulated {max_strike} strikes and therefore will be banned from the server.')
                if document['log_channel'] and document['log_kbm']:
                    msglog = int(document['log_channel'])
                    logChannel = ctx.guild.get_channel(msglog)
                    embed = gen_embed(title='ban',
                                      content=f'{member.name} (ID: {member.id} has been banned.\nReason: Accumulated maximum # of strikes')
                    await logChannel.send(embed=embed)
                return #if this happens we should zip out

            elif len(results) == 2 and severity != 2:
                # we need to do this now since severity was not 2
                # yes it's kinda redundant to do it here but this reduces calls to the DB
                msg = await mutetime()
                mtime = convert_to_seconds(msg)
                mutedRole = discord.utils.get(ctx.guild.roles, name="Muted")

                if not mutedRole:
                    mutedRole = await ctx.guild.create_role(name="Muted")

                    for channel in ctx.guild.channels:
                        await channel.set_permissions(mutedRole, speak=False, send_messages=False)

            if severity == '2' or len(results) == 2:
                await member.add_roles(mutedRole)

                if m:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted for {mtime} seconds',
                                         content=f'Strike 2 - automatic mute\n\nIf you have any issues, you may reply (use the reply function) to this message and send a modmail.')
                    dm_embed.set_footer(text=ctx.guild.id)
                else:
                    dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon_url,
                                         title=f'You have been muted for {mtime} seconds',
                                         content=f'Strike 2 - automatic mute')
                    dm_embed.set_footer(text=time.ctime())
                try:
                    await dm_channel.send(embed=dm_embed)
                except discord.errors.Forbidden:
                    await ctx.send(embed=gen_embed(title='Warning',
                                                   content='This user does not accept DMs. I could not send them the message, but I will proceed with striking and muting the user.'))
                await ctx.send(embed=gen_embed(title='mute', content=f'{member.mention} has been muted.'))
                if document['log_channel'] and document['log_kbm']:
                    msglog = int(document['log_channel'])
                    logChannel = ctx.guild.get_channel(msglog)
                    embed = gen_embed(title='ban',
                                      content=f'{member.name} (ID: {member.id} has been muted for {mtime} seconds.\nReason: Strike severity 2')
                    await logChannel.send(embed=embed)  # do custom
                await asyncio.sleep(mtime)
                await member.remove_roles(mutedRole)
                return

    @commands.command(name='lookup',
                      description='Lookup strikes for a user. Returns all currently active strikes.',
                      help='Usage\n\n%lookup [user mention/user id]')
    @commands.check_any(commands.has_guild_permissions(view_audit_log=True), has_modrole())
    async def lookup(self, ctx, member: discord.User):
        valid_strikes = []  # probably redundant but doing it anyways to prevent anything stupid
        results = await check_strike(ctx, member, time=datetime.datetime.utcnow() + relativedelta(minutes=2),
                                     valid_strikes=valid_strikes)
        num_strikes = len(results)
        # pull all of the documents now, cross reference with active strikes to determine the expired ones
        expired_query = {'server_id': ctx.guild.id, 'user_id': member.id}
        expired_results = db.warns.find(expired_query).sort('time', pymongo.DESCENDING)

        embed = gen_embed(name=f'{member.name}#{member.discriminator}', icon_url=member.avatar_url,
                          title='Strike Lookup', content=f'Found {num_strikes} active strikes for this user.')
        for document in results:
            documentid = document['_id']
            stime = document['time']
            reason = document['reason']
            message_link = document['message_link']
            moderator = document['moderator']
            embed_message = f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {reason}\n[Go to message/evidence]({message_link})'
            if len(embed_message) > 1024:
                truncate = len(reason) - (len(embed_message) - 1024) - 4
                truncatedreason = reason[0:truncate] + "..."
                embed.add_field(name=f'Strike | {stime.ctime()}',
                                value=f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {truncatedreason}\n[Go to message/evidence]({message_link})',
                                inline=False)
            else:
                embed.add_field(name=f'Strike | {stime.ctime()}',
                                value=f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {reason}\n[Go to message/evidence]({message_link})',
                                inline=False)
        async for document in expired_results:
            if document not in results:
                documentid = document['_id']
                stime = document['time']
                reason = document['reason']
                message_link = document['message_link']
                moderator = document['moderator']
                embed_message = f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {reason}\n[Go to message/evidence]({message_link})'
                if len(embed_message) > 1024:
                    truncate = len(reason) - (len(embed_message) - 1024) - 4
                    truncatedreason = reason[0:truncate] + "..."
                    embed.add_field(name=f'Strike | {stime.ctime()}',
                                    value=f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {truncatedreason}\n[Go to message/evidence]({message_link})',
                                    inline=False)
                else:
                    embed.add_field(name=f'Strike (EXPIRED) | {stime.ctime()}',
                                    value=f'Strike UID: {documentid} | Moderator: {moderator}\nReason: {reason}\n[Go to message/evidence]({message_link})',
                                    inline=False)
        embed.set_footer(text=f'UID: {member.id}')
        await ctx.send(embed=embed)

    @commands.command(name='removestrike',
                      description='Remove a strike from the database.',
                      help='Usage\n\n%removestrike [strike UID]\n(This is found using %lookup)')
    async def removestrike(self, ctx, strikeid: str):
        deleted = await db.warns.delete_one({"_id": ObjectId(strikeid)})
        if deleted.deleted_count == 1:
            embed = gen_embed(title='Strike Deleted', content=f'Strike {strikeid} was deleted.')
            await ctx.send(embed=embed)
        elif deleted.deleted_count == 0:
            log.warning(f'Error while deleting strike')
            await ctx.send(embed=gen_embed(title='Error',
                                           content="Was unable to delete strike. Check your UID. If correct, something may be wrong with the database or the strike does not exist."))

    @commands.command(name='slowmode',
                      description='Enables slowmode for the channel you are in. Time is in seconds.',
                      help='Usage\n\n%slowmode [time]')
    @commands.check_any(commands.has_guild_permissions(manage_channels=True), has_modrole())
    async def slowmode(self, ctx, time: int):
        await ctx.channel.edit(slowmode_delay=0)
        await ctx.send(embed=gen_embed(title='slowmode',
                                       content=f'Slowmode has been enabled in {ctx.channel.name}\n({time} seconds)'))

    @commands.command(name='shutdown',
                      description='Shuts down the bot. Only owner can use this command.')
    @is_owner()
    async def shutdown(self, ctx):
        await self.close()

    @shutdown.error
    async def shutdown_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            log.warning("Error: Permission Error")
            await ctx.send(
                embed=gen_embed(title='Permission Error', content="Sorry, you don't have access to this command."))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        document = await db.servers.find_one({"server_id": message.guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                if not message.author.id == self.bot.user.id and message.author.bot == False:
                    gprefix = prefix(self.bot, message)
                    if re.match(f'^\\{gprefix}', message.content) == None:
                        cleanMessage = re.sub('<@!?&?\d{17,18}>', '[removed mention]', message.content)
                        logChannel = message.guild.get_channel(msglog)
                        content = discord.Embed(colour=0x1abc9c)
                        content.set_author(name=f"{message.author.name}#{message.author.discriminator}",
                                           icon_url=message.author.avatar_url)
                        content.set_footer(text=f"UID: {message.author.id} | {time.ctime()}")
                        content.title = f"Message deleted in #{message.channel.name}"
                        content.description = f"**Message Content:** {cleanMessage}"
                        if len(message.attachments) > 0:
                            content.add_field(name="Attachment:", value="\u200b")
                            content.set_image(url=message.attachments[0].proxy_url)
                        await logChannel.send(embed=content)
        except:
            pass

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        document = await db.servers.find_one({"server_id": messages[0].guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                for message in messages:
                    if not message.author.id == self.bot.user.id and message.author.bot == False:
                        gprefix = prefix(self.bot, message)
                        if re.match(f'^\\{gprefix}', message.content) == None:
                            cleanMessage = re.sub('<@!?&?\d{17,18}>', '[removed mention]', message.content)
                            logChannel = message.guild.get_channel(msglog)
                            content = discord.Embed(colour=0x1abc9c)
                            content.set_author(name=f"{message.author.name}#{message.author.discriminator}",
                                               icon_url=message.author.avatar_url)
                            content.set_footer(text=f"UID: {message.author.id} | {time.ctime()}")
                            content.title = f"Message deleted in #{message.channel.name}"
                            content.description = f"**Message Content:** {cleanMessage}"
                            if len(message.attachments) > 0:
                                content.add_field(name="Attachment:", value="\u200b")
                                content.set_image(url=message.attachments[0].proxy_url)
                            await logChannel.send(embed=content)
        except:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        document = await db.servers.find_one({"server_id": before.guild.id})
        try:
            if document['log_channel']:
                msglog = int(document['log_channel'])
                if not before.author.id == self.bot.user.id and before.author.bot == False:
                    if not before.content == after.content:
                        logChannel = before.guild.get_channel(msglog)
                        content = discord.Embed(colour=0x1abc9c)
                        content.set_author(name=f"{before.author.name}#{before.author.discriminator}",
                                           icon_url=before.author.avatar_url)
                        content.set_footer(text=f"UID: {before.author.id} | {time.ctime()}")
                        content.title = f"Message edited in #{before.channel.name}"
                        content.description = f"**Before:** {before.clean_content}\n**After:** {after.clean_content}"
                        await logChannel.send(embed=content)
        except:
            pass


# This method will spit out the list of valid strikes. we can cross reference the entire list of strikes to determine which ones are expired on the lookup command.
# We can also check the length of the list when giving out strikes to determine if an automatic ban is required.
# Currently, there are 5 scenarios:
#   1. No strikes active (none in past 2 months OR one in past 4 months but none in the 2 months immediately prior to that strike)
#   2. One strike active (past 2 months)
#   3. One strike active due to the presence of two strikes within two months (First strike expired, second is still active)
#   4. Two strikes active (past 2 months)
#   5. Three strikes active (proceed to ban the user)
async def check_strike(ctx, member, time=datetime.datetime.utcnow(), valid_strikes=[]):
    log.info(time)  # this is here for debugging race condition atm

    # Create the search query
    expire_date = time + relativedelta(months=-2)
    query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date, '$lt': time}}
    results = await db.warns.count_documents(query)

    if results > 0:
        # This case means we have an active strike. let's check the next strike to see if it's within 2 months of this strike.
        # This sorts our query by date and will return the latest strike
        log.info('found strike, beginning search process')
        results = db.warns.find(query).sort('time', pymongo.DESCENDING).limit(1)
        document = await results.to_list(length=None)
        document = document.pop()
        valid_strikes.append(document)

        if len(valid_strikes) >= 3:
            # Ban time boom boom. stop searching and step out
            log.info('max_strike exceeded, proceed to ban')
            return valid_strikes

        # Else it's time to step in and start the recursion to check the next two months again.
        # If the second strike is found, we will step in one final time to check for the third and final strike. 
        newtime = document['time']
        return await check_strike(ctx, member, time=newtime, valid_strikes=valid_strikes)

        # If we didn't find any strikes in the past 2 months, we still need to check for the third case.
    # A recent strike might still be decaying due to the reset decay timer so let's check the past 4 months.
    elif len(valid_strikes) == 0:
        log.info('no valid strikes in past 2 months')
        # Create new search query
        expire_date = time + relativedelta(months=-4)
        query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date, '$lt': time}}
        results = await db.warns.count_documents(query)

        if results > 0:
            # We found a strike! let's check to see if there's another strike within 2 months of this one.
            expire_date = time + relativedelta(months=-2)
            query = {'server_id': ctx.guild.id, 'user_id': member.id, 'time': {'$gte': expire_date, '$lt': time}}
            results = db.warns.find(query).sort('time', pymongo.DESCENDING).limit(1)
            resultsnum = await db.warns.count_documents(query)
            if resultsnum > 0:
                sdocument = await results.to_list(length=None)
                sdocument = sdocument.pop()
                sresults = await db.warns.count_documents(query)

                if sresults > 0:
                    # We found a second strike. That means this second strike is expired, but the first strike is active.
                    # Remember, the first strike in this case is the most recent, while second is older. It's flipped from terminology.
                    valid_strikes.append(sdocument)
        return valid_strikes

    else:
        # This means we didn't get a hit, so let's step out and spit out our list.
        log.info('all strike cases false')
        return valid_strikes


def setup(bot):
    bot.add_cog(Administration(bot))
