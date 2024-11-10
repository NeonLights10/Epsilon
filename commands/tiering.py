import asyncio
import re
from typing import Optional

import validators

import discord
from discord.ext import commands
from discord.commands import Option, OptionChoice, SlashCommandGroup, user_command
from discord.commands.permissions import default_permissions

from formatting.embed import gen_embed, embed_splitter
from __main__ import log, db


class Tiering(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refill_running = {}

    @staticmethod
    def convert_room(argument):
        if re.search(r'^\d{5}$', argument):
            return argument
        elif re.search(r'^\w+', argument):
            log.warning('Room Code not found, skipping')
            raise discord.ext.commands.BadArgument(message="This is not a valid room code.")
        else:
            raise discord.ext.commands.BadArgument(message="This is not a valid room code.")

    @staticmethod
    def convert_spot(argument):
        if re.search(r'^\d{5}$', argument):
            log.warning('Number of players not found, skipping')
            raise discord.ext.commands.BadArgument(
                message="This is not a valid option. Open spots must be a single digit number.")
        elif re.search(r'^\d$', argument):
            return argument
        elif re.search('^[Ff]$', argument):
            return "0"
        else:
            log.warning('Number of players not found, skipping')
            raise discord.ext.commands.BadArgument(
                message="This is not a valid option. Open spots must be a single digit number.")

    @staticmethod
    def has_modrole():
        async def predicate(ctx):
            document = await db.servers.find_one({"server_id": ctx.guild.id})
            if document['modrole']:
                role = discord.utils.find(lambda r: r.id == document['modrole'], ctx.guild.roles)
                return role in ctx.author.roles
            else:
                return False

        return commands.check(predicate)

    guides = SlashCommandGroup('guide', 'Commands to post various tiering guides',
                               default_member_permissions=discord.Permissions(manage_messages=True))

    @guides.command(name='efficiency',
                    description='Generates an efficiency guide for tiering')
    @default_permissions(manage_messages=True)
    async def efficiencyguide(self,
                              ctx: discord.ApplicationContext,
                              channel: Option(discord.SlashCommandOptionType.channel,
                                              ('Channel to post guide in. If not specified, '
                                               'will post in current channel'),
                                              required=False)):
        await ctx.interaction.response.defer()
        if channel:
            dest_channel = channel
        else:
            dest_channel = ctx.interaction.channel
        embed = gen_embed(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url,
            title='Tiering Etiqeutte and Efficiency',
            content='Efficiency guidelines taken from LH 2.0, originally made by Binh and edited by doom_chicken.')
        embed.set_image(url='https://files.s-neon.xyz/share/bandori-efficiency.png')
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Menuing',
            content='Spam the bottom right of your screen in between songs. See video for an example:')
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await dest_channel.send(content='https://twitter.com/Binh_gbp/status/1106789316607410176')
        embed = gen_embed(
            title='Swaps',
            content=("Try to have someone ready to swap with you by the time you're done. Ping the appropriate roles"
                     " (usually standby, or t100 or even t1000) and when you're planning to stop.  Say \"scores\" in"
                     " your room's chat dest_channel when you finish the song and \"open\" when you're out of the room."
                     " Ideally whoever is swapping in should be spamming the room code to join as soon as they see"
                     " \"scores.\" If possible, being in VC with the tierers can greatly smooth out this process."))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Pins/Frames/Titles',
            content=('Pins/Frames/Titles - Please remove any and all existing pins as well as setting the default'
                     ' frame; these will slow down the room greatly with additional loading times. We would also prefer'
                     ' if you went down to one title before you join any rooms, but no need to leave if forgotten.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Flame Sync',
            content=('Flame syncing will operate with the remake of the room every set of 90 🔥. If multiple sets'
                     ' are being done, a room maker should be designated. The flame check setting should now be turned'
                     ' OFF from now on.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Skip Full Combo',
            content="Break combo somewhere in the song, it'll skip the FC animation and save a few seconds.")
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Rooming Guidelines',
            content=("**Starting with 3-4 people** can potentially be better than dealing with the chance of bad pubs"
                     " depending on the event.\n\nFor extremely competitive events, iOS and high end Android devices"
                     " are given priority."))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await ctx.interaction.followup.send(embed=gen_embed(
            title='Efficiency Guide',
            content=f'Tiering etiquette and efficiency guide posted in {dest_channel.mention}'),
            ephemeral=True)

    @guides.command(name='vslive',
                    description='Generates a guide for VS Live events')
    @default_permissions(manage_messages=True)
    async def vsliveguide(self,
                          ctx: discord.ApplicationContext,
                          channel: Option(discord.SlashCommandOptionType.channel,
                                          ('Channel to post guide in. If not specified, '
                                           'will post in current channel'),
                                          required=False)):
        await ctx.interaction.response.defer()
        if channel:
            dest_channel = channel
        else:
            dest_channel = ctx.interaction.channel
        embed = gen_embed(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url,
            title='Versus Live Tiering Info',
            content=('Graciously stolen from **Zia** & **Blur** and the **Play Act! Challenge*Audition** server,'
                     ' edited by **Neon**'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="Marina's Gift Box Can Efficiency",
            content=("**NEW**: You can now use the /giftbox command to have Kanon tell you when to move boxes!"
                     "This chart helps you get the most boost cans as efficiently as possible."
                     "It lets you know whether you should keep opening gifts from a box or move on to the next box"
                     " (if possible) based on the probability of pulling a boost can."
                     "\nTo use this chart, make sure turn on the settings called "
                     '\n"Exchange All" & "Stop on Special Prize".'
                     "\nOnce you have collected the special prize, you can look at this chart to determine if you"
                     " should keep pulling or move to the next box."))
        embed.set_image(url='https://files.s-neon.xyz/share/marina_box.png')
        embed.add_field(
            name='Green',
            value='Favourable probability - **continue opening**')
        embed.add_field(
            name='Red',
            value='Unfavourable probability - **skip to next box**')
        embed.add_field(
            name='White',
            value='Neutral probability - **keep opening OR skip to next box**')
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="Lazy Doormat Strategy",
            content='Follow the chart below to obtain the best efficiency. Generally playing past fever is safe.')
        embed.add_field(
            name='Songs',
            value=("```\nUnite! From A to Z: 87 / 124 / 252 / 357 / 311 (SP)"
                   "\nSavior of Song: 67 / 123 / 201 / 386"
                   "\nJumpin': 63 / 102 / 185 / 281"
                   "\nKizuna Music: 78 / 127 / 207 / 265"
                   "\nFuwa Fuwa Time: 52 / 98 / 192 / 272"
                   "\nB.O.F - 54 / 88 / 207 / 306"
                   "\nLegendary EN: 64 / 100 / 189 / 272"
                   "\nHome Street: 65 / 111 / 193 / 269"
                   "\nStraight Through Our Dreams!: 52 / 107 / 184 / 280"
                   "\nInitial: 86 / 114 / 218 / 341"
                   "\nKorekara: 59 / 104 / 170 / 296"
                   "\nKyu~Mai * Flower: 73 / 108 / 226 / 351```"))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await ctx.interaction.followup.send(embed=gen_embed(
            title='VS Live Guide',
            content=f'Versus Live guide posted in {dest_channel.mention}'),
            ephemeral=True)

    @guides.command(name='carpal-avoidance',
                    description='Generates a guide for avoiding Carpal Tunnel or RSI')
    @default_permissions(manage_messages=True)
    async def vsliveguide(self,
                          ctx: discord.ApplicationContext,
                          channel: Option(discord.SlashCommandOptionType.channel,
                                          ('Channel to post guide in. If not specified, '
                                           'will post in current channel'),
                                          required=False)):
        await ctx.interaction.response.defer()
        if channel:
            dest_channel = channel
        else:
            dest_channel = ctx.interaction.channel
        embed = gen_embed(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url,
            title='Carpal Tunnel & Tiering Wellness',
            content=('Graciously created by **Aris/Nio**, originally for PRSK, edited by **Neon**'
                     '\n***Disclaimer: This is not medical advice. This is for educational purposes only and is my'
                     " (aris') research and does not replace going to the doctor.***"))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="What is Carpal Tunnel Syndrome/RSI?",
            content=('**Carpal Tunnel Syndrome** is the irritation of the median nerve within the carpal tunnel at the'
                     ' base of your hand. When the nerve becomes irritated in this region due to pressure, inflammation'
                     ', and/or stretching (ie gaming), symptoms are likely to occur.\n\nRepetitive quick movements over'
                     ' long periods of time (ie, tiering) can damage the carpal tunnel nerve in your wrists. This may'
                     ' cause numbness and weakness in your hands over long periods of time, which can become'
                     ' permanent.\n\n**Repetitive Strain Injury (RSI)** is damage damage to your muscles, tendons or'
                     ' nerves caused by repetitive motions and constant use. Anyone can get a RSI.'))
        embed.set_footer(text=('https://esportshealthcare.com/carpal-tunnel-syndrome/\n'
                               'https://my.clevelandclinic.org/health/diseases/17424-repetitive-strain-injury'))
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="Symptoms of Carpal Tunnel Syndrome/RSI",
            content=('🔹 Feelings of pain or numbness in your fingers\n'
                     '🔹 Weakness when gripping objects with one or both hands\n'
                     '🔹 "Pins and needles" or swollen feeling in your fingers\n'
                     '🔹 Burning or tingling in the fingers, especially the thumb, index, and middle fingers\n'
                     '🔹 Pain or numbness that is worse at night\n\nIf you ever feel pain, **TAKE A BREAK!**'))
        embed.set_footer(text='https://www.hopkinsmedicine.org/health/conditions-and-diseases/carpal-tunnel-syndrome')
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="Before Playing",
            content=('Below is a helpful guide for warming up. Other guides for Gamer Stretches™ probably exist on the'
                     ' internet. If you have one you like, keep following it.\n\nTake off any wristwatches before'
                     ' playing - wearing them worsens carpal tunnel.\n\nGrab a jug of water or other drinks to keep'
                     ' hydration within arm’s reach.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await dest_channel.send(content='https://esportshealthcare.com/gamer-warm-up/')
        embed = gen_embed(
            title="While Playing",
            content=('**Try to keep good posture.**\nTyping ergonomics logic likely applies here.\n'
                     '🔹 Consider playing on index fingers; it’s easier on your wrists. Put your phone or tablet flat'
                     ' on the table, and tap on it as if it was a keyboard.\n'
                     '🔹 Position your wrist straight/aligned and neutral, as if you were playing piano.\n'
                     '🔹 Try to look down at your screen with your eyes instead of moving your head.'
                     ' You may need to perform neck stretches if your neck hurts.'))
        embed.set_image(url='https://files.s-neon.xyz/share/unknown.png')
        embed.add_field(name='Keep your hands warm',
                        value='Play in a warm environment - hand pain and stiffness is more likely in a cold one.',
                        inline=False)
        embed.add_field(name='Ideally, your screen should be at eye level',
                        value=('I think theoretically the best way to accomplish this is to cast your phone/tablet to'
                               'a monitor/TV and play while looking straight at the monitor you casted to instead of'
                               ' your device screen.'),
                        inline=False)
        embed.set_footer(text=('Exercises and tips in this section from:\n'
                               'https://youtu.be/EiRC80FJbHU\n'
                               'https://bit.ly/3lD5ot9\n'
                               'https://bit.ly/38IZeVI'))
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title="Routines",
            content=('**Every 20 minutes**, do the 20-20-20 rule: look at something 20 feet away, for about 20 seconds,'
                     ' to give your eyes a break. This is easily done while menuing in between songs.\n\n'
                     '**Every 60 minutes**, consider taking a 5 minute break to rest your hands.\n\n'
                     '**Every 2-3 hours**, shake out your hands and perform some hand/finger exercises. See below for'
                     ' an instructional video.\n\n'
                     '**1-2 times a day**, run your hands gently under warm water. Move your hands up and down under'
                     ' the water.\n\n'
                     '**If your hands hurt, take breaks more often.**'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await dest_channel.send(content='https://youtu.be/EiRC80FJbHU?t=85')
        embed = gen_embed(
            title="After Playing",
            content=('Below is a helpful guide for post-game stretches. Again, other guides for Gamer Stretches™'
                     ' probably exist on the internet. If you have one you like, keep following it.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await dest_channel.send(content='https://esportshealthcare.com/gamer-stretches/')
        await ctx.interaction.followup.send(embed=gen_embed(
            title='Carpal Avoidance Guide',
            content=f'Carpal Tunnel & RSI Avoidance guide posted in {dest_channel.mention}'),
            ephemeral=True)

    @guides.command(name='new-players',
                    description='Generates a guide for helping new players adjust to tiering')
    @default_permissions(manage_messages=True)
    async def vsliveguide(self,
                          ctx: discord.ApplicationContext,
                          channel: Option(discord.SlashCommandOptionType.channel,
                                          ('Channel to post guide in. If not specified, '
                                           'will post in current channel'),
                                          required=False)):
        await ctx.interaction.response.defer()
        if channel:
            dest_channel = channel
        else:
            dest_channel = ctx.interaction.channel
        embed = gen_embed(
            name=f"{ctx.guild.name}",
            icon_url=ctx.guild.icon.url,
            title='New Tiering Member Tips & Tricks',
            content=('Graciously created by **feathers**, edited by **Neon**'
                     '\n\nHi all, I’m here to make a special additional post regarding new players, rules, and tiering'
                     ' etiquette. The trend lately has been that brand new players tend to have difficulty knowing what'
                     ' questions they should be asking, and aren’t familiar with the intensity of tiering and the need'
                     ' to rely on fellow players to support each other properly for success. By **no means** should'
                     ' joining in be discouraged, but I wanted to take some time to emphasize the impact of being a'
                     ' good or bad helper. Many of you simply read a brief how-to or perhaps watched a video, but doing'
                     ' those things does not necessarily prepare you to be a good tierer or filler.\n\n'
                     'Some of these tidbits will repeat established rules, but I encourage you to think of this as'
                     ' reaffirming how important the rules truly are. The high tierers are spending a lot of time and'
                     ' money on these events, and we should always be considering that dedication when we come into a'
                     ' server to support or directly help the high tiering players. Every second will count from start'
                     ' to end. It is important to be confident and reliable in your ability to help everyone reach'
                     ' their goals, including those who are shooting for lower tiers. Being a good helper helps'
                     ' everyone, not just the high tierers.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Importance of Menus',
            content=('It may seem negligible in the end, but when it comes down to it, getting in those extra songs'
                     ' per hour thanks to fast menu tapping can make a substantial difference in placement if we come'
                     ' down to the wire.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Smooth Swapping',
            content=('The swapping of players in rooms can often lead to the biggest of time losses, so it is extremely'
                     ' important to judge correctly whether or not you should be joining Room 1 based on how much time'
                     ' you can spare. Players who have more time on their hands are generally more favorable in Room 1,'
                     ' where the podium players spend most of their time. The less swaps over time, the more efficient'
                     ' the room can be.\n\nIf you think you may have obligations (parents, meals, class, etc) that only'
                     ' allow you to play for short periods of time, try to actively seek out players who can be ready'
                     ' when you leave before you even join a room to play. I find that searching for replacements about'
                     ' **30 minutes before you need them** is the best way. If members of the server are present and'
                     ' unable to play, join the search to find a substitute! This is a team effort through and'
                     ' through.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Why Should I Remove Pins/Frames/Titles?',
            content=('The reason we remove these is to reduce loading times across devices, some of which struggle more'
                     ' than others. While it’s an easy mistake to make, do your best to prepare in advance. Go into'
                     ' your profile NOW, as you read this, and remove everything. If you accidentally join with them'
                     ' on, you can remove them the next time you fill your flames.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Flames, Rooms and Syncing',
            content=('As much as we like to plan this out and pray for full and smooth sets of 90 flames, falling out'
                     ' of sync is common and there is no reason to panic!\n\nIf you are helping in Room 1 or 2, where'
                     ' our top 10 and podium runners will be, you must prioritize the highest tiering player in the'
                     ' room. If T1 is on 30 flames and you, a filler or lower tierer, are on 20 flames, you will refill'
                     ' when the T1 is ready. It is important that we all reach our goals, but we must support our top'
                     ' players first and foremost, as is the purpose of servers like this one. T1, T2, and T3 ALWAYS'
                     ' have highest priority for entering rooms and deciding when flames will be re-synced.'
                     ' Please listen to them!'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Starting a Partially Filled Room',
            content=('If you happen to be hosting a room with players that are tiering high and need every second to'
                     ' count, don’t be afraid to start your room with three or four people if a swap goes wrong. Often'
                     ' the length of one song is enough to re-organize. Don’t wait, EP is EP! Just say you’re going'
                     ' again and let the players who are swapping in prepare. More songs per hour is always the correct'
                     ' choice!'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Being Asked to Play in a Different Room',
            content=('Please don’t be personally offended if you are asked to play in a different room. This could'
                     ' happen if your device loads slowly, if someone else is available to play longer than you, if'
                     ' someone happens to be able to menu faster than you at that current time, if the room needs'
                     ' higher band power teams for the extra boost, or even if someone has a better center than you.'
                     ' There are a lot of reasons a swap could be requested, and it is never personal. It **never**'
                     ' means that we hate you or are purposely ignoring your goals. Efficiency is key above all else,'
                     ' and we will try our best to make sure the other room is running smoothly as well!'
                     ' Don’t make trouble or argue, just do your best to swap out smoothly.'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        embed = gen_embed(
            title='Closing Words of Wisdom',
            content=('If you are new and not quite sure what you’re doing yet, it might be best not to help in G1'
                     ' right away. Hang out in other game rooms and watch others to learn how everything works before'
                     ' jumping into the main tiering room, just to help keep up efficiency where we need it most. If'
                     ' we need an emergency filler, you’ll know!\n\nUltimately tiering is a game of math and endurance,'
                     ' and being realistic and mathematical about it is very beneficial mentally and physically. The'
                     ' mental game is just as important as the endurance, so it is important to stay calm and reign in'
                     ' those nerves as a first time, or even repeat player. We don’t have to concern ourselves with'
                     ' what the competition is doing, or who they are, or what they’re up to. We only have to work'
                     ' together to get the highest numbers the most times per hour until the event is over.'
                     ' We want **EVERYONE** to achieve their goals, we just need to remember that podium and T10 will'
                     ' need extra support. Most of all, remember to have fun doing it!'))
        embed.remove_footer()
        await dest_channel.send(embed=embed)
        await ctx.interaction.followup.send(embed=gen_embed(
            title='New Tiering Members Guide',
            content=f'New Tiering Members Tips and Tricks guide posted in {dest_channel.mention}'),
            ephemeral=True)
        
    def verify_room(self, room):
        """Checks if room matches the format [name]-xxxxx

        Args:
            room (str): The room name to check

        Returns:
            bool: True if the room matches the format, False otherwise
        """
        if re.search(r'^.*-[0-9x]{5}.*', room):
            return True
        else:
            return False
        
    def split_room(self, room):
        """Splits room code by '-' and returns the index of the code and player count (if present)

        Args:
            room (str): The room name
        """
        room_split = room.split('-')
        
        codeMatch = re.compile(r'^[0-9x]{5}$')
        playerMatch = re.compile(r'^[0-4f]$')
        
        code_idx = None
        player_idx = None
        
        ## Always assume first is name
        for i in range(1, len(room_split)):
            if codeMatch.match(room_split[i]):
                code_idx = i
            if playerMatch.match(room_split[i]):
                player_idx = i
                
        return room_split, code_idx, player_idx

    @commands.command(name='room',
                      aliases=['rm'],
                      description=('Changes the room name without having to go through the menu. If no arguments are'
                                   ' provided, the room will be changed to a dead room. Rooms must start with the'
                                   ' standard tiering prefix, i.e. "g#-".\nBoth parameters are optional.'),
                      help=('Usage:\n\n%room <room number> <open spots>\n\nExample:\n\n`%room 12345 1`\nFor just'
                            ' changing room number - `%room 12345`\nFor just changing open spots - `%room 3`'))
    @commands.cooldown(rate=2, per=600.00, type=commands.BucketType.channel)
    async def room(self, ctx, room_num: Optional[convert_room], open_spots: Optional[convert_spot]):
        currentname = ctx.channel.name
        namesuffix = ""
        
        log.info(f'Running room in {ctx.guild.name}')
        if not self.verify_room(currentname):
            log.warning('Error: Invalid Channel')
            await ctx.send(embed=gen_embed(title='Invalid Channel',
                                           content=(f'This is not a valid tiering channel. Please match the format'
                                                    ' [name]-xxxxx to use this command.')))
            return
        
        room_split, code_idx, player_idx = self.split_room(currentname)
        
        if code_idx is None:
            log.warning('Error: Invalid Channel')
            await ctx.send(embed=gen_embed(title='Invalid Channel',
                                           content=(f'This is not a valid tiering channel. Please match the format'
                                                    ' [name]-xxxxx to use this command.')))
            
        if room_num:
            room_split[code_idx] = str(room_num)
            
        if open_spots:
            if open_spots in ['1', '2', '3', '4']:
                namesuffix = f'{open_spots}'
            elif open_spots in ['0', 'f', 'F']:
                namesuffix = 'f'
            else:
                log.warning('Error: Invalid Input')
                await ctx.send(embed=gen_embed(title='Input Error',
                                                content=(f'That is not a valid option for this parameter. Open spots'
                                                        " must be a value from 0-4 or 'f' (shorthand for full).")))
                return
            
            if player_idx is None and room_split[code_idx] != 'xxxxx':
                room_split.append(namesuffix)
                player_idx = len(room_split) - 1
            else:
                room_split[player_idx] = namesuffix

        if room_num is not None or open_spots is not None:
            newName = "-".join(room_split)
            if newName != currentname:
                await ctx.channel.edit(name=newName)
            roomTitle = f'{room_split[code_idx]}' + (f'-{room_split[player_idx]}' if player_idx else '')
            await ctx.send(embed=gen_embed(title='room',
                                            content=f'Changed room code to {roomTitle}'))
        else:
            room_split[code_idx] = 'xxxxx'
            if player_idx:
                room_split[player_idx] = ''
            room_split = [x for x in room_split if x]
            newName = "-".join(room_split)
            if newName != currentname:
                await ctx.channel.edit(name=newName)
            await ctx.send(embed=gen_embed(title='room', content=f'Closed room'))

    @discord.slash_command(name='room',
                           description=('Changes the room name. If no options are filled out, the room will close.'),
                           cooldown=discord.ext.commands.CooldownMapping.from_cooldown(2.0, 600.0, commands.BucketType.channel))
    async def sroom(self,
                    ctx: discord.ApplicationContext,
                    roomcode: Option(str, 'Room Code. Should be a 5 digit number from 00000-99999',
                                     required=False),
                    spots: Option(int, '# of spots open in room. Can be from 0-4.',
                                  min_value=0,
                                  max_value=4,
                                  required=False)):
        currentname = ctx.channel.name
        namesuffix = ""
        await ctx.interaction.response.defer()
        
        log.info(f'Running room in {ctx.guild.name}')
        if not self.verify_room(currentname):
            log.warning('Error: Invalid Channel')
            await ctx.reply(embed=gen_embed(title='Invalid Channel',
                                           content=(f'This is not a valid tiering channel. Please match the format'
                                                    ' [name]-xxxxx to use this command.')))
            return
        
        room_split, code_idx, player_idx = self.split_room(currentname)
        
        if code_idx is None:
            log.warning('Error: Invalid Channel')
            await ctx.respond(embed=gen_embed(title='Invalid Channel',
                                           content=(f'This is not a valid tiering channel. Please match the format'
                                                    ' [name]-xxxxx to use this command.')))
            
        if roomcode:
            room_split[code_idx] = str(roomcode)
            
        if spots is not None:
            spots = str(spots)
            if spots in ['1', '2', '3', '4']:
                namesuffix = f'{spots}'
            elif spots in ['0', 'f', 'F']:
                namesuffix = 'f'
            else:
                log.warning('Error: Invalid Input')
                await ctx.respond(embed=gen_embed(title='Input Error',
                                                content=(f'That is not a valid option for this parameter. Open spots'
                                                        " must be a value from 0-4 or 'f' (shorthand for full).")))
                return
            
            if player_idx is None and room_split[code_idx] != 'xxxxx':
                room_split.append(namesuffix)
                player_idx = len(room_split) - 1
            else:
                room_split[player_idx] = namesuffix

        if roomcode is not None or spots is not None:
            newName = "-".join(room_split)
            if newName != currentname:
                await ctx.channel.edit(name=newName)
            roomTitle = f'{room_split[code_idx]}' + (f'-{room_split[player_idx]}' if player_idx else '')
            await ctx.respond(embed=gen_embed(title='room',
                                            content=f'Changed room code to {roomTitle}'))
        else:
            room_split[code_idx] = 'xxxxx'
            if player_idx:
                room_split[player_idx] = ''
            room_split = [x for x in room_split if x]
            newName = "-".join(room_split)
            if newName != currentname:
                await ctx.channel.edit(name=newName)
            await ctx.respond(embed=gen_embed(title='room', content=f'Closed room'))

    @discord.slash_command(name='giftbox',
                           description='Helps you calculate the optimal pulls for getting small boost cans.')
    async def giftbox(self,
                      ctx: discord.ApplicationContext,
                      event: Option(str, 'The current event type',
                                    choices=[OptionChoice('VS Live', value='1'),
                                             OptionChoice('Team Live Festival', value='2')]),
                      giftbox: Option(int, 'The number of the giftbox you are currently on',
                                      min_value=1,
                                      max_value=99999,
                                      default=1,
                                      required=False)):
        class GiftboxMenu(discord.ui.View):
            def __init__(self, context, boxnum, event_type):
                super().__init__(timeout=900.0)
                self.context = context
                self.boxnum = boxnum
                self.event_type = int(event_type)
                self.value = None
                self.boxsize = 0
                self.cansize = 0
                self.can_remaining = 0
                self.remaining = 0
                self.vs_boxsizes = [30, 50, 70, 120, 170, 180]
                self.tl_boxsizes = [40, 65, 90, 160, 220, 230]
                self.vs_cansizes = [3, 5, 10, 10, 10, 10]
                self.tl_cansizes = [3, 5, 5, 5, 5, 10]
                self.vs_base_probabilities = [.1, .1, .1429, .0833, .0588, .0556]
                self.tl_base_probabilities = [.075, .0769, .0555, .03125, .0227, .0435]
                self.base_probability = 0
                self.probability = 0

                if self.boxnum == 1:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[0]
                        self.can_remaining = self.vs_cansizes[0]
                        self.boxsize = self.vs_boxsizes[0]
                        self.cansize = self.vs_cansizes[0]
                        self.probability = self.vs_base_probabilities[0]
                        self.base_probability = self.vs_base_probabilities[1]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[0]
                        self.can_remaining = self.tl_cansizes[0]
                        self.boxsize = self.tl_boxsizes[0]
                        self.cansize = self.tl_cansizes[0]
                        self.probability = self.tl_base_probabilities[0]
                        self.base_probability = self.tl_base_probabilities[1]
                elif self.boxnum == 2:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[1]
                        self.can_remaining = self.vs_cansizes[1]
                        self.boxsize = self.vs_boxsizes[1]
                        self.cansize = self.vs_cansizes[1]
                        self.probability = self.vs_base_probabilities[1]
                        self.base_probability = self.vs_base_probabilities[2]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[1]
                        self.can_remaining = self.tl_cansizes[1]
                        self.boxsize = self.tl_boxsizes[1]
                        self.cansize = self.tl_cansizes[1]
                        self.probability = self.tl_base_probabilities[1]
                        self.base_probability = self.tl_base_probabilities[2]
                elif self.boxnum == 3:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[2]
                        self.can_remaining = self.vs_cansizes[2]
                        self.boxsize = self.vs_boxsizes[2]
                        self.cansize = self.vs_cansizes[2]
                        self.probability = self.vs_base_probabilities[2]
                        self.base_probability = self.vs_base_probabilities[3]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[2]
                        self.can_remaining = self.tl_cansizes[2]
                        self.boxsize = self.tl_boxsizes[2]
                        self.cansize = self.tl_cansizes[2]
                        self.probability = self.tl_base_probabilities[2]
                        self.base_probability = self.tl_base_probabilities[3]
                elif self.boxnum == 4:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[3]
                        self.can_remaining = self.vs_cansizes[3]
                        self.boxsize = self.vs_boxsizes[3]
                        self.cansize = self.vs_cansizes[3]
                        self.probability = self.vs_base_probabilities[3]
                        self.base_probability = self.vs_base_probabilities[4]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[3]
                        self.can_remaining = self.tl_cansizes[3]
                        self.boxsize = self.tl_boxsizes[3]
                        self.cansize = self.tl_cansizes[3]
                        self.probability = self.tl_base_probabilities[3]
                        self.base_probability = self.tl_base_probabilities[4]
                elif self.boxnum == 5:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[4]
                        self.can_remaining = self.vs_cansizes[4]
                        self.boxsize = self.vs_boxsizes[4]
                        self.cansize = self.vs_cansizes[4]
                        self.probability = self.vs_base_probabilities[4]
                        self.base_probability = self.vs_base_probabilities[5]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[4]
                        self.can_remaining = self.tl_cansizes[4]
                        self.boxsize = self.tl_boxsizes[4]
                        self.cansize = self.tl_cansizes[4]
                        self.probability = self.tl_base_probabilities[4]
                        self.base_probability = self.tl_base_probabilities[5]
                elif self.boxnum > 5:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[5]
                        self.can_remaining = self.vs_cansizes[5]
                        self.boxsize = self.vs_boxsizes[5]
                        self.cansize = self.vs_cansizes[5]
                        self.probability = self.vs_base_probabilities[5]
                        self.base_probability = self.vs_base_probabilities[5]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[5]
                        self.can_remaining = self.tl_cansizes[5]
                        self.boxsize = self.tl_boxsizes[5]
                        self.cansize = self.tl_cansizes[5]
                        self.probability = self.tl_base_probabilities[5]
                        self.base_probability = self.tl_base_probabilities[5]

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
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **Yes**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                else:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **No**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                g_embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
                await interaction.response.edit_message(embed=g_embed, view=self)

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
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **Yes**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                else:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **No**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                g_embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
                await interaction.response.edit_message(embed=g_embed, view=self)

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
                    self.probability = 0
                    self.children[1].disabled = True
                if self.probability > self.base_probability:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **Yes**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                else:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **No**"
                                                 f" ({round(self.probability * 100, 2)}% probability)"))
                g_embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
                await interaction.response.edit_message(embed=g_embed, view=self)

            @discord.ui.button(label='Next Box', style=discord.ButtonStyle.green)
            async def nextbox(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.boxnum += 1
                if self.boxnum == 1:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[0]
                        self.can_remaining = self.vs_cansizes[0]
                        self.boxsize = self.vs_boxsizes[0]
                        self.cansize = self.vs_cansizes[0]
                        self.probability = self.vs_base_probabilities[0]
                        self.base_probability = self.vs_base_probabilities[1]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[0]
                        self.can_remaining = self.tl_cansizes[0]
                        self.boxsize = self.tl_boxsizes[0]
                        self.cansize = self.tl_cansizes[0]
                        self.probability = self.tl_base_probabilities[0]
                        self.base_probability = self.tl_base_probabilities[1]
                elif self.boxnum == 2:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[1]
                        self.can_remaining = self.vs_cansizes[1]
                        self.boxsize = self.vs_boxsizes[1]
                        self.cansize = self.vs_cansizes[1]
                        self.probability = self.vs_base_probabilities[1]
                        self.base_probability = self.vs_base_probabilities[2]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[1]
                        self.can_remaining = self.tl_cansizes[1]
                        self.boxsize = self.tl_boxsizes[1]
                        self.cansize = self.tl_cansizes[1]
                        self.probability = self.tl_base_probabilities[1]
                        self.base_probability = self.tl_base_probabilities[2]
                elif self.boxnum == 3:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[2]
                        self.can_remaining = self.vs_cansizes[2]
                        self.boxsize = self.vs_boxsizes[2]
                        self.cansize = self.vs_cansizes[2]
                        self.probability = self.vs_base_probabilities[2]
                        self.base_probability = self.vs_base_probabilities[3]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[2]
                        self.can_remaining = self.tl_cansizes[2]
                        self.boxsize = self.tl_boxsizes[2]
                        self.cansize = self.tl_cansizes[2]
                        self.probability = self.tl_base_probabilities[2]
                        self.base_probability = self.tl_base_probabilities[3]
                elif self.boxnum == 4:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[3]
                        self.can_remaining = self.vs_cansizes[3]
                        self.boxsize = self.vs_boxsizes[3]
                        self.cansize = self.vs_cansizes[3]
                        self.probability = self.vs_base_probabilities[3]
                        self.base_probability = self.vs_base_probabilities[4]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[3]
                        self.can_remaining = self.tl_cansizes[3]
                        self.boxsize = self.tl_boxsizes[3]
                        self.cansize = self.tl_cansizes[3]
                        self.probability = self.tl_base_probabilities[3]
                        self.base_probability = self.tl_base_probabilities[4]
                elif self.boxnum == 5:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[4]
                        self.can_remaining = self.vs_cansizes[4]
                        self.boxsize = self.vs_boxsizes[4]
                        self.cansize = self.vs_cansizes[4]
                        self.probability = self.vs_base_probabilities[4]
                        self.base_probability = self.vs_base_probabilities[5]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[4]
                        self.can_remaining = self.tl_cansizes[4]
                        self.boxsize = self.tl_boxsizes[4]
                        self.cansize = self.tl_cansizes[4]
                        self.probability = self.tl_base_probabilities[4]
                        self.base_probability = self.tl_base_probabilities[5]
                elif self.boxnum > 5:
                    if self.event_type == 1:
                        self.remaining = self.vs_boxsizes[5]
                        self.can_remaining = self.vs_cansizes[5]
                        self.boxsize = self.vs_boxsizes[5]
                        self.cansize = self.vs_cansizes[5]
                        self.probability = self.vs_base_probabilities[5]
                        self.base_probability = self.vs_base_probabilities[5]
                    elif self.event_type == 2:
                        self.remaining = self.tl_boxsizes[5]
                        self.can_remaining = self.tl_cansizes[5]
                        self.boxsize = self.tl_boxsizes[5]
                        self.cansize = self.tl_cansizes[5]
                        self.probability = self.tl_base_probabilities[5]
                        self.base_probability = self.tl_base_probabilities[5]
                self.value = 4
                for item in self.children:
                    item.disabled = False
                g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                    content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                             f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                             f"Should I pull? **Yes**"
                                             f" ({round(self.probability * 100, 2)}% probability)"))
                g_embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
                await interaction.response.edit_message(embed=g_embed, view=self)

            @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger)
            async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.send_message('Closing gift box calculator.', ephemeral=True)
                for item in self.children:
                    item.disabled = True
                self.value = False
                self.stop()

            @discord.ui.button(label='Manual Input', style=discord.ButtonStyle.secondary, row=1)
            async def manualinput(self, button: discord.ui.Button, interaction: discord.Interaction):
                async def remaining_prompt(attempts=1, sent_messages=[]):
                    def check(m):
                        return m.author == self.context.author and m.channel == self.context.channel

                    g_sent_message = await self.context.send(embed=gen_embed(
                        title='Items remaining',
                        content='How many items are remaining in the box?'))
                    sent_messages.append(g_sent_message)
                    try:
                        mmsg = await self.context.bot.wait_for('message', check=check, timeout=60.0)
                    except asyncio.TimeoutError:
                        await self.context.send(embed=gen_embed(title='Gift box Cancelled',
                                                                content='Gift box calculator cancelled.'))
                        return
                    if re.match(r'^\d+$', mmsg.clean_content):
                        if validators.between(int(mmsg.clean_content), min=0, max=self.boxsize):
                            for message in sent_messages:
                                await message.delete()
                            await mmsg.delete()
                            return int(mmsg.clean_content)
                        elif attempts > 3:
                            raise discord.ext.commands.BadArgument()
                        else:
                            g_sent_message = await self.context.send(embed=gen_embed(
                                title='Items remaining',
                                content=(f"Sorry, I didn't catch that or it was an invalid format.\n"
                                         f"Please enter a number from 1-{self.boxsize}.")))
                            sent_messages.append(g_sent_message)
                            attempts += 1
                            return await remaining_prompt(attempts, sent_messages)
                    elif attempts > 3:
                        raise discord.ext.commands.BadArgument()
                    else:
                        g_sent_message = await self.context.send(embed=gen_embed(
                            title='Items remaining',
                            content=(f"Sorry, I didn't catch that or it was an invalid format.\n"
                                     f"Please enter a number from 1-{self.boxsize}.")))
                        sent_messages.append(g_sent_message)
                        attempts += 1
                        return await remaining_prompt(attempts, sent_messages)

                await interaction.response.defer()
                self.remaining = await remaining_prompt()
                if self.remaining != 0:
                    self.probability = self.can_remaining / self.remaining
                else:
                    self.probability = 0
                    self.children[1].disabled = True
                    self.children[2].disabled = True
                if self.probability > self.base_probability:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **Yes**"
                                                 f"({round(self.probability * 100, 2)}% probability)"))
                else:
                    g_embed = gen_embed(title=f'Gift Box #{self.boxnum}',
                                        content=(f"**{self.remaining}/{self.boxsize} remaining**\n"
                                                 f"{self.can_remaining}/{self.cansize} cans remaining\n\n"
                                                 f"Should I pull? **No**"
                                                 f"({round(self.probability * 100, 2)}% probability)"))
                g_embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
                await interaction.edit_original_response(embed=g_embed, view=self)

        await ctx.interaction.response.defer()
        giftbox_view = GiftboxMenu(ctx, giftbox, event)
        current_probability = giftbox_view.can_remaining / giftbox_view.remaining
        embed = gen_embed(title=f'Gift Box #{giftbox}',
                          content=(f"**{giftbox_view.remaining}/{giftbox_view.boxsize} remaining**\n"
                                   f"{giftbox_view.can_remaining}/{giftbox_view.cansize} cans remaining\n\n"
                                   f"Should I pull? **Yes** ({round(current_probability * 100, 2)}% probability)"))
        embed.set_footer(text='Subtracting one can will not subtract from the total remaining.')
        sent_message = await ctx.interaction.followup.send(embed=embed, view=giftbox_view)
        await giftbox_view.wait()
        await sent_message.edit(view=giftbox_view)

    refill = SlashCommandGroup('refill', 'Refill related commands')

    @refill.command(name='counter',
                    description='Refill counter to help you keep track of when to refill')
    async def refillcounter(self,
                            ctx: discord.ApplicationContext,
                            games: Option(int, '# of games left in the set',
                                          min_value=1,
                                          max_value=30,
                                          default=30,
                                          required=False)):
        class RefillCounter(discord.ui.View):
            def __init__(self, context, game_count):
                super().__init__(timeout=900.0)
                self.context = context
                self.counter = game_count
                self.value = False

            async def end_interaction(self,
                                      interaction: discord.Interaction):
                view = discord.ui.View.from_message(interaction.message)
                for child in view.children:
                    child.disabled = True

                self.value = True
                await interaction.message.edit(view=view)
                self.stop()

            @discord.ui.button(emoji='❌', style=discord.ButtonStyle.secondary)
            async def exit(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                await self.end_interaction(interaction)

            @discord.ui.button(emoji='🔄', style=discord.ButtonStyle.secondary)
            async def refill(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                self.counter = 30
                new_embed = gen_embed(title='Refill Counter',
                                      content=f'{self.counter} games left in the set')
                await interaction.message.edit(embed=new_embed)

            @discord.ui.button(emoji='➕', style=discord.ButtonStyle.green)
            async def plus(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                self.counter += 1
                new_embed = gen_embed(title='Refill Counter',
                                      content=f'{self.counter} games left in the set')
                await interaction.message.edit(embed=new_embed)

            @discord.ui.button(emoji='➖', style=discord.ButtonStyle.danger)
            async def minus(self, button: discord.ui.Button, interaction: discord.Interaction):
                await interaction.response.defer()
                self.counter -= 1
                new_embed = gen_embed(title='Refill Counter',
                                      content=f'{self.counter} games left in the set')
                await interaction.message.edit(embed=new_embed)

        await ctx.interaction.response.defer()

        try:
            refill_running = self.refill_running[str(ctx.interaction.channel.id)]
        except KeyError:
            self.refill_running[str(ctx.interaction.channel.id)] = False

        if self.refill_running[str(ctx.interaction.channel.id)]:
            embed = gen_embed(title='Refill Counter',
                              content=f'A counter is already running in this channel!')
            sent_message = await ctx.interaction.followup.send(embed=embed, ephemeral=True)
            return
        refillcounter_view = RefillCounter(ctx, games)
        embed = gen_embed(title='Refill Counter',
                          content=f'{games} games left in the set')
        sent_message = await ctx.interaction.followup.send(embed=embed, view=refillcounter_view)
        self.refill_running[str(ctx.interaction.channel.id)] = True
        while refillcounter_view.value is not True:
            if ctx.channel.last_message.id != sent_message.id:
                await sent_message.delete()
                embed = gen_embed(title='Refill Counter',
                                  content=f'{refillcounter_view.counter} games left in the set')
                sent_message = await ctx.channel.send(embed=embed, view=refillcounter_view)
            await asyncio.sleep(5)
        self.refill_running[str(ctx.interaction.channel.id)] = False

    trackfiller = SlashCommandGroup('trackfiller', 'Filler tracking for tiering servers',
                                    default_member_permissions=discord.Permissions(manage_roles=True))

    @trackfiller.command(name='enable',
                         description='Enable filler tracking for the server')
    @default_permissions(manage_roles=True)
    async def trackfiller_enable(self,
                                 ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.fillers.find_one({'server_id': ctx.interaction.guild_id})
        if document:
            await db.fillers.update_one({'server_id': ctx.interaction.guild_id},
                                        {"$set": {"enabled": True}})
        else:
            post = {'server_id': ctx.interaction.guild_id,
                    'fillers': [],
                    'roles': [],
                    'enabled': True
                    }
            await db.fillers.insert_one(post)
        await ctx.interaction.followup.send(embed=gen_embed(title='trackfiller',
                                                            content=f'Enabled trackfiller for {ctx.guild.name}.'),
                                            ephemeral=True)
        await ctx.interaction.followup.send(content=('How do I set up who can add fillers?\n'
                                                     'https://files.s-neon.xyz/share/2022-05-25%2015-18-21.mp4'),
                                            ephemeral=True)
        await ctx.interaction.followup.send(content=('How do I add a filler?\n'
                                                     'https://files.s-neon.xyz/share/DiscordPTB_QkOPfrdP4L.png'),
                                            ephemeral=True)

    @trackfiller.command(name='disable',
                         description='Disable filler tracking for the server')
    @default_permissions(manage_roles=True)
    async def trackfiller_disable(self,
                                  ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.fillers.find_one({'server_id': ctx.interaction.guild_id})
        if document:
            await db.fillers.update_one({'server_id': ctx.interaction.guild_id},
                                        {"$set": {"enabled": False}})
        else:
            post = {'server_id': ctx.interaction.guild_id,
                    'fillers': [],
                    'roles': [],
                    'enabled': False
                    }
            await db.fillers.insert_one(post)
        await ctx.interaction.followup.send(embed=gen_embed(title='trackfiller',
                                                            content=f'Disabled trackfiller for {ctx.guild.name}.'),
                                            ephemeral=True)

    @trackfiller.command(name='help',
                         description='Display help on how to use the filler tracking feature')
    async def trackfiller_help(self,
                               ctx: discord.ApplicationContext):
        await ctx.respond(content=('How do I add a filler?\n'
                                   'https://files.s-neon.xyz/share/DiscordPTB_QkOPfrdP4L.png'),
                          ephemeral=True)

    @trackfiller.command(name='list',
                         description='List fillers')
    async def trackfiller_list(self,
                               ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer()
        fillers = []
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        for memberid in document['fillers']:
            member = await self.bot.fetch_user(memberid)
            fillers.append(member.name)
        fillers_str = ", ".join(fillers)
        embed = gen_embed(title='List of Fillers',
                          content=f'{fillers_str}')
        await embed_splitter(embed=embed, destination=ctx.channel, followup=ctx.interaction.followup)

    @trackfiller.command(name='remove',
                         description='Remove a filler from the list')
    @default_permissions(manage_roles=True)
    async def trackfiller_remove(self,
                                 ctx: discord.ApplicationContext,
                                 user: Option(discord.Member, 'Filler to remove')):
        await ctx.interaction.response.defer(ephemeral=True)
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        fillers = document['fillers']
        fillers.remove(user.id)
        await db.fillers.update_one({'server_id': ctx.guild.id}, {"$set": {"fillers": fillers}})
        await ctx.interaction.followup.send(embed=
                                            gen_embed(title='Remove Filler',
                                                      content=f'{user.name}#{user.discriminator} removed.'),
                                            ephemeral=True)

    @trackfiller.command(name='clear',
                         description='Clear the filler list')
    @default_permissions(manage_roles=True)
    async def trackfiller_clear(self,
                                ctx: discord.ApplicationContext):
        await ctx.interaction.response.defer(ephemeral=True)
        await db.fillers.update_one({'server_id': ctx.guild.id}, {"$set": {"fillers": []}})
        await ctx.interaction.followup.send(embed=
                                            gen_embed(title='Clear Filler List',
                                                      content=f'The filler list has been cleared.'),
                                            ephemeral=True)

    @user_command(name='Add User to Filler List')
    @default_permissions()
    async def addfiller(self,
                        ctx: discord.ApplicationContext,
                        member: discord.Member):
        document = await db.fillers.find_one({'server_id': ctx.guild.id})
        if document:
            fillers = document['fillers']
            enabled = document['enabled']
        else:
            fillers = []
            enabled = False
        if enabled:
            if member.id in fillers:
                await ctx.respond(content='User is already in the list of fillers.', ephemeral=True)
            else:
                fillers.append(member.id)
                log.info(f'Appended user to filler list for {ctx.guild.name}')
                await db.fillers.update_one({'server_id': ctx.guild.id},
                                            {"$set": {"fillers": fillers, "roles": []}}, upsert=True)
                await ctx.respond(content=f"Added {member.name} to the list of fillers.", ephemeral=True)
        else:
            await ctx.respond(content='This is not enabled for this server.', ephemeral=True)


def setup(bot):
    bot.add_cog(Tiering(bot))
