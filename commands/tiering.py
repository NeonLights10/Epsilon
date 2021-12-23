import asyncio
import discord
import re
import validators

from discord.ext import commands
from discord.commands import user_command
from formatting.embed import gen_embed
from typing import Union, Optional
from formatting.embed import embed_splitter
from __main__ import log, db

class RoomPositionMenu(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=900)
        self.value = None
        self.user = user

    async def interaction_check(self, interaction):
        if interaction.user != self.user:
            return False
        return True

    @discord.ui.button(emoji='1️⃣', style=discord.ButtonStyle.secondary)
    async def one(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = 0
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(emoji='2️⃣', style=discord.ButtonStyle.secondary)
    async def two(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = 1
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(emoji='3️⃣', style=discord.ButtonStyle.secondary)
    async def three(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = 2
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(emoji='4️⃣', style=discord.ButtonStyle.secondary)
    async def four(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = 3
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(emoji='5️⃣', style=discord.ButtonStyle.secondary)
    async def five(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = 4
        for item in self.children:
            item.disabled = True
        self.stop()

class ManageMenu(discord.ui.View):
    def __init__(self, user, leader, members):
        super().__init__(timeout=900)
        self.value = None
        self.user = user
        self.leader = leader
        self.members = members

    async def interaction_check(self, interaction):
        if interaction.user != self.user:
            return False
        return True

    @discord.ui.button(label='Kick User', style=discord.ButtonStyle.secondary)
    async def kickuser(self, button: discord.ui.Button, interaction: discord.Interaction):
        roompos_view = RoomPositionMenu(user = self.user)
        roompos_view.children[0].disabled = True
        for x in range(0,5):
            if x > len(self.members):
                roompos_view.children[x].disabled = True
        await interaction.response.send_message(content='Which user do you want to kick?', view=roompos_view,
                                                ephemeral=True)
        await roompos_view.wait()
        await interaction.edit_original_message(content=f'You selected position {roompos_view.value+1}', view=None)
        del self.members[roompos_view.value]
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label='Add/Change User', style=discord.ButtonStyle.secondary)
    async def changeuser(self, button: discord.ui.Button, interaction: discord.Interaction):
        # do stuff
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label='Transfer Ownership', style=discord.ButtonStyle.primary)
    async def transferowner(self, button: discord.ui.Button, interaction: discord.Interaction):
        roompos_view = RoomPositionMenu(user=interaction.user)
        roompos_view.children[0].disabled = True
        for x in range(0,5):
            if x > len(self.members):
                roompos_view.children[x].disabled = True
        await interaction.response.send_message(content='Please transfer ownership to another user.', view=roompos_view,
                                                ephemeral=True)
        await roompos_view.wait()
        await interaction.edit_original_message(content=f'You selected position {roompos_view.value+1}', view=None)
        self.leader = self.members[roompos_view.value]
        self.members[0], self.members[roompos_view.value] = self.members[roompos_view.value], self.members[0]
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label='Sync Room', style=discord.ButtonStyle.green)
    async def syncroom(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        self.stop()

class RoomMenu(discord.ui.View):
    def __init__(self, ctx, roomnum):
        super().__init__(timeout=None)
        self.context = ctx
        self.leader = ctx.author
        self.members = []
        self.members.append(self.leader)
        self.room = roomnum
        self.queue = []

    @discord.ui.button(emoji='📥', row = 0, style=discord.ButtonStyle.secondary, custom_id="persistent_view:joinroom")
    async def joinroom(self, button: discord.ui.Button, interaction: discord.Interaction):
        log.info(f'{interaction.user.name} triggered the joinroom button')
        debug_output = "["
        #for member in self.members:
        #    debug_output = debug_output + f'{member.name}, '
        #log.info(debug_output)
        if interaction.user in self.members:
            raise RuntimeError('User is already in room')
        if len(self.members) >= 5:
            raise RuntimeError('Room is full')
        self.members.append(interaction.user)
        embed = gen_embed(title=f'Room Code: {self.room}')
        embed_msg = ""
        for x in range(1,6):
            if x <= len(self.members) != 5:
                embed_msg = embed_msg + f"P{x} - {self.members[x-1].name}#{self.members[x-1].discriminator} | "
            elif x == len(self.members) and len(self.members) == 5:
                embed_msg = embed_msg + f"P{x} - {self.members[x-1].name}#{self.members[x-1].discriminator}"
            else:
                if x == 5:
                    embed_msg = embed_msg + f"P{x} - Empty"
                else:
                    embed_msg = embed_msg + f"P{x} - Empty | "
        embed.add_field(name='Currently Playing',
                        value=embed_msg,
                        inline=False)
        embed_value = ""
        if self.queue:
            for member in self.queue:
                embed_value = embed_value + f'{member.name}#{member.discriminator} '
        else:
            embed_value = "Empty"
        embed.add_field(name='Standby Queue',
                        value=f'{embed_value}',
                        inline=False)
        debug_output = "["
        #for member in self.members:
        #    debug_output = debug_output + f'{member.name}, '
        #log.info(debug_output)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji='📤', row = 0, style=discord.ButtonStyle.secondary, custom_id="persistent_view:leaveroom")
    async def leaveroom(self, button: discord.ui.Button, interaction: discord.Interaction):
        log.info(f'{interaction.user.name} triggered the leaveroom button')
        debug_output = "["
        #for member in self.members:
        #    debug_output = debug_output + f'{member.name}, '
        #log.info(debug_output)
        if interaction.user not in self.members:
            raise RuntimeError('User is not in the room')
        if interaction.user == self.leader:
            if len(self.members) == 1:
                for item in self.children:
                    item.disabled = True
                embed = gen_embed(title=f'Room Code: {self.room}',
                                  content='Room Closed')
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
                return
            else:
                roompos_view = RoomPositionMenu(user=interaction.user)
                roompos_view.children[0].disabled = True
                await interaction.response.send_message(content='Please transfer ownership to another user.', view=roompos_view,
                                                        ephemeral=True)
                await roompos_view.wait()
                await interaction.edit_original_message(content=f'You selected position {roompos_view.value+1}', view=None)
                self.leader = self.members[roompos_view.value]
                self.members[0], self.members[roompos_view.value] = self.members[roompos_view.value], self.members[0]
        self.members.remove(interaction.user)
        embed = gen_embed(title=f'Room Code: {self.room}')
        embed_msg = ""
        for x in range(1, 6):
            if x <= len(self.members) != 5:
                embed_msg = embed_msg + f"P{x} - {self.members[x - 1].name}#{self.members[x - 1].discriminator} | "
            elif x == len(self.members) and len(self.members) == 5:
                embed_msg = embed_msg + f"P{x} - {self.members[x - 1].name}#{self.members[x - 1].discriminator}"
            else:
                if x == 5:
                    embed_msg = embed_msg + f"P{x} - Empty"
                else:
                    embed_msg = embed_msg + f"P{x} - Empty | "
        embed.add_field(name='Currently Playing',
                        value=embed_msg,
                        inline=False)
        embed_value = ""
        if self.queue:
            for member in self.queue:
                embed_value = embed_value + f'{member.name}#{member.discriminator} '
        else:
            embed_value = "Empty"
        embed.add_field(name='Standby Queue',
                        value=f'{embed_value}',
                        inline=False)
        debug_output = "["
        #for member in self.members:
        #    debug_output = debug_output + f'{member.name}, '
        #log.info(debug_output)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Join/Leave Queue', row = 0, style=discord.ButtonStyle.secondary, custom_id="persistent_view:roomqueue")
    async def roomqueue(self, button: discord.ui.Button, interaction: discord.Interaction):
        pass

    @discord.ui.button(label='Manage Room', row = 1, style=discord.ButtonStyle.secondary, custom_id="persistent_view:manageroom")
    async def manageroom(self, button:discord.ui.Button, interaction: discord.Interaction):
        log.info(f'{interaction.user.name} triggered the manageroom button')
        debug_output = "["
        for member in self.members:
            debug_output = debug_output + f'{member.name}, '
        log.info(debug_output)
        if interaction.user != self.leader:
            #ALLOW MODS TO CLOSE ROOMS
            await interaction.response.send_message(content='You do not have permission to manage this room.', ephemeral=True)
            raise RuntimeError('Non-authorized user attempted to manage room')
        else:
            await interaction.response.defer()
            manageroom_view = ManageMenu(user = self.leader, leader = self.leader, members = self.members)
            original_message = await interaction.original_message()
            sent_message = await interaction.followup.send(content='Manage Room', view=manageroom_view, ephemeral=True)
            await manageroom_view.wait()
            self.members = manageroom_view.members
            self.leader = manageroom_view.leader
            await sent_message.edit(content='Operation Completed', view=manageroom_view)

            embed = gen_embed(title=f'Room Code: {self.room}')
            embed_msg = ""
            for x in range(1, 6):
                if x <= len(self.members) != 5:
                    embed_msg = embed_msg + f"P{x} - {self.members[x - 1].name}#{self.members[x - 1].discriminator} | "
                elif x == len(self.members) and len(self.members) == 5:
                    embed_msg = embed_msg + f"P{x} - {self.members[x - 1].name}#{self.members[x - 1].discriminator}"
                else:
                    if x == 5:
                        embed_msg = embed_msg + f"P{x} - Empty"
                    else:
                        embed_msg = embed_msg + f"P{x} - Empty | "
            embed.add_field(name='Currently Playing',
                            value=embed_msg,
                            inline=False)
            embed_value=""
            if self.queue:
                for member in self.queue:
                    embed_value = embed_value + f'{member.name}#{member.discriminator} '
            else:
                embed_value = "Empty"
            embed.add_field(name='Standby Queue',
                            value=f'{embed_value}',
                            inline=False)
            debug_output = "["
            for member in self.members:
                debug_output = debug_output + f'{member.name}, '
            log.info(debug_output)
            await interaction.followup.edit_message(original_message.id, embed=embed, view=self)

    @discord.ui.button(label='Close Room', row = 1, style=discord.ButtonStyle.danger, custom_id="persistent_view:closeroom")
    async def closeroom(self, button:discord.ui.Button, interaction: discord.Interaction):
        if interaction.user != self.leader:
            await interaction.response.send_message(content='You do not have permission to manage this room.', ephemeral=True)
            raise RuntimeError('Non-authorized user attempted to close room')

        embed = gen_embed(title=f'Room Code: {self.room}',
                          content='Room Closed')
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class GiftboxMenu(discord.ui.View):
    def __init__(self, ctx, boxnum):
        super().__init__(timeout=900.0)
        self.context = ctx
        self.boxnum = boxnum
        self.value = None
        self.boxsize = 0
        self.cansize = 0
        self.can_remaining = 0
        self.remaining = 0
        self.base_probabilities = [.1, .1, .1429, .0833, .0588, .0556]
        self.base_probability = 0
        self.probability = 0

        if self.boxnum == 1:
            self.remaining = 30
            self.can_remaining = 3
            self.boxsize = 30
            self.cansize = 3
            self.probability = self.base_probabilities[0]
            self.base_probability = self.base_probabilities[0]
        elif self.boxnum == 2:
            self.remaining = 50
            self.can_remaining = 5
            self.boxsize = 50
            self.cansize = 5
            self.probability = self.base_probabilities[1]
            self.base_probability = self.base_probabilities[1]
        elif self.boxnum == 3:
            self.remaining = 70
            self.can_remaining = 10
            self.boxsize = 70
            self.cansize = 10
            self.probability = self.base_probabilities[2]
            self.base_probability = self.base_probabilities[2]
        elif self.boxnum == 4:
            self.remaining = 120
            self.can_remaining = 10
            self.boxsize = 120
            self.cansize = 10
            self.probability = self.base_probabilities[3]
            self.base_probability = self.base_probabilities[3]
        elif self.boxnum == 5:
            self.remaining = 170
            self.can_remaining = 10
            self.boxsize = 170
            self.cansize = 10
            self.probability = self.base_probabilities[4]
            self.base_probability = self.base_probabilities[4]
        elif self.boxnum > 5:
            self.remaining = 180
            self.can_remaining = 10
            self.boxsize = 180
            self.cansize = 10
            self.probability = self.base_probabilities[5]
            self.base_probability = self.base_probabilities[5]

    async def interaction_check(self, interaction):
        if interaction.user != self.context.author:
            return False
        return True

    @discord.ui.button(label='-1 Can', style=discord.ButtonStyle.primary)
    async def minusonecan(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.can_remaining -= 1
        if self.can_remaining <= 0:
            self.children[0].disabled = True
        else:
            self.children[0].disabled = False
        self.value = 1
        self.probability = self.can_remaining / self.remaining
        if self.probability > self.base_probability:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **Yes** ({round(self.probability * 100, 2)}% probability)"))
        else:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **No** ({round(self.probability * 100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        await interaction.response.edit_message(embed=embed, view=self)


    @discord.ui.button(label='-1', style=discord.ButtonStyle.secondary)
    async def minusone(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.remaining -= 1
        if self.remaining <= 0:
            self.children[0].disabled = True
            self.children[1].disabled = True
            self.children[2].disabled = True
        else:
            self.children[1].disabled = False
        if self.remaining < 10:
            self.children[2].disabled = True
        self.value = 2
        if self.remaining != 0:
            self.probability = self.can_remaining / self.remaining
        else:
            self.probability = 0
        if self.probability > self.base_probability:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **Yes** ({round(self.probability * 100, 2)}% probability)"))
        else:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **No** ({round(self.probability * 100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='-10', style=discord.ButtonStyle.secondary)
    async def minusten(self, button: discord.ui.Button, interaction: discord.Interaction):
        if (self.remaining - 10) < 0:
            raise RuntimeError('Gift box - tried to subtract more items than are available')
        self.remaining -= 10
        if self.remaining < 10:
            self.children[2].disabled = True
        else:
            self.children[2].disabled = False
        self.value = 3
        if self.remaining != 0:
            self.probability = self.can_remaining / self.remaining
        else:
            self.probability= 0
            self.children[1].disabled = True
        if self.probability > self.base_probability:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **Yes** ({round(self.probability * 100, 2)}% probability)"))
        else:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **No** ({round(self.probability * 100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Next Box', style=discord.ButtonStyle.green)
    async def nextbox(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.boxnum += 1
        if self.boxnum == 1:
            self.remaining = 30
            self.can_remaining = 3
            self.boxsize = 30
            self.cansize = 3
            self.probability = self.base_probabilities[0]
            self.base_probability = self.base_probabilities[0]
        elif self.boxnum == 2:
            self.remaining = 50
            self.can_remaining = 5
            self.boxsize = 50
            self.cansize = 5
            self.probability = self.base_probabilities[1]
            self.base_probability = self.base_probabilities[1]
        elif self.boxnum == 3:
            self.remaining = 70
            self.can_remaining = 10
            self.boxsize = 70
            self.cansize = 10
            self.probability = self.base_probabilities[2]
            self.base_probability = self.base_probabilities[2]
        elif self.boxnum == 4:
            self.remaining = 120
            self.can_remaining = 10
            self.boxsize = 120
            self.cansize = 10
            self.probability = self.base_probabilities[3]
            self.base_probability = self.base_probabilities[3]
        elif self.boxnum == 5:
            self.remaining = 170
            self.can_remaining = 10
            self.boxsize = 170
            self.cansize = 10
            self.probability = self.base_probabilities[4]
            self.base_probability = self.base_probabilities[4]
        elif self.boxnum > 5:
            self.remaining = 180
            self.can_remaining = 10
            self.boxsize = 180
            self.cansize = 10
            self.probability = self.base_probabilities[5]
            self.base_probability = self.base_probabilities[5]
        self.value = 4
        for item in self.children:
            item.disabled = False
        embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                          content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                   f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                   f"Should I pull? **Yes** ({round(self.probability * 100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message('Closing gift box calculator.', ephemeral=True)
        for item in self.children:
            item.disabled = True
        self.value = False
        self.stop()

    @discord.ui.button(label='Manual Input', style=discord.ButtonStyle.secondary, row=1)
    async def manualinput(self, button: discord.ui.Button, interaction: discord.Interaction):
        async def remaining_prompt(attempts=1, sent_messages = []):
            def check(m):
                return m.author == self.context.author and m.channel == self.context.channel

            sent_message = await self.context.send(embed=gen_embed(title='Items remaining',
                                           content='How many items are remaining in the box?'))
            sent_messages.append(sent_message)
            try:
                mmsg = await self.context.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                await self.context.send(embed=gen_embed(title='Gift box Cancelled',
                                               content='Gift box calculator cancelled.'))
                return
            if re.match('^[0-9]+$', mmsg.clean_content):
                if validators.between(int(mmsg.clean_content), min=0, max=self.boxsize):
                    for message in sent_messages:
                        await message.delete()
                    return int(mmsg.clean_content)
                elif attempts > 3:
                    raise discord.ext.commands.BadArgument()
                else:
                    sent_message = await self.context.send(embed=gen_embed(title='Items remaining',
                                                                           content=f"Sorry, I didn't catch that or it was an invalid format.\nPlease enter a number from 1-{self.boxsize}."))
                    sent_messages.append(sent_message)
                    attempts += 1
                    return await remaining_prompt(attempts, sent_messages)
            elif attempts > 3:
                raise discord.ext.commands.BadArgument()
            else:
                sent_message = await self.context.send(embed=gen_embed(title='Items remaining',
                                               content=f"Sorry, I didn't catch that or it was an invalid format.\nPlease enter a number from 1-{self.boxsize}."))
                sent_messages.append(sent_message)
                attempts += 1
                return await remaining_prompt(attempts, sent_messages)

        await interaction.response.defer()
        self.remaining = await remaining_prompt()
        if self.remaining != 0:
            self.probability = self.can_remaining / self.remaining
            self.probability = round(self.probability * 100, 2)
        else:
            self.probability = 0
            self.children[1].disabled = True
            self.children[2].disabled = True
        if self.probability > self.base_probability:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **Yes** ({self.probability}% probability)"))
        else:
            embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                              content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                       f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                       f"Should I pull? **No** ({self.probability}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        await interaction.edit_original_message(embed=embed, view=self)

class Tiering(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_timers = []

    def convert_room(argument):
        if re.search('^\d{5}$', argument):
            return argument
        elif re.search('^\w+',argument):
            log.warning('Room Code not found, skipping')
            raise discord.ext.commands.BadArgument(message="This is not a valid room code.")
        else:
            raise discord.ext.commands.BadArgument(message="This is not a valid room code.")

    def convert_spot(argument):
        if re.search('^\d{5}$', argument):
            log.warning('Bad Argument - Spots Open')
            raise discord.ext.commands.BadArgument(message="This is not a valid option. Open spots must be a single digit number.")
        elif re.search('^\d{1}$', argument):
            return argument
        elif re.search('^[Ff]$', argument):
            return "0"
        else:
            log.warning('Bad Argument - Spots Open')
            raise discord.ext.commands.BadArgument(message="This is not a valid option. Open spots must be a single digit number.")

    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                return role in ctx.author.roles
            else:
                return False
        return commands.check(predicate)

    def can_trackfillers():
        async def predicate(ctx):
            document = await db.fillers.find_one({"server_id": ctx.guild.id})
            roles = []
            for role in ctx.author.roles:
                roles.append(role.id)
            return any(roleid in document['roles'] for roleid in roles)
        return commands.check(predicate)

    @user_command(name = 'Add user to filler list')
    async def addfiller(self, ctx, member: discord.Member):
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        log.info('found document')
        if document:
            fillers = document['fillers']
            enabled = document['enabled']
        else:
            fillers = []
            enabled = False
        if enabled:
            if document['roles']:
                roles = []
                for role in ctx.author.roles:
                    roles.append(role.id)
                if any(roleid in document['roles'] for roleid in roles):
                    if member.id in fillers:
                        await ctx.respond(content = 'User is already in the list of fillers.', ephemeral=True)
                    else:
                        fillers.append(member.id)
                        log.info('appended')
                        await db.fillers.update_one({'server_id': ctx.guild.id}, {"$set": {"fillers": fillers, "roles": []}}, upsert=True)
                        log.info('updated one')
                        await ctx.respond(content = f"Added {member.name} to the list of fillers.", ephemeral=True)
                        return
                else:
                    await ctx.respond(content = 'You do not have access to this feature.', ephemeral=True)
            else:
                if member.id in fillers:
                    await ctx.respond(content='User is already in the list of fillers.', ephemeral=True)
                else:
                    fillers.append(member.id)
                    log.info('appended')
                    await db.fillers.update_one({'server_id': ctx.guild.id},
                                                {"$set": {"fillers": fillers, "roles": []}}, upsert=True)
                    log.info('updated one')
                    await ctx.respond(content=f"Added {member.name} to the list of fillers.", ephemeral=True)
        else:
            await ctx.respond(content='This is not enabled for this server.', ephemeral=True)

    @commands.group(name='trackfiller',
                    description='Filler tracking feature for the server.')
    async def trackfiller(self, ctx):
        await ctx.send(embed = gen_embed(title='Before you use Kanon to track fillers', content= 'You or the server moderators will need to reauthorize Kanon to use application commands. You can do so by visiting the following link:\nhttps://s-neon.xyz/kanon\n\nThis feature is not complete, but permissions are configured now. Below is an example of how to activate filler tracking for your server:\n`%trackfiller settings enable`\n`%trackfiller rolepermission "t10" 012345678999999999`\n(This activates the feature for the roles t10 and the roleid listed after. You can use either format, or even mention the role.)'))
        pass

    @trackfiller.command(name='help',
                         description='Tutorial for adding a filler to the list.')
    async def trackfillerhelp(self, ctx):
        await ctx.send(content='How do I add a filler?')
        await ctx.send(content='https://files.s-neon.xyz/share/DiscordPTB_QkOPfrdP4L.png')

    @trackfiller.command(name='list',
                         aliases=['get'],
                         description='Show the list of all the fillers.')
    async def list(self, ctx):
        fillers = []
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        for memberid in document['fillers']:
            member = await self.bot.fetch_user(memberid)
            fillers.append(member.name)
        fillers_str = ", ".join(fillers)
        embed = gen_embed(title='List of Fillers',
                          content=f'{fillers_str}')
        await embed_splitter(embed = embed, destination = ctx.channel)

    @trackfiller.command(name='settings',
                         description='Configure settings for trackfiller.',
                         help='\nUsage:\n\n%trackfiller settings [option]\n\nAvailable settings: enable, disable')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def settings(self, ctx, option: str):
        valid_options = {'enable', 'disable'}
        option = option.lower()
        if option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return
        if option == 'enable':
            document = await db.fillers.find_one({'server_id': ctx.guild.id})
            if document:
                await db.fillers.update_one({'server_id': ctx.guild.id},
                                            {"$set": {"enabled": True}})
            else:
                post = {'server_id': id,
                        'fillers': [],
                        'roles': [],
                        'enabled': True
                        }
                await db.fillers.insert_one(post)
            await ctx.send(embed=gen_embed(title='trackfiller',
                                     content=f'Enabled trackfiller for {ctx.guild.name}.'))
            await ctx.send(content='How do I add a filler?')
            await ctx.send(content='https://files.s-neon.xyz/share/DiscordPTB_QkOPfrdP4L.png')
        elif option == 'disable':
            document = await db.fillers.find_one({'server_id': ctx.guild.id})
            if document:
                await db.fillers.update_one({'server_id': ctx.guild.id},
                                            {"$set": {"enabled": False}})
            else:
                post = {'server_id': id,
                        'fillers': [],
                        'roles': [],
                        'enabled': False
                        }
                await db.fillers.insert_one(post)
            await ctx.send(embed=gen_embed(title='trackfiller',
                                     content=f'Disabled trackfiller for {ctx.guild.name}.'))

    @trackfiller.command(name='rolepermission',
                         description='Configure which roles have access to trackfiller.',
                         help = '\nUsage:\n\n%trackfiller rolepermission [enable/disable] [role mentions/role ids/role names in quotations]')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole())
    async def rolepermission(self, ctx, option: str, value: commands.Greedy[discord.Role]):
        valid_options = {'enable', 'disable'}
        option = option.lower()
        if option not in valid_options:
            params = ' '.join([x for x in valid_options])
            await ctx.send(embed=gen_embed(title='Input Error',
                                           content=f'That is not a valid option for this parameter. Valid options: <{params}>'))
            return

        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        if document:
            fillers = document['fillers']
            roles = document['roles']
        else:
            fillers = []
            roles = []

        for role in value:
            edited = []
            if option == 'enable':
                if role.id in roles:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This role has already been enabled.'))
                    continue
                else:
                    roles.append(role.id)
                    edited.append(role.name)
            elif option == 'disable':
                if role.id in roles:
                    roles.remove(role.id)
                    edited.append(role.name)
                else:
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'This role has already been disabled.'))
                    continue
        await db.fillers.update_one({'server_id': ctx.guild.id},
                                    {"$set": {"fillers": fillers, "roles": roles, "enabled": True}},
                                    upsert=True)

        formatted_str = ", ".join(edited)
        if option == 'enable':
            await ctx.send(embed=gen_embed(title='trackfiller',
                                           content=f'Enabled trackfiller for {formatted_str}.'))
        elif option == 'disable':
            await ctx.send(embed=gen_embed(title='trackfiller',
                                           content=f'Disabled trackfiller for {formatted_str}.'))

    @trackfiller.command(name='clear',
                         description='Clear the list of all names.')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole(), can_trackfillers())
    async def clear(self, ctx):
        await db.fillers.update_one({'server_id': ctx.guild.id}, {"$set": {"fillers": []}})
        await ctx.send(embed = gen_embed(title='trackfiller - clear', content = 'List of fillers has been cleared.'))

    @trackfiller.command(name='remove',
                         aliases=['delete'],
                         description='Remove one or more users from the list.',
                         help='\nUsage:\n\n%trackfiller remove [user mentions/user ids/user name + discriminator (ex: name#0000)]')
    @commands.check_any(commands.has_guild_permissions(manage_roles=True), has_modrole(), can_trackfillers())
    async def remove(self, ctx, members: commands.Greedy[discord.Member]):
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        fillers = document['fillers']
        for member in members:
            fillers.remove(member.id)
        await db.fillers.update_one({'server_id': ctx.guild.id}, {"$set": {"fillers": fillers}})
        await ctx.send(embed=gen_embed(title='trackfiller - remove', content='Fillers removed.'))

    @commands.command(name = 'efficiencyguide',
                      description = 'Generates an efficiency guide for tiering in the channel you specify.',
                      help = 'Example:\n\n%efficiencyguide #tiering-etiquette')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def efficiencyguide(self, ctx, channel: discord.TextChannel):
        embed = gen_embed(
                    name = f"{ctx.guild.name}",
                    icon_url = ctx.guild.icon.url,
                    title = 'Tiering Etiqeutte and Efficiency',
                    content = 'Efficiency guidelines taken from LH 2.0, originally made by Binh and edited by doom_chicken.'
                    )
        embed.set_image(url = 'https://files.s-neon.xyz/share/bandori-efficiency.png')
        await channel.send(embed=embed)
        embed = gen_embed(
                    title = 'Menuing',
                    content = 'Spam the bottom right of your screen in between songs. See video for an example:'
                    )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        await channel.send(content='https://twitter.com/Binh_gbp/status/1106789316607410176')
        embed = gen_embed(
                    title='Swaps',
                    content="Try to have someone ready to swap with you by the time you're done. Ping the appropriate roles (usually standby, or t100 or even t1000) and when you're planning to stop.  Say \"scores\" in your room's chat channel when you finish the song and \"open\" when you're out of the room.  Ideally whoever is swapping in should be spamming the room code to join as soon as they see \"scores.\" If possible, being in VC with the tierers can greatly smooth out this process."
                    )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
                    title='Pins/Frames/Titles',
                    content='Pins/Frames/Titles - Please remove any and all existing pins as well as setting the default frame; these will slow down the room greatly with additional loading times. I would also prefer if you went down to one title before you join any rooms, but no need to leave if forgotten.'
                )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
                    title='Flame Sync',
                    content='Flame syncing will now operate with the remake of the room every set of 90 🔥. If multiple sets are being done, a room maker should be designated. The flame check setting should now be turned OFF from now on.'
                )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
                    title='Skip Full Combo',
                    content="Break combo somewhere in the song, it'll skip the FC animation and save a few seconds."
                )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
                    title='Rooming Guidelines',
                    content="**Starting with 3-4 people** can potentially be better than dealing with the chance of bad pubs depending on the event.\n\nFor extremely competitive events, iOS and high end Android devices are given priority."
                )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        await ctx.send(embed=gen_embed(title='efficiencyguide', content=f'Tiering etiquette and efficiency guide posted in {channel.mention}'))

    @commands.command(name='vsliveguide',
                      description='Generates a versus live guide for tiering in the channel you specify. This includes gift box and lazy doormat info.',
                      help='Example:\n\n%vsliveguide #tiering-etiquette')
    @commands.check_any(commands.has_guild_permissions(manage_messages=True), has_modrole())
    async def vsliveguide(self, ctx, channel: discord.TextChannel):
        embed = gen_embed(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url,
            title='Versus Live Tiering Info',
            content='Graciously stolen from **Zia** & **Blur** and the **Play Act! Challenge*Audition** server, edited by **Neon**'
        )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
            title="Marina's Gift Box Can Efficiency",
            content="""This chart helps you get the most boost cans as efficiently as possible.
            It lets you know whether you should keep opening gifts from a box or move on to the next box (if possible) based on the probability of pulling a boost can.
            \nTo use this chart, make sure turn on the settings called
            \n"Exchange All" & "Stop on Special Prize".
            \nOnce you have collected the special prize, you can look at this chart to determine if you should keep pulling or move to the next box."""
        )
        embed.set_image(url='https://files.s-neon.xyz/share/marina_box.png')
        embed.add_field(
            name='Green',
            value='Favourable probability - **continue opening**'

        )
        embed.add_field(
            name='Red',
            value='Unfavourable probability - **skip to next box**'

        )
        embed.add_field(
            name='White',
            value='Neutral probability - **keep opening OR skip to next box**'

        )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        embed = gen_embed(
            title="Lazy Doormat Strategy",
            content='Follow the chart below to obtain the best efficiency.'
        )
        embed.add_field(
            name='Songs',
            value="```\nUnite! From A to Z: 87 / 124 / 252 / 357/ 311 (SP)\nJumpin': 63 / 102 / 185 / 281\nKizuna Music: 78 / 127 / 207 / 265\nFuwa Fuwa Time: 52 / 98 / 192 / 272\nB.O.F - 54 / 88 / 207 / 306\nLegendary EN: 64 / 100 / 189 / 272\nHome Street: 65 / 111 / 193 / 269\nStraight Through Our Dreams!: 52 / 107 / 184 / 280\nInitial: 86 / 114 / 218 / 341\nKorekara: 59 / 104 / 170 / 296\nKyu~Mai * Flower: 73 / 108 / 226 / 351```"
        )
        embed.set_footer(text=discord.Embed.Empty)
        await channel.send(embed=embed)
        await ctx.send(embed=gen_embed(title='vsliveguide',
                                       content=f'Versus Live guide posted in {channel.mention}'))

    @commands.command(name='room',
                      aliases=['rm'],
                      description='Changes the room name without having to go through the menu. If no arguments are provided, the room will be changed to a dead room. Rooms must start with the standard tiering prefix, i.e. "g#-".\nBoth parameters are optional.',
                      help='Usage:\n\n%room <room number> <open spots>\n\nExample:\n\n`%room 12345 1`\nFor just changing room number - `%room 12345`\nFor just changing open spots - `%room 3`')
    @commands.cooldown(rate=2,per=600.00,type=commands.BucketType.channel)
    async def room(self, ctx, room_num: Optional[convert_room], open_spots: Optional[convert_spot]):
        currentname = ctx.channel.name
        namesuffix = ""
        if re.search('^[A-Za-z]\d-', currentname):
            nameprefix=re.match("^[A-Za-z]\d-", currentname).group(0)
        else:
            log.warning('Error: Invalid Channel')
            await ctx.send(embed=gen_embed(title='Invalid Channel',
                                           content=f'This is not a valid tiering channel. Please match the format g#-xxxxx to use this command.'))
            return
        if re.search('-[\df]$', currentname):
            namesuffix=re.search("-[\df]$", currentname).group(0)

        if room_num:
            if open_spots:
                open_spots = int(open_spots)
                if 0 < open_spots <= 4:
                    namesuffix=f'-{open_spots}'
                elif open_spots == 0:
                    namesuffix='-f'
                else:
                    log.warning('Error: Invalid Input')
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'That is not a valid option for this parameter. Open spots must be a value from 0-4.'))
                    return

            await ctx.channel.edit(name=f'{nameprefix}{room_num}{namesuffix}')
            await ctx.send(embed=gen_embed(title='room',
                                           content=f'Changed room code to {room_num}'))
        else:
            if open_spots:
                open_spots = int(open_spots)
                if 0 < open_spots <= 4:
                    namesuffix=f'-{open_spots}'
                    nameprefix=re.search("(^[A-Za-z]\d-.+)(?![^-])(?<!-[\df]$)",currentname).group(0)
                elif open_spots == 0:
                    namesuffix='-f'
                    nameprefix = re.search("(^[A-Za-z]\d-.+)(?![^-])(?<!-[\df]$)", currentname).group(0)
                else:
                    log.warning('Error: Invalid Input')
                    await ctx.send(embed=gen_embed(title='Input Error',
                                                   content=f'That is not a valid option for this parameter. Open spots must be a value from 0-4.'))
                    return
                await ctx.channel.edit(name=f'{nameprefix}{namesuffix}')
                await ctx.send(embed=gen_embed(title='room',
                                               content=f'Changed open spots to {open_spots}'))
            else:
                await ctx.channel.edit(name=f'{nameprefix}xxxxx')
                await ctx.send(embed=gen_embed(title='room',
                                               content=f'Closed room'))

    @commands.command(name='giftbox',
                      aliases=['gb', 'marinagiftbox', 'giftboxcalc'],
                      description='Helps you calculate the optimal pulls for getting small boost cans.',
                      help='Usage:\n\n%giftbox')
    async def giftbox(self, ctx):
        async def box_number_prompt(attempts = 1):
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            await ctx.send(embed=gen_embed(title='Gift Box #',
                                           content='What gift box number are you currently on?'))
            try:
                mmsg = await self.bot.wait_for('message', check=check, timeout=60.0)
            except asyncio.TimeoutError:
                await ctx.send(embed=gen_embed(title='Gift box cancelled',
                                               content='Gift box calculator cancelled.'))
                return
            if re.match('^[0-9]+$', mmsg.clean_content):
                if validators.between(int(mmsg.clean_content), min=1, max=99999):
                    return int(mmsg.clean_content)
            elif attempts > 3:
                raise discord.ext.commands.BadArgument()
            else:
                await ctx.send(embed=gen_embed(title='Gift Box #',
                                               content="Sorry, I didn't catch that or it was an invalid format.\nPlease enter a number from 1-99999."))
                attempts += 1
                return await box_number_prompt(attempts)
        boxnum = await box_number_prompt()
        giftbox_view = GiftboxMenu(ctx, boxnum)
        current_probability = giftbox_view.can_remaining / giftbox_view.remaining
        embed = gen_embed(title=f'Gift Box #{boxnum}',
                          content=(f"**{giftbox_view.remaining}/{giftbox_view.boxsize} remaining**\n"
                                   f"{giftbox_view.can_remaining}/{giftbox_view.cansize} cans remaining\n\n"
                                   f"Should I pull? **Yes** ({round(current_probability*100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        sent_message = await ctx.send(embed=embed, view=giftbox_view)
        await giftbox_view.wait()
        await sent_message.edit(view=giftbox_view)

    @commands.command(name='refilltimer',
                      aliases=['refill'],
                      description='Starts a timer that will remind you to refill when you have 1-3 games left. Based on average of 2 minutes per game.',
                      help='Usage:\n\n%refilltimer\nTo stop the time: %refilltimer cancel')
    async def refilltimer(self, ctx, option: Optional[str]):
        count = 0
        if option:
            if option == 'cancel' and ctx.channel.id in self.active_timers:
                self.active_timers.remove(ctx.channel.id)
            else:
                ctx.send(embed=gen_embed(title='Refill Timer', content='Timer is not running in this channel!'))
                return
        else:
            if ctx.channel.id in self.active_timers:
                ctx.send(embed=gen_embed(title='Refill Timer', content='Timer is already running in this channel!'))
                return
            else:
                self.active_timers.append(ctx.channel.id)
                while count < 30 and ctx.channel.id in self.active_timers:
                    if self.current_loop == 27:
                        ctx.send(embed=gen_embed(title='Refill Timer', content='Estimated 3 games left! Prepare to refill.'))
                    if self.current_loop == 28:
                        ctx.send(embed=gen_embed(title='Refill Timer', content='Estimated 2 games left! Prepare to refill.'))
                    if self.current_loop == 29:
                        ctx.send(embed=gen_embed(title='Refill Timer', content='Refill after this game!'))
                    count += 1
                    await asyncio.sleep(120)

    @commands.command(name='roomview',
                      aliases=['rmv', 'rv'],
                      description='CONCEPT TESTING ONLY DO NOT USE',
                      help='DO NOT USE')
    async def roomview(self, ctx, room_num: convert_room):
        room_view = RoomMenu(ctx, room_num)
        embed = gen_embed(title=f'Room Code: {room_num}')
        embed.add_field(name='Currently Playing',
                        value=f"P1 - {ctx.author.name}#{ctx.author.discriminator} | P2 - Empty | P3 - Empty | P4 - Empty | P5 - Empty",
                        inline=False)
        embed.add_field(name='Standby Queue',
                        value=f'Empty',
                        inline=False)
        sent_message = await ctx.send(embed=embed, view=room_view)
        await room_view.wait()
        await sent_message.edit(view=room_view)
    #async def connect(self, ctx, label, dest_server):

def setup(bot):
    bot.add_cog(Tiering(bot))