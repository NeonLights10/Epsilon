import discord

from formatting.constants import VERSION as BOTVERSION
from __main__ import bot, log

def gen_embed(name = None, icon_url = None, title = None, content = None):
        """Provides a basic template for embeds"""
        e = discord.Embed(colour = 0x1abc9c)
        if name and icon_url:
        	e.set_author(name = name, icon_url = icon_url)
        else:
        	e.set_author(name = f"Epsilon v{BOTVERSION}", icon_url = bot.user.avatar_url)
        e.set_footer(text = "Sugoi!")
        e.title = title
        e.description = content
        return e 