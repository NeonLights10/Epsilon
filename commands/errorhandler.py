import discord
import traceback
import sys

from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log

class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """The event triggered when an error is raised while invoking a command.
        Parameters
        ------------
        ctx: commands.Context
            The context used for command invocation.
        error: commands.CommandError
            The Exception raised.
        """
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound, )
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        if isinstance(error, commands.DisabledCommand):
            await ctx.send(f'{ctx.command} has been disabled.')

        elif isinstance(error, commands.MissingRequiredArgument):
            log.warning("Missing Required Argument - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            params = ' '.join([x for x in ctx.command.clean_params])
            await ctx.send(embed = gen_embed(title = "Invalid parameter(s) entered", content = f"Parameter order: {params}\n\nDetailed parameter usage can be found by typing {ctx.prefix}help {ctx.command.name}```"))

        elif isinstance(error, commands.BadArgument):
            log.warning("Bad Argument - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit = 0)
            await ctx.send(embed = gen_embed(title = "Invalid type of parameter entered", content = "Are you sure you entered the right parameter?"))

        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file = sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file = sys.stderr)

def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))