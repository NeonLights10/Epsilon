import discord
from discord.ext import commands

from formatting.embed import gen_embed
from __main__ import log, db, check_document, initialize_document

async def on_guild_join(guild):
    await check_document(guild, guild.id)

    status = discord.Game(f'{default_prefix}help | {len(bot.guilds)} servers')
    await bot.change_presence(activity=status)

    general = find(lambda x: x.name == 'general', guild.text_channels)
    if general and general.permissions_for(guild.me).send_messages:
        embed = gen_embed(name=f'{guild.name}',
                          icon_url=guild.icon.url,
                          title='Thanks for inviting me!',
                          content=("You can get started by typing %help to find the current command list.\n"
                                   "Change the command prefix by typing %setprefix, and configure server "
                                   "settings with %serverconfig and %channelconfig.\n\n"
                                   "Source code: https://github.com/neonlights10/Epsilon\n"
                                   "Support: https://www.patreon.com/kanonbot or https://ko-fi.com/neonlights\n"
                                   "If you have feedback or need help, please DM Neon#5555 or join the server "
                                   "at https://discord.gg/AYTFJY8VhF")
                          )
        await general.send(embed=embed)
        await general.send(embed=gen_embed(title='Thank you Kanon Supporters!',
                                           content=(
                                               "**Thanks to:**\nReileky#4161, SinisterSmiley#0704, Makoto#7777,"
                                               " Vince.#6969, Elise ☆#0001, EN_Gaige#3910, shimmerleaf#2115, "
                                               "Hypnotic Rhythm#1260, wachie#0320, Ashlyne#8080")
                                           )
                           )
        return
    else:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = gen_embed(name=f'{guild.name}',
                                  icon_url=guild.icon.url,
                                  title='Thanks for inviting me!',
                                  content=("You can get started by typing %help to find the current command list.\n"
                                           "Change the command prefix by typing %setprefix, and configure server "
                                           "settings with %serverconfig and %channelconfig.\n\n"
                                           "Source code: https://github.com/neonlights10/Epsilon\n"
                                           "Support: https://www.patreon.com/kanonbot or "
                                           "https://ko-fi.com/neonlights\n "
                                           "If you have feedback or need help, please DM Neon#5555 or join the "
                                           "server at https://discord.gg/AYTFJY8VhF.")
                                  )
                await channel.send(embed=embed)
                await channel.send(embed=gen_embed(title='Thank you Kanon Supporters!',
                                                   content=("**Thanks to:**\nReileky#4161, SinisterSmiley#0704, "
                                                            "Makoto#7777, Vince.#6969, Elise ☆#0001, "
                                                            "EN_Gaige#3910, shimmerleaf#2115, "
                                                            "Hypnotic Rhythm#1260, wachie#0320, Ashlyne#8080")
                                                   )
                                   )
                return


async def on_member_join(member):
    log.info(f"A new member joined in {member.guild.name}")
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['autorole']:
        role = discord.utils.find(lambda r: r.id == int(document['autorole']), member.guild.roles)
        if role:
            await member.add_roles(role)
            log.info("Auto-assigned role to new member in {}".format(member.guild.name))
        else:
            log.error("Auto-assign role does not exist!")
    if document['welcome_message'] and document['welcome_channel']:
        welcome_channel = find(lambda c: c.id == int(document['welcome_channel']), member.guild.text_channels)
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title=f"Welcome to {member.guild.name}",
                          content=document['welcome_message'])
        if document['welcome_banner']:
            embed.set_image(url=document['welcome_banner'])
        await welcome_channel.send(embed=embed)
    if document['log_joinleaves'] and document['log_channel']:
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title="Member joined",
                          content=f"Member #{member.guild.member_count}")
        msglog = int(document['log_channel'])
        log_channel = member.guild.get_channel(msglog)
        await log_channel.send(embed=embed)


async def on_member_remove(member):
    document = await db.servers.find_one({"server_id": member.guild.id})
    if document['log_joinleaves'] and document['log_channel']:
        jointime = member.joined_at
        nowtime = datetime.datetime.now(datetime.timezone.utc)
        embed = gen_embed(name=f"{member.name}#{member.discriminator}",
                          icon_url=member.display_avatar.url,
                          title="Member left",
                          content=f"Joined {member.joined_at} ({nowtime - jointime} ago)")
        msglog = int(document['log_channel'])
        log_channel = member.guild.get_channel(msglog)
        await log_channel.send(embed=embed)


def setup(bot):
    bot.add_listener(on_guild_join)
    bot.add_listener(on_member_join)
    bot.add_listener(on_member_remove)
