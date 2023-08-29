import discord
import re
import math
import time
import asyncio
import datetime

from formatting.embed import gen_embed
from __main__ import check_document, default_prefix, bot, db, log, get_prefix


async def on_guild_join(guild):
    await check_document(guild, guild.id)

    status = discord.Game(f'/help | {len(bot.guilds)} servers')
    await bot.change_presence(activity=status)

    general = discord.utils.find(lambda x: x.name == 'general', guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        embed = gen_embed(name=f'{guild.name}',
                          icon_url=guild.icon.url,
                          title='Thanks for inviting me!',
                          content=('You can get started by typing `/help` to find the current command list.'
                                   '\nChange the command prefix and configure server settings using `/settings`!\n\n'
                                   'Source code: https://github.com/neon10lights/Epsilon\n'
                                   'Support: https://www.patreon.com/kanonbot or https://ko-fi.com/neonlights\n'
                                   'If you have feedback or need help, please DM Neon#5555 or join the server at '
                                   'https://discord.gg/AYTFJY8VhF'))
        await general.send(embed=embed)
        await general.send(embed=gen_embed(title='Thank you Kanon Supporters!',
                                           content=('**Thanks to:**\nReileky#4161, SinisterSmiley#0704, Makoto#7777, '
                                                    'Vince.#6969, Elise ☆#0001, EN_Gaige#3910, shimmerleaf#2115, '
                                                    'Hypnotic Rhythm#1260, wachie#0320, Ashlyne#8080, nehelenia#4489, '
                                                    'careblaire#6969, Reileky#4161')))
        return
    else:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = gen_embed(name=f'{guild.name}',
                                  icon_url=guild.icon.url,
                                  title='Thanks for inviting me!',
                                  content=('You can get started by typing `/help` to find the current command list.'
                                           '\nChange the command prefix and configure server settings using `/settings`'
                                           '!\n\nSource code: https://github.com/neon10lights/Epsilon\n'
                                           'Support: https://www.patreon.com/kanonbot or https://ko-fi.com/neonlights\n'
                                           'If you have feedback or need help, please DM Neon#5555 or join the server '
                                           'at https://discord.gg/AYTFJY8VhF'))
                await channel.send(embed=embed)
                await channel.send(embed=gen_embed(title='Thank you Kanon Supporters!',
                                                   content=('**Thanks to:**\nReileky#4161, SinisterSmiley#0704, '
                                                            'Makoto#7777, Vince.#6969, Elise ☆#0001, EN_Gaige#3910, '
                                                            'shimmerleaf#2115, Hypnotic Rhythm#1260, wachie#0320, '
                                                            'Ashlyne#8080, nehelenia#4489, careblaire#6969, '
                                                            'Reileky#4161')))
                return


async def on_message_delete(message):
    try:
        document = await db.servers.find_one({"server_id": message.guild.id})
    except AttributeError:
        return

    try:
        if msglog := int(document['log_channel']):
            if not message.author.id == bot.user.id and message.author.bot is False:
                prefix = await get_prefix(bot, message)
                if re.match(f'^{prefix}', message.content) is None:
                    log_channel = message.guild.get_channel(msglog)
                    sent_time = math.trunc(time.mktime(message.created_at.timetuple()))
                    content = gen_embed(name=f'{message.author.name}#{message.author.discriminator}',
                                        icon_url=message.author.display_avatar.url,
                                        title=f'Message deleted in {message.channel.name}',
                                        content=f'Message sent <t:{sent_time}>')
                    content.add_field(name='Content',
                                      value=message.clean_content,
                                      inline=False)
                    content.add_field(name='ID',
                                      value=f'```ml\nUser = {message.author.id}\nMessage = {message.id}```',
                                      inline=False)
                    content.set_footer(text=time.ctime())
                    if len(message.attachments) > 0:
                        content.add_field(name="Attachment:", value="\u200b")
                        content.set_image(url=message.attachments[0].proxy_url)
                    await log_channel.send(embed=content)
    except TypeError:
        pass
    except Exception as e:
        log.info(f'Error occurred while tracking message deletion: {e}')
        pass


async def on_bulk_message_delete(messages):
    document = await db.servers.find_one({"server_id": messages[0].guild.id})
    try:
        if msglog := int(document['log_channel']):
            for message in messages:
                if not message.author.id == bot.user.id and message.author.bot is False:
                    prefix = await get_prefix(bot, message)
                    if re.match(f'^{prefix}', message.content) is None:
                        log_channel = message.guild.get_channel(msglog)
                        sent_time = math.trunc(time.mktime(message.created_at.timetuple()))
                        content = gen_embed(name=f'{message.author.name}#{message.author.discriminator}',
                                            icon_url=message.author.display_avatar.url,
                                            title=f'Message deleted in #{message.channel.name}',
                                            content=f'Message sent <t:{sent_time}>')
                        content.add_field(name='Content',
                                          value=message.clean_content,
                                          inline=False)
                        content.add_field(name='ID',
                                          value=f'```ml\nUser = {message.author.id}\nMessage = {message.id}```',
                                          inline=False)
                        content.set_footer(text=time.ctime())
                        if len(message.attachments) > 0:
                            content.add_field(name="Attachment:", value="\u200b")
                            content.set_image(url=message.attachments[0].proxy_url)
                        await log_channel.send(embed=content)
                        await asyncio.sleep(1)
    except TypeError:
        pass
    except Exception as e:
        log.info(f'Error occurred while tracking bulk message deletion: {e}')
        pass


async def on_raw_message_delete(payload):
    if payload.guild_id:
        document = await db.servers.find_one({"server_id": payload.guild_id})
        try:
            if msglog := int(document['log_channel']):
                if not payload.cached_message:
                    guild = bot.get_guild(payload.guild_id)
                    log_channel = guild.get_channel(msglog)
                    content = gen_embed(title=f'Message deleted in #{guild.get_channel(payload.channel_id).name}',
                                        content=f'```ml\nMessage ID = {payload.message_id}```')
                    await log_channel.send(embed=content)
        except TypeError:
            pass
        except Exception as e:
            log.info(f'Error occurred while tracking raw message deletion: {e}')
            pass


async def on_message_edit(before, after):
    try:
        document = await db.servers.find_one({'server_id': before.guild.id})
    except AttributeError:
        # prevent error when "editing ephemerals"
        return
    try:
        if msglog := int(document['log_channel']):
            if not before.author.id == bot.user.id and before.author.bot is False:
                if not before.content == after.content:
                    log_channel = before.guild.get_channel(msglog)
                    content = gen_embed(name=f'{before.author.name}#{before.author.discriminator}',
                                        icon_url=before.author.display_avatar.url,
                                        title=f'Message edited in #{before.channel.name}',
                                        content=f'[Go to Message]({after.jump_url})')
                    content.add_field(name='Previous',
                                      value=before.clean_content,
                                      inline=False)
                    content.add_field(name='Current',
                                      value=after.clean_content,
                                      inline=False)
                    content.add_field(name='ID',
                                      value=f'```ml\nUser = {after.author.id}\nMessage = {after.id}```',
                                      inline=False)
                    content.set_footer(text=time.ctime())
                    await log_channel.send(embed=content)
    except TypeError:
        pass
    except Exception as e:
        log.info(f'Error occurred while tracking message edits: {e}')
        pass


async def on_member_join(member):
    log.info(f'A new member joined in {member.guild.name}')
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['autorole']:
        role = discord.utils.find(lambda r: r.id == int(document['autorole']), member.guild.roles)
        if role:
            await member.add_roles(role)
            log.info(f"Auto-assigned role to new member in {member.guild.name}")
        else:
            log.error(f"Could not find auto assign role for {member.guild.name}!")
    if document['log_joinleaves'] and document['log_channel']:
        log_channel = member.guild.get_channel(int(document['log_channel']))
        content = gen_embed(name=f'{member.name}#{member.discriminator}',
                            icon_url=member.display_avatar.url,
                            title="Member joined",
                            content=f'{member.name}#{member.discriminator} {member.mention}',
                            colour=0x2ecc71)
        content.add_field(name='Joined At',
                          value=f'<t:{math.trunc(time.mktime(member.joined_at.timetuple()))}>',
                          inline=False)
        account_age = (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days
        content.add_field(name='Account Age',
                          value=f'**{account_age}** days',
                          inline=True)
        content.add_field(name='Member Count',
                          value=member.guild.member_count,
                          inline=True)
        query = {'server_id': member.guild.id, 'user_id': member.id}
        results = db.warns.find(query)
        results = await results.to_list(length=None)
        results = len(results)
        content.add_field(name='Previous Strikes',
                          value=results,
                          inline=True)
        content.add_field(name='ID',
                          value=f'```ml\nMember = {member.id}```',
                          inline=False)
        content.set_footer(text=time.ctime())
        await log_channel.send(embed=content)


async def on_member_remove(member):
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['log_joinleaves'] and document['log_channel']:
        log_channel = member.guild.get_channel(int(document['log_channel']))
        content = gen_embed(name=f'{member.name}#{member.discriminator}',
                            icon_url=member.display_avatar.url,
                            title="Member left",
                            content=f'{member.name}#{member.discriminator} {member.mention}',
                            colour=0xe74c3c)
        join_unix = math.trunc(time.mktime(member.joined_at.timetuple()))
        content.add_field(name='Joined At',
                          value=f'<t:{join_unix}> (<t:{join_unix}:R>)',
                          inline=False)
        create_unix = math.trunc(time.mktime(member.created_at.timetuple()))
        content.add_field(name='Joined At',
                          value=f'<t:{create_unix}> (<t:{create_unix}:R>)',
                          inline=False)
        content.add_field(name='ID',
                          value=f'```ml\nMember = {member.id}```',
                          inline=False)
        content.set_footer(text=time.ctime())
        await log_channel.send(embed=content)


async def on_member_update(before, after):
    document = await db.servers.find_one({'server_id': before.guild.id})
    if document['log_joinleaves'] and int(document['log_channel']):
        if not before.nick == after.nick:
            log_channel = before.guild.get_channel(int(document['log_channel']))
            content = gen_embed(name=f'{after.name}#{after.discriminator}',
                                icon_url=after.display_avatar.url,
                                title="Member updated",
                                content=f'{after.name}#{after.discriminator} {after.mention}',
                                colour=0xFEE75C)
            content.add_field(name='Previous name',
                              value=f'{before.nick}#{before.discriminator}',
                              inline=False)
            content.add_field(name='Current name',
                              value=f'{after.nick}#{after.discriminator}',
                              inline=False)
            content.add_field(name='ID',
                              value=f'```ml\nUser = {after.author.id}```',
                              inline=False)
            content.set_footer(text=time.ctime())
            await log_channel.send(embed=content)


async def on_application_command(context):
    log.info(f'{context.interaction.user.name}#{context.interaction.user.discriminator} ({context.interaction.user.id})'
             f' | {context.command.qualified_name} {context.selected_options}')


def setup(bot):
    bot.add_listener(on_guild_join)
    bot.add_listener(on_member_join)
    bot.add_listener(on_member_remove)
    bot.add_listener(on_message_edit)
    bot.add_listener(on_message_delete)
    bot.add_listener(on_raw_message_delete)
    bot.add_listener(on_bulk_message_delete)
    bot.add_listener(on_application_command)
