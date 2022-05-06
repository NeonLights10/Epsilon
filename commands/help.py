import discord

from discord.ext import commands
from discord.commands.options import Option
from discord.ext import bridge

from __main__ import log, db


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def help_autocomplete(self,
                                ctx):
        command_list = []
        for x in self.bot.cogs:
            cog_commands = (self.bot.get_cog(x)).get_commands()
            for c in cog_commands:
                if not isinstance(c, bridge.BridgeExtCommand):
                    command_list.append(c.name)
        return [command for command in command_list if command.startswith(ctx.value.lower())]

    @bridge.bridge_command(name='help',
                           description='Shows all available commands and help context.')
    async def help(self,
                   ctx,
                   command: Option(str, "Enter a command for more details on usage",
                                   default="",
                                   required=False,
                                   autocomplete=help_autocomplete)):
        bot_icon_url = self.bot.user.display_avatar.url
        if not command:
            help_message = discord.Embed(title='Available Commands',
                                         color=discord.Color.blue(),
                                         description=('Prefixed commands will appear with the prefix '
                                                      'in the list below. Send this command with the '
                                                      'optional value to get detailed help with those '
                                                      'commands.\n\n'
                                                      'Need help with anything? Feel free to shoot me '
                                                      'a DM (Neon#5555 or @neon10lights on twitter) or '
                                                      'join the server at https://discord.gg/AYTFJY8VhF.\n\n'
                                                      'View our privacy policy: '
                                                      'https://s-neon.xyz/privacy-policy\n'
                                                      'To request data deletion: '
                                                      'https://forms.gle/4LYZvADpoe12R6BZ8'))
            help_message.set_thumbnail(url=bot_icon_url)
            help_message.set_footer(text='Fueee~')
            for x in self.bot.cogs:
                cog_commands = (self.bot.get_cog(x)).get_commands()
                if cog_commands and x not in ['Admin']:
                    commands = []
                    for y in cog_commands:
                        server_prefix = (await db.servers.find_one({"server_id": ctx.interaction.guild.id}))[
                                            'prefix'] or "%"
                        if isinstance(y, bridge.BridgeExtCommand):
                            commands.append(f"{server_prefix}{y.name} **|** /{y.name}")
                        elif isinstance(y, discord.ext.commands.Command):
                            commands.append(f"{server_prefix}{y.name}")
                        elif not isinstance(y, bridge.BridgeSlashCommand):
                            commands.append(f"/{y.name}")
                    commands = ('\n'.join(map(str, sorted(commands))))
                    help_message.add_field(name=x, value=commands, inline=True)
            await ctx.respond(embed=help_message)
        else:
            command = command.lower()
            found = False
            shelp = None
            help_detail_message = None

            for x in self.bot.cogs:
                cog_commands = (self.bot.get_cog(x)).get_commands()
                for y in cog_commands:
                    if not isinstance(y, discord.ApplicationCommand):
                        if command == y.name or command in y.aliases:
                            if y.aliases:
                                help_detail_message = discord.Embed(
                                    title=f"{y.name.capitalize()} ({(', '.join(map(str, sorted(y.aliases))))})",
                                    color=discord.Color.blue())
                            else:
                                help_detail_message = discord.Embed(title=y.name.capitalize(), color=discord.Color.blue())
                            help_detail_message.add_field(name='Description', value=y.description, inline=False)
                            help_detail_message.add_field(name='Inputs', value=f"%{y.name} {y.signature}",
                                                          inline=False)
                            if y.help:
                                help_detail_message.add_field(name='Examples / Further Help', value=y.help,
                                                              inline=False)

                            # TODO: walk through slash command groups

                            if isinstance(y, discord.ext.commands.Group):
                                shelp = discord.Embed(title="Subcommands", color=discord.Color.blue())
                                for sc in y.walk_commands():
                                    if sc.parents[0] == y:
                                        value = f'{sc.description}\nInputs: %{y.name} {sc.name} {sc.signature}'
                                        if sc.help:
                                            value = value + f'\nExamples / Further Help: ' + sc.help
                                        if sc.aliases:
                                            shelp.add_field(
                                                name=f"{sc.name.capitalize()} ({(', '.join(map(str, sorted(sc.aliases))))})",
                                                value=value, inline=False)
                                        else:
                                            shelp.add_field(name=f"{sc.name.capitalize()}",
                                                            value=value, inline=False)
                            found = True
                    else:
                        if command == y.name:
                            help_detail_message = discord.Embed(title=y.name.capitalize(), color=discord.Color.blue())
                            help_detail_message.add_field(name='Description', value=y.description or "No description provided", inline=False)

                            if isinstance(y, discord.SlashCommand):
                                options = ""
                                if y.options:
                                    for option in y.options:
                                        if not option.name == 'optional':
                                            options = options + f"{option.name}: {option.description}"
                                        else:
                                            options = options + f"(Optional) {option.name}: {option.description}"
                                else:
                                    options = "No options available."
                                help_detail_message.add_field(name='Options', value=options,
                                                              inline=False)
                            found = True
            if not found:
                """Reminds you if that cog doesn't exist."""
                help_message = discord.Embed(title=f'No command with name {command} found', color=discord.Color.red())
                help_message.set_thumbnail(url=bot_icon_url)
                await ctx.respond(embed=help_message)
            else:
                help_detail_message.set_thumbnail(url=bot_icon_url)
                await ctx.respond(embed=help_detail_message)
                if shelp:
                    shelp.set_thumbnail(url=bot_icon_url)
                    await ctx.respond(embed=shelp)


def setup(bot):
    bot.add_cog(Help(bot))
