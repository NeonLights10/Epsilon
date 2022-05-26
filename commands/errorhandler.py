import discord
import traceback
import sys

from humanfriendly import format_timespan
from discord.ext import commands
from formatting.embed import gen_embed
from __main__ import log


class CheckOwner(commands.CheckFailure):
    def __init__(self):
        super().__init__('This command can only be used by the owner.')


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_application_command_error(self,
                                           ctx: discord.ApplicationContext,
                                           error):
        """Handles errors for all application commands."""

        # Unpack the error first
        if isinstance(error, discord.ApplicationCommandInvokeError):
            error = error.original

        if hasattr(ctx.command, 'on_error'):
            return

        elif isinstance(error, CheckOwner):
            await ctx.respond(f'{ctx.command.qualified_name} can only be used by the owner of this bot.')
            return

        elif isinstance(error, commands.ChannelNotReadable):
            await ctx.respond(f"I cannot access messages in {error.argument.mention}. "
                              "Please check your server's permission settings and try again!", ephemeral=True)
            return

        elif isinstance(error, commands.BotMissingPermissions):
            message = f"I don't have the following permissions to run this command: \n"
            for permission in error.missing_permissions:
                message += f"{permission}\n"
            message += "Please check your server's permission settings and try again!"
            await ctx.respond(message, ephemeral=True)
            return

        elif isinstance(error, commands.MessageNotFound):
            await ctx.respond('Message not found. Check the ID or URL of the message.', ephemeral=True)
            return

        elif isinstance(error, commands.BadArgument):
            log.warning("Bad Argument - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__)
            if hasattr(error, 'message'):
                await ctx.respond(embed=gen_embed(title="Invalid parameter entered",
                                                  content=f"Error: {error.message} \nAre you sure you entered the right"
                                                          f" parameter?"),
                                  ephemeral=True)
            else:
                await ctx.respond(embed=gen_embed(title="Invalid parameter entered",
                                                  content=f"Are you sure you entered the right parameter?"),
                                  ephemeral=True)
            return

        elif isinstance(error, commands.UserInputError):
            await ctx.respond(error, ephemeral=True)
            return

        elif isinstance(error, discord.ExtensionNotFound):
            await ctx.respond(f'Extension {ctx.selected_options[0]["value"]} is not a valid option!')
            return

        elif isinstance(error, discord.ExtensionNotLoaded):
            if ctx.command.name == 'reload':
                await ctx.interaction.followup.send('There was an error loading the cog. '
                                                    'Rolling back to previous state.')
            else:
                await ctx.interaction.followup.send('There was an error loading the cog.')
            return

        elif isinstance(error, discord.Forbidden):
            await ctx.respond(('It seems I do not have the server permissions to post in the target channel.'
                               '\nPlease check the permissions and try again.'))
            return

        elif isinstance(error, discord.HTTPException):
            log.error(f"Error: {error.status} | {error.text}")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.respond(embed=gen_embed(title=f'{error.status}', content=f'{error.text}'))
            return

        else:
            log.error(f"Ignoring unhandled exception in application command {ctx.command.name!r}")
            traceback.print_exception(type(error), error, error.__traceback__)
            exception = '\n'.join(traceback.format_exception(type(error), error, error.__traceback__))
            await ctx.respond(
                "An error occured during command execution. Please send the following info to Neon#5555 immediately."
                f"```py\n{exception}```"
                "Please try again later...", ephemeral=True)

        return

    @commands.Cog.listener()
    async def on_command_error(self,
                               ctx: discord.ext.commands.Context,
                               error):
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

        if isinstance(error, commands.DisabledCommand):
            await ctx.send(f'{ctx.command.name} has been disabled.')
            return

        if isinstance(error, CheckOwner):
            await ctx.send(f'{ctx.command.name} can only be used by the owner of this bot.')
            return

        elif isinstance(error, commands.GuildNotFound):
            log.warning("Guild Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"Guild {str(error.argument)} not found",
                                content="Doublecheck the spelling or id of this guild!"))
            return

        elif isinstance(error, commands.RoleNotFound):
            log.warning("Role Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"Role {str(error.argument)} not found",
                                content="Doublecheck the spelling or id of this role!"))
            return

        elif isinstance(error, commands.MessageNotFound):
            log.warning("Message Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"Message {str(error.argument)} not found",
                                content="Doublecheck the id of this message!"))
            return

        elif isinstance(error, commands.UserNotFound):
            log.warning("User Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"User {str(error.argument)} not found",
                                content="Doublecheck the spelling or id of this user!"))
            return

        elif isinstance(error, commands.MemberNotFound):
            log.warning("Member Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"Member {str(error.argument)} not found",
                                content="Doublecheck the spelling or id of this member!"))
            return

        elif isinstance(error, discord.ExtensionNotFound):
            log.warning("Cog Not Found - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title=f"Cog {error.name} not found", content="Doublecheck the spelling of this cog!"))
            return

        elif isinstance(error, discord.ExtensionAlreadyLoaded):
            await ctx.send(
                embed=gen_embed(title=f"Cog {error.name} already loaded!",
                                content="Cannot load a cog that is already loaded."))
            return

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=gen_embed(title=f"{ctx.command.name}", content="You do not have permission to run this command."))
            return

        # catchall for any BadArgument errors that are not listed above
        elif isinstance(error, commands.BadArgument):
            log.warning("Bad Argument - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            if hasattr(error, 'message'):
                await ctx.send(embed=gen_embed(title="Invalid parameter entered",
                                               content=f"Error: {error.message} \nAre you sure you entered the right "
                                                       f"parameter?"))
            else:
                await ctx.send(embed=gen_embed(title="Invalid parameter entered",
                                               content=f"Are you sure you entered the right parameter?"))
            return

        elif isinstance(error, commands.CommandOnCooldown):
            log.warning("Command on Cooldown - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title="Command on Cooldown",
                                content=f"You are trying to change the name too many times. Discord's global rate "
                                        f"limit per channel is twice per 10 minutes.\nPlease try again in "
                                        f"{format_timespan(ctx.command.get_cooldown_retry_after(ctx))}."))
            return

        elif isinstance(error, discord.Forbidden):
            log.error("Permission Error: Bot does not have sufficient permissions. - Traceback below:")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title='Bot Permission Error',
                                content="It seems like I don't have the permissions to do that. Check your server "
                                        "settings."))
            return

        elif isinstance(error, commands.CheckAnyFailure):
            log.warning("Permission Error: Insufficient Permissions")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(
                embed=gen_embed(title='Permissions Error',
                                content='You must have server permissions or moderator role to run this command.'))
            return

        elif isinstance(error, discord.HTTPException):
            log.error(f"Error: {error.status} | {error.text}")
            traceback.print_exception(type(error), error, error.__traceback__, limit=0)
            await ctx.send(embed=gen_embed(title=f'{error.status}', content=f'{error.text}'))
            return

        else:
            log.critical(f'Ignoring exception in command {ctx.command}:')
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            # await ctx.respond(embed=gen_embed(title='Error', content=f'{traceback.format_exc(error)}'))
            return


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))
