elif severity != '2' and ctx.guild.id == 432379300684103699:
msg = await imagemute()
if msg is None:
    return
else:
    mtime = convert_to_seconds(msg)
    mutedRole = discord.utils.get(ctx.guild.roles, name="Image Mute")

    await member.add_roles(mutedRole)

    if m:
        dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon.url,
                             title=f'You have had your image/external emote privileges revoked for for {mtime} seconds',
                             content=f'If you have any issues, you may reply (use the reply function) to this message and send a modmail.')
        dm_embed.set_footer(text=ctx.guild.id)
    else:
        dm_embed = gen_embed(name=ctx.guild.name, icon_url=ctx.guild.icon.url,
                             title=f'You have been image/external emote privileges revoked for for {mtime} seconds',
                             content=f'This is a result of your strike.')
        dm_embed.set_footer(text=time.ctime())
    try:
        await dm_channel.send(embed=dm_embed)
    except discord.Forbidden:
        await ctx.send(embed=gen_embed(title='Warning',
                                       content='This user does not accept DMs. I could not send them the message, but I will proceed with striking and muting the user.'))
    await ctx.send(embed=gen_embed(title='mute', content=f'{member.mention} has been muted.'))
    if document['log_channel'] and document['log_kbm']:
        msglog = int(document['log_channel'])
        logChannel = ctx.guild.get_channel(msglog)
        embed = gen_embed(title='mute',
                          content=f'{member.name} (ID: {member.id} has had their image/external emote privileges revoked for {mtime} seconds.\nReason: Moderator specified')
        await logChannel.send(embed=embed)  # do custom
    await asyncio.sleep(mtime)
    await member.remove_roles(mutedRole)
    return


async def imagemute(attempts=1):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    await ctx.send(embed=gen_embed(title='Image Mute',
                                   content='Do you want to revoke image/external emote privileges? Accepted answers: yes/no y/n'))
    try:
        imsg = await self.bot.wait_for('message', check=check, timeout=60.0)
    except asyncio.TimeoutError:
        await ctx.send(embed=gen_embed(title='Mute cancelled',
                                       content='Strike has still been applied.'))
        return
    if re.match('^Yes|y', imsg.clean_content):
        return await mutetime()
    if re.match('^No|n', imsg.clean_content):
        return
    elif attempts > 3:
        # exit out so we don't crash in a recursive loop due to user incompetency
        raise discord.ext.commands.BadArgument()
    else:
        await ctx.send(embed=gen_embed(title='Image Mute',
                                       content="Sorry, I didn't catch that or it was an invalid format."))
        attempts += 1
        return await imagemute(attempts)