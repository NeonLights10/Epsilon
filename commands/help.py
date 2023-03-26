import discord

from discord.ext import commands
from discord.commands.options import Option
from discord.ext import bridge

from __main__ import db, log


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

    @discord.slash_command(name='help',
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
                if cog_commands and x not in ['Dev']:
                    commands = []
                    for y in cog_commands:
                        if isinstance(y, discord.commands.SlashCommandGroup):
                            for sc in y.subcommands:
                                if isinstance(sc, discord.commands.SlashCommandGroup):
                                    for ssc in sc.subcommands:
                                        # log.info(f'sub-sub-command /{ssc.parent} {ssc.name} | {type(ssc)}')
                                        if not isinstance(y, bridge.BridgeSlashCommand):
                                            commands.append(f"/{sc.parent} {sc.name} {ssc.name}")
                                    continue
                                # log.info(f'sub-command /{sc.parent} {sc.name} | {type(sc)}')
                                if not isinstance(y, bridge.BridgeSlashCommand):
                                    commands.append(f"/{sc.parent} {sc.name}")
                            continue
                        # log.info(f'{y.name} | {type(y)}')
                        server_prefix = (await db.servers.find_one({"server_id": ctx.interaction.guild.id}))[
                                            'prefix'] or "%"
                        if isinstance(y, bridge.BridgeExtCommand):
                            commands.append(f"{server_prefix}{y.name} **|** /{y.name}")
                        elif isinstance(y, discord.ext.commands.Command):
                            if y.name == 'room':
                                commands.append(f"{server_prefix}{y.name} **|** /{y.name}")
                            else:
                                commands.append(f"{server_prefix}{y.name}")
                        elif isinstance(y, discord.commands.UserCommand):
                            commands.append(f"{y.name}")
                        elif not isinstance(y, bridge.BridgeSlashCommand):
                            if y.name != 'room':
                                commands.append(f"/{y.name}")
                    commands = ('\n'.join(map(str, sorted(commands))))
                    help_message.add_field(name=x, value=commands, inline=True)
            try:
                if ctx.prefix:
                    await ctx.respond(embed=help_message)
            except AttributeError:
                await ctx.respond(embed=help_message, ephemeral=True)
        else:
            command = command.lower()
            found = False
            shelp = None
            help_detail_message = None

            for x in self.bot.cogs:
                cog_commands = (self.bot.get_cog(x)).get_commands()
                for y in cog_commands:
                    if not isinstance(y, discord.ApplicationCommand):
                        if command == y.name or command in y.aliases and y.name != 'old':
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
                        # log.info(f'{y.name} | {type(y)}')
                        if isinstance(y, discord.commands.SlashCommandGroup):
                            if command == y.name:
                                help_detail_message = discord.Embed(title=y.name.capitalize(),
                                                                    description=f'{y.description}',
                                                                    color=discord.Color.blue())
                                for sc in y.subcommands:
                                    name = sc.name
                                    if isinstance(sc, discord.commands.SlashCommandGroup):
                                        for ssc in sc.subcommands:
                                            value = f'{sc.description}\n> **Options**:\n'
                                            options = ""
                                            if ssc.options:
                                                for option in ssc.options:
                                                    if not option.name == 'optional':
                                                        options = options + f"> {option.name}: {option.description}\n"
                                                    else:
                                                        continue
                                            else:
                                                options = "No options available."
                                            value += options
                                            help_detail_message.add_field(name=f"{sc.name} {ssc.name}".capitalize(),
                                                                          value=value,
                                                                          inline=False)
                                    else:
                                        value = f'{sc.description}\n> **Options**:\n'
                                        options = ""
                                        if sc.options:
                                            for option in sc.options:
                                                if not option.name == 'optional':
                                                    options = options + f"> {option.name}: {option.description}\n"
                                                else:
                                                    continue
                                        else:
                                            options = "No options available."
                                        value += options
                                        help_detail_message.add_field(name=f"{name.capitalize()}",
                                                                      value=value,
                                                                      inline=False)
                                found = True

                        elif command == y.name:
                            help_detail_message = discord.Embed(title=y.name.capitalize(), color=discord.Color.blue())
                            help_detail_message.add_field(name='Description',
                                                          value=y.description or "No description provided",
                                                          inline=False)

                            if isinstance(y, discord.SlashCommand):
                                options = ""
                                if y.options:
                                    for option in y.options:
                                        if not option.name == 'optional':
                                            options = options + f"{option.name}: {option.description}\n"
                                        else:
                                            continue
                                else:
                                    options = "No options available."
                                help_detail_message.add_field(name='Options', value=options,
                                                              inline=False)
                            found = True
            if not found:
                """Reminds you if that cog doesn't exist."""
                help_message = discord.Embed(title=f'No command with name {command} found', color=discord.Color.red())
                help_message.set_thumbnail(url=bot_icon_url)
                try:
                    if ctx.prefix:
                        await ctx.respond(embed=help_message)
                except AttributeError:
                    await ctx.respond(embed=help_message, ephemeral=True)
            else:
                help_detail_message.set_thumbnail(url=bot_icon_url)
                try:
                    if ctx.prefix:
                        await ctx.respond(embed=help_detail_message)
                except AttributeError:
                    await ctx.respond(embed=help_detail_message, ephemeral=True)
                if shelp:
                    shelp.set_thumbnail(url=bot_icon_url)
                    try:
                        if ctx.prefix:
                            await ctx.respond(embed=shelp)
                    except AttributeError:
                        await ctx.respond(embed=shelp, ephemeral=True)


def setup(bot):
    bot.add_cog(Help(bot))
