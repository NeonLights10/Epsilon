from bson import ObjectId

import discord
from discord.ext import commands
from discord.commands import Option
from discord.commands.permissions import default_permissions
from discord.ui import InputText

import validators

from formatting.embed import gen_embed
from __main__ import log, db
from commands.errorhandler import CheckOwner

EMBED_MAX_LENGTH = 4000


class Custom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.views = {}

    def cog_unload(self):
        pass

    @staticmethod
    def is_owner():
        async def predicate(ctx) -> bool:
            if isinstance(ctx, discord.ApplicationContext):
                if ctx.interaction.user.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()
            else:
                if ctx.author.id == 133048058756726784:
                    return True
                else:
                    raise CheckOwner()

        return commands.check(predicate)

    @discord.slash_command(name='customcommands',
                           description='Create and manage custom commands')
    @default_permissions(manage_messages=True)
    async def custom_commands(self,
                              ctx: discord.ApplicationContext):
        class Confirm(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.value = None

            # When the confirm button is pressed, set the inner value to `True` and
            # stop the View from listening to more input.
            # We also send the user an ephemeral message that we're confirming their choice.
            @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
            async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                # await interaction.response.send_message("Confirming", ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = True
                self.stop()

            # This one is similar to the confirmation button except sets the inner value to `False`
            @discord.ui.button(label="No", style=discord.ButtonStyle.red)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                log.info('Workflow cancelled')
                await interaction.response.send_message("Operation cancelled.", ephemeral=True, delete_after=0.1)
                for item in self.children:
                    item.disabled = True
                self.value = False
                self.stop()

        class CommandSelect(discord.ui.Select):
            def __init__(self, command_options, og_embed, all_commands):
                super().__init__(custom_id='command_select',
                                 placeholder="Select your commands here!",
                                 min_values=1,
                                 max_values=1,
                                 options=command_options,
                                 row=0)
                self.embed = og_embed
                self.all_commands = all_commands
                # populate select list with all available commands

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()
                name = self.values[0]
                for entry in self.all_commands:
                    if name == entry['name']:
                        message = entry['message']
                        image = entry['image']
                self.embed.fields[0].name = name
                if len(message) < 1024:
                    self.embed.fields[0].value = message
                else:
                    self.embed.fields[0].value = 'Command message is too long to display. Edit command to see content.'
                self.embed.set_image(url=image)
                edit_button = self.view.get_item('edit_command')
                edit_button.disabled = False
                remove_button = self.view.get_item('remove_command')
                remove_button.disabled = False
                await interaction.message.edit(embed=self.embed,
                                               view=self.view)

        class CustomCommandModal(discord.ui.Modal):
            def __init__(self, max_length, selected_command=None):
                super().__init__(title='Custom Command Message')
                self.name = None
                self.message = None
                self.image = None
                if selected_command:
                    self.name = selected_command['name']
                    self.message = selected_command['message']
                    self.image = selected_command['image']
                    self.add_item(
                        InputText(
                            label='Custom Command Name',
                            value=self.name,
                            style=discord.InputTextStyle.short,
                            max_length=64))
                    self.add_item(
                        InputText(
                            label='Custom Command Message',
                            value=self.message,
                            style=discord.InputTextStyle.long,
                            max_length=max_length))
                    self.add_item(
                        InputText(
                            label='Custom Command Image',
                            value=self.image,
                            style=discord.InputTextStyle.short,
                            required=False))
                else:
                    self.add_item(
                        InputText(
                            label='Custom Command Name',
                            placeholder='Enter the custom command name here.',
                            style=discord.InputTextStyle.short,
                            max_length=64))
                    self.add_item(
                        InputText(
                            label='Custom Command Message',
                            placeholder='Enter your custom command message here.',
                            style=discord.InputTextStyle.long,
                            max_length=max_length))
                    self.add_item(
                        InputText(
                            label='Custom Command Image',
                            placeholder='Enter the URL for the image here.',
                            style=discord.InputTextStyle.short,
                            required=False))

            async def callback(self, interaction: discord.Interaction):
                confirm_view = Confirm()
                int_embed = gen_embed(
                    title='Does the command message look correct?',
                    content=self.children[1].value)

                if self.children[2].value:
                    if not validators.url(self.children[2].value):
                        await interaction.response.send_message(embed=gen_embed(
                            title='Error',
                            content='Image URL is invalid. Please try again.'
                        ), ephemeral=True)
                        self.stop()
                        return
                    int_embed.set_image(url=self.children[2].value)

                await interaction.response.send_message(embed=int_embed, view=confirm_view)
                await confirm_view.wait()
                if confirm_view.value:
                    self.name = self.children[0].value
                    self.message = self.children[1].value
                    if self.children[2].value:
                        self.image = self.children[2].value
                    og_msg = await interaction.original_response()
                    await og_msg.delete()
                    self.stop()
                else:
                    og_msg = await interaction.original_response()
                    await og_msg.delete()
                    self.stop()

        # this view is the landing page for the custom_command command - from here display a list of available commands,
        # and give a select list to view them in more detail. once a command is selected, provide a button to edit and a button to delete.
        # a button to add a command is always present, and will launch the modal.
        # once modal is submitted, confirm message, write to DB, and then update the select list and change "page".
        class CustomCommandMenu(discord.ui.View):
            def __init__(self, context, start_embed, bot, defaults):
                super().__init__()
                self.context = context
                self.selectmenu = None
                self.embed = start_embed
                self.bot = bot
                self.all_commands = defaults

                options = []
                for entry in self.all_commands:
                    options.append(discord.SelectOption(label=entry['name'],
                                                        value=entry['name']))
                if len(options) > 0:
                    self.add_item(CommandSelect(options, self.embed, self.all_commands))

            async def interaction_check(self,
                                        interaction: discord.Interaction) -> bool:
                return interaction.user == self.context.interaction.user

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                await interaction.message.edit(view=view)
                self.stop()

            async def check_count(self,
                                  interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                if len(self.all_commands) < 25:
                    add_button = view.get_item('add_command')
                    add_button.disabled = False
                else:
                    add_button = view.get_item('add_command')
                    add_button.disabled = True

            @discord.ui.button(label='Save & Exit',
                               style=discord.ButtonStyle.green,
                               row=1)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                # no need to update database here because they are atomic - just close out
                await self.end_interaction(interaction)

            @discord.ui.button(label='Add Command',
                               custom_id='add_command',
                               style=discord.ButtonStyle.primary,
                               row=1)
            async def open_modal(self, button: discord.ui.Button, interaction: discord.Interaction):
                modal = CustomCommandModal(EMBED_MAX_LENGTH)
                await interaction.response.send_modal(modal)
                await modal.wait()

                if modal.name is None:
                    log.info("View timed out")
                    await interaction.followup.send(embed=gen_embed(
                        title='Custom Command',
                        content=f'Creating a new custom command has been cancelled.'),
                        ephemeral=True)
                elif modal.name:
                    db_command = await db.custom_commands.find_one({"server_id": ctx.interaction.guild_id,
                                                                    "name": modal.name.lower()})
                    if not db_command:
                        await interaction.followup.send(embed=gen_embed(
                            title='Custom command',
                            content='Custom command created!'),
                            ephemeral=True,
                            delete_after=5.0)
                        _id = ObjectId()
                        post = {
                            '_id': _id,
                            'server_id': ctx.interaction.guild_id,
                            'name': modal.name.lower(),
                            'message': modal.message,
                            'image': modal.image
                        }
                        await db.custom_commands.insert_one(post)
                        self.all_commands.append({'name': modal.name.lower(),
                                                  'message': modal.message,
                                                  'image': modal.image})
                        embd_text = ""
                        for cmd in self.all_commands:
                            embd_text += cmd['name'] + '\n'
                        self.embed.fields[0].name = 'Current Available Commands'
                        self.embed.fields[0].value = embd_text

                        r_item = self.get_item('command_select')
                        if r_item:
                            self.remove_item(r_item)
                        options = []
                        for entry in self.all_commands:
                            options.append(discord.SelectOption(label=entry['name'],
                                                                value=entry['name']))
                        self.selectmenu = CommandSelect(options, self.embed, self.all_commands)
                        self.add_item(self.selectmenu)
                        edit_button = main_menu_view.get_item('edit_command')
                        edit_button.disabled = True
                        remove_button = main_menu_view.get_item('remove_command')
                        remove_button.disabled = True
                        await interaction.message.edit(embed=self.embed,
                                                       view=self)
                    else:
                        await interaction.followup.send(embed=gen_embed(
                            title='Custom command',
                            content='Custom command already exists!'),
                            ephemeral=True,
                            delete_after=5.0)
                await self.check_count(interaction)

            @discord.ui.button(label='Edit Command',
                               custom_id='edit_command',
                               style=discord.ButtonStyle.secondary,
                               row=1)
            async def edit_command(self, button: discord.ui.Button, interaction: discord.Interaction):
                n = self.embed.fields[0].name
                for entry in self.all_commands:
                    if n == entry['name']:
                        m = entry['message']
                        i = entry['image']
                command_to_edit = {'name': n,
                                   'message': m,
                                   'image': i}
                old_command_name = self.embed.fields[0].name
                modal = CustomCommandModal(EMBED_MAX_LENGTH, command_to_edit)
                await interaction.response.send_modal(modal)
                await modal.wait()

                if modal.name is None:
                    log.info("View timed out")
                    await interaction.followup.send(embed=gen_embed(
                        title='Custom Command',
                        content=f'Editing the custom command {old_command_name} has been cancelled.'),
                        ephemeral=True,
                        delete_after=5.0)
                elif modal.name:
                    await interaction.followup.send(embed=gen_embed(
                        title='Custom command',
                        content=f'Custom command {modal.name} edited!'),
                        ephemeral=True,
                        delete_after=5.0)
                    await db.custom_commands.update_one({"server_id": 432379300684103699,
                                                         "name": old_command_name},
                                                        {"$set": {'name': modal.name.lower(),
                                                                  'message': modal.message,
                                                                  'image': modal.image}},
                                                        upsert=True)
                    self.embed.fields[0].name = modal.name.lower()
                    self.embed.fields[0].value = modal.message
                    self.embed.set_image(url=modal.image)
                    already_exists = False
                    for i in range(len(self.all_commands)):
                        if self.all_commands[i]['name'] == modal.name.lower():
                            self.all_commands[i]['message'] = modal.message
                            self.all_commands[i]['image'] = modal.image
                            already_exists = True
                            break
                    if not already_exists:
                        for i in range(len(self.all_commands)):
                            if self.all_commands[i]['name'] == old_command_name:
                                del self.all_commands[i]
                                break
                        self.all_commands.append({'name': modal.name.lower(),
                                                  'message': modal.message,
                                                  'image': modal.image})
                    await interaction.message.edit(embed=self.embed,
                                                   view=self)
                await self.check_count(interaction)

            @discord.ui.button(label='Remove Command',
                               custom_id='remove_command',
                               style=discord.ButtonStyle.danger,
                               row=1)
            async def remove_command(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                db_command = await db.custom_commands.delete_one({"server_id": ctx.interaction.guild_id,
                                                                  "name": self.embed.fields[0].name})
                deleted_name = self.embed.fields[0].name
                for i in range(len(self.all_commands)):
                    if self.all_commands[i]['name'] == self.embed.fields[0].name:
                        del self.all_commands[i]
                        break

                r_item = self.get_item('command_select')
                self.remove_item(r_item)
                options = []
                new_command_list = []
                for entry in self.all_commands:
                    options.append(discord.SelectOption(label=entry['name'],
                                                        value=entry['name']))
                    new_command_list.append({'name': entry['name'],
                                             'message': entry['message'],
                                             'image': entry['image']})
                self.selectmenu = CommandSelect(options, self.embed, self.all_commands)
                if len(self.all_commands) > 1:
                    self.add_item(self.selectmenu)

                new_field_text = 'No configured commands'
                if new_command_list:
                    new_field_text = ""
                    for new_command in new_command_list:
                        new_field_text += new_command['name'] + '\n'
                self.embed.fields[0].name = 'Current Available Commands'
                self.embed.fields[0].value = new_field_text
                if len(self.all_commands) < 1:
                    edit_button = main_menu_view.get_item('edit_command')
                    edit_button.disabled = True
                    remove_button = main_menu_view.get_item('remove_command')
                    remove_button.disabled = True
                await interaction.message.edit(embed=self.embed,
                                               view=self)
                await self.check_count(interaction)
                await interaction.followup.send(embed=gen_embed(
                    title='Custom Command',
                    content=f'Command {deleted_name} has been deleted.'),
                    ephemeral=True,
                    delete_after=10.0)

        await ctx.interaction.response.defer()
        db_commands = db.custom_commands.find({"server_id": ctx.interaction.guild_id})
        command_list = []
        async for document in db_commands:
            command_list.append({'name': document['name'],
                                 'message': document['message'],
                                 'image': document['image']})

        embed = gen_embed(name='Custom Commands',
                          content='You can configure custom commands for this server using the select dropdown below.')

        embed_text = 'No configured commands'
        if command_list:
            embed_text = ""
            for command in command_list:
                embed_text += command['name'] + '\n'

        embed.add_field(name='Current Available Commands',
                        value=embed_text,
                        inline=False)
        main_menu_view = CustomCommandMenu(ctx, embed, self.bot, command_list)
        if len(command_list) > 24:
            a_button = main_menu_view.get_item('add_command')
            a_button.disabled = True
        e_button = main_menu_view.get_item('edit_command')
        e_button.disabled = True
        r_button = main_menu_view.get_item('remove_command')
        r_button.disabled = True
        sent_menu_message = await ctx.interaction.followup.send(embed=embed,
                                                                view=main_menu_view,
                                                                ephemeral=True)

        timeout = await main_menu_view.wait()
        if timeout:
            for item in main_menu_view.children:
                item.disabled = True
            await sent_menu_message.edit(embed=embed,
                                         view=main_menu_view)

    async def custom_command_autocomplete(self,
                                          ctx: discord.ApplicationContext):
        command_list = []
        db_commands = db.custom_commands.find({"server_id": ctx.interaction.guild_id})
        async for document in db_commands:
            command_list.append(document['name'])
        return [command for command in command_list if command.startswith(ctx.value.lower())]

    @discord.slash_command(name='custom',
                           description='Send a custom command for this server.')
    @default_permissions(manage_messages=True)
    async def send_custom_command(self,
                                  ctx: discord.ApplicationContext,
                                  command: Option(str, 'Name of command',
                                                  autocomplete=custom_command_autocomplete)):
        await ctx.interaction.response.defer(ephemeral=False)
        command = command.lower()
        db_command = await db.custom_commands.find_one({"server_id": ctx.interaction.guild_id,
                                                        "name": command})
        if db_command:
            embed = gen_embed(title=db_command['name'],
                              content=db_command['message'])
            embed.set_image(url=db_command['image'])
            await ctx.interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await ctx.interaction.followup.send(embed=gen_embed(title='Custom Commands',
                                                                content='This command is not a valid custom command!'),
                                                ephemeral=True)


def setup(bot):
    bot.add_cog(Custom(bot))
