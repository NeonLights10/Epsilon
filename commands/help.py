import discord

from discord import app_commands
from discord.ext import commands

from typing import List

from __main__ import log, db


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help',
                          description='Shows all available commands and help context.')
    @app_commands.describe(command='Enter a command for more details on usage')
    @app_commands.guilds(911509078038151168)
    async def help(self,
                   interaction: discord.Interaction,
                   command: str = None):
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
                                                      'https://s-neon.notion.site/Kanon-Bot-Public-Policy'
                                                      '-340f17f60bb44571a12f153805380783\n'
                                                      'To request data deletion, please fill out this form: '
                                                      'https://forms.gle/4LYZvADpoe12R6BZ8'))
            help_message.set_thumbnail(url=bot_icon_url)
            help_message.set_footer(text='Fueee~')
            for x in self.bot.cogs:
                cog_commands = (self.bot.get_cog(x)).get_commands()
                if cog_commands and x not in ['Admin']:
                    commands = []
                    for y in cog_commands:
                        if y.hidden == False:
                            commands.append(y.name)
                    commands = ('\n'.join(map(str, sorted(commands))))
                    help_message.add_field(name=x, value=commands, inline=True)
            await interaction.response.send_message(embed=help_message)
        else:
            for command in command:
                found = False
                shelp = None
                for x in self.bot.cogs:
                    cog_commands = (self.bot.get_cog(x)).get_commands()
                    for y in cog_commands:
                        if command == y.name or command in y.aliases:
                            if y.aliases:
                                help = discord.Embed(
                                    title=f"{y.name.capitalize()} ({(', '.join(map(str, sorted(y.aliases))))})",
                                    color=discord.Color.blue())
                            else:
                                help = discord.Embed(title=y.name.capitalize(), color=discord.Color.blue())
                            for c in self.bot.get_cog(y.cog_name).get_commands():
                                if command == c.name or command in c.aliases:
                                    help.add_field(name='Description', value=c.description, inline=False)
                                    help.add_field(name='Inputs', value=f"%{c.name} {c.signature}",
                                                   inline=False)
                                    if c.help:
                                        help.add_field(name='Examples / Further Help', value=c.help, inline=False)
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
                if not found:
                    """Reminds you if that cog doesn't exist."""
                    help = discord.Embed(title=f'No command with name {command} found', color=discord.Color.red())
                    help.set_thumbnail(url=bot_icon_url)
                    await interaction.response.send_message(embed=help)
                else:
                    help_message.set_thumbnail(url=bot_icon_url)
                    await interaction.response.send_message(embed=help_message)
                    if shelp:
                        shelp.set_thumbnail(url=bot_icon_url)
                        await interaction.response.send_message(embed=shelp)

    @help.autocomplete('command')
    async def help_autocomplete(self,
                                interaction: discord.Interaction,
                                current: str,
                                ) -> List[app_commands.Choice[str]]:
        command_list = ['help', 'help2', 'help3']
        return [
            app_commands.Choice(name=command, value=command)
            for command in command_list if current.lower() in command_list
        ]

    @commands.command(name='hello',
                      description='hello world',
                      help='hello world')
    async def hello(self, ctx, optional: str = None):
        if optional:
            raise TypeError
        else:
            await ctx.send('hello world')


async def setup(bot):
    await bot.add_cog(Help(bot))


async def teardown(bot):
    bot.tree.remove('help', guild=discord.Object(id=911509078038151168))
    await bot.tree.sync(guild=discord.Object(id=911509078038151168))
