from discord.ext import commands
import discord

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(pass_context=True)
    @commands.has_permissions(embed_links=True)
    async def help(self,ctx,*commands):
        #try:
            bot_icon_url = f"{self.bot.user.avatar_url.BASE}{self.bot.user.avatar_url._url}"
            if not commands:
                help=discord.Embed(title='Available Commands',color=discord.Color.blue(),description='Run this command again followed by a command or list of commands to receive further help (e.g. `%help cutoff`)\n\nNeed help with anything? Feel free to shoot me a DM (Neon#5555 or @neon10lights on twitter).\nTo request data deletion, please fill out the this form: https://forms.gle/4LYZvADpoe12R6BZ8')
                help.set_thumbnail(url=bot_icon_url)
                help.set_footer(text = 'Fueee~')
                for x in self.bot.cogs:
                    cog_commands = (self.bot.get_cog(x)).get_commands()
                    if cog_commands and x not in ['Help','Admin']:
                        commands = []
                        for y in cog_commands:
                            if y.hidden == False:
                                commands.append(y.name)
                        commands = ('\n'.join(map(str, sorted(commands))))
                        help.add_field(name=x,value=commands,inline=True)
                await ctx.send(embed=help)
            else:
                for command in commands:
                    found = False
                    shelp = None
                    for x in self.bot.cogs:
                        cog_commands = (self.bot.get_cog(x)).get_commands()
                        for y in cog_commands:
                            if command == y.name or command in y.aliases:
                                if y.aliases:
                                    help=discord.Embed(title=f"{y.name.capitalize()} ({(', '.join(map(str, sorted(y.aliases))))})",color=discord.Color.blue())
                                else:
                                    help=discord.Embed(title=y.name.capitalize(),color=discord.Color.blue())
                                for c in self.bot.get_cog(y.cog_name).get_commands():
                                    if command == c.name or command in c.aliases:
                                        help.add_field(name='Description',value=c.description, inline=False)
                                        help.add_field(name='Inputs',value=f"{ctx.prefix}{c.name} {c.signature}", inline=False)
                                        if c.help:
                                            help.add_field(name='Examples / Further Help',value=c.help, inline=False)
                                if isinstance(y, discord.ext.commands.Group):
                                    shelp=discord.Embed(title="Subcommands",color=discord.Color.blue())
                                    for sc in y.walk_commands():
                                        if sc.parents[0] == y:
                                            value = f'{sc.description}\nInputs: {ctx.prefix}{y.name} {sc.name} {sc.signature}'
                                            if sc.help:
                                                value = value + f'\nExamples / Further Help: ' + sc.help
                                            if sc.aliases:
                                                shelp.add_field(name=f"{sc.name.capitalize()} ({(', '.join(map(str, sorted(sc.aliases))))})",
                                                                value=value, inline=False)
                                            else:
                                                shelp.add_field(name=f"{sc.name.capitalize()}",
                                                                value=value, inline=False)
                                found = True
                    if not found:
                        """Reminds you if that cog doesn't exist."""
                        help = discord.Embed(title=f'No command with name {command} found',color=discord.Color.red())
                        help.set_thumbnail(url=bot_icon_url)
                    else:
                        help.set_thumbnail(url=bot_icon_url)
                        await ctx.send(embed=help)
                        if shelp:
                            shelp.set_thumbnail(url=bot_icon_url)
                            await ctx.send(embed=shelp)
        #except Exception as e:
            #await ctx.send(str(e))
            
            
def setup(bot):
    bot.add_cog(Help(bot))