from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log

class Administration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot