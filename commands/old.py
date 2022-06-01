from typing import Optional

import discord
from discord.ext import commands

from __main__ import log
from formatting.embed import gen_embed


class Old(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='old',
                      aliases=['setprefix', 'setmodrole', 'autorole', 'blacklist', 'whitelist', 'channelconfig',
                               'welcomeconfig', 'serverconfig', 'purgeid', 'addrole', 'removerole', 'adduser',
                               'removeuser', 'setupverify', 'timeout', 'removetimeout', 'kick', 'ban', 'strike',
                               'lookup', 'removestrike', 'slowmode', 'hug', 'cuddle', 'headpat', 'stats',
                               'joinserver', 'support', 'shoutout', 'deleteguild', 'deleteuser', 'unload', 'load',
                               'reload', 'announce', 'updatedb', 'modmail', 'remindme', 'reminder', 'delete',
                               'remove', 'del', 'forgetme', 'modify', 'missing', 'trackfiller', 'efficiencyguide',
                               'vsliveguide', 'giftbox', 'roll', 'froll', 'time', 'tconvert', 'reactcategory',
                               'reactrole'])
    async def old(self, ctx, msg_content: Optional[str]):
        embed = gen_embed(title=':warning: Kanon Bot is Moving to Slash Commands!',
                          content=('You must now use / as the prefix to use Kanon Bot.\n\n'
                                   '**HOWEVER**, some commands will retain their original prefix to ensure feature'
                                   ' parity or for speed reasons.\n'
                                   'Type `/` or `/help` to see a list of available commands and what prefix to use.\n\n'
                                   'If you cannot see slash commands, ask a server admin to invite the bot again'
                                   ' using the following link: https://s-neon.xyz/kanon'))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Old(bot))
