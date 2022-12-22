import psutil
import time
import os
import datetime
from datetime import timedelta

import discord
from discord.ext import commands
from discord.commands import Option, SlashCommandGroup
from discord.enums import SlashCommandOptionType
from discord.ui import InputText, Modal

from __main__ import log, db
from formatting.embed import gen_embed
from formatting.constants import NAME, EXTENSIONS, VERSION as BOTVERSION
from commands.errorhandler import CheckOwner


class Miscellaneous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    async def generate_invite_link(self, permissions=discord.Permissions(1632444476630)):
        app_info = await self.bot.application_info()
        return discord.utils.oauth_url(app_info.id, permissions=permissions, scopes=['bot', 'applications.commands'])

    @discord.slash_command(name='stats',
                           description='Provides statistics about the bot.')
    async def stats(self,
                    ctx: discord.ApplicationContext):
        content = discord.Embed(colour=0x1abc9c)
        content.set_author(name=f"{NAME} v{BOTVERSION}", icon_url=self.bot.user.display_avatar.url)
        content.set_footer(text="Fueee~")
        content.add_field(name="Author", value="Neon#5555")
        content.add_field(name="BotID", value=self.bot.user.id)
        content.add_field(name="Messages",
                          value=f"{self.bot.message_count} ({(self.bot.message_count / ((time.time() - self.bot.uptime) / 60)):.2f}/min)")
        content.add_field(name="Commands Processed", value=f"{self.bot.command_count}")
        process = psutil.Process(os.getpid())
        mem = process.memory_full_info()
        mem = mem.uss / 1000000
        content.add_field(name="Memory Usage", value=f'{mem:.2f} MB')
        content.add_field(name="Servers", value=f"I am running on {str(len(self.bot.guilds))} servers")
        ctime = float(time.time() - self.bot.uptime)
        day = ctime // (24 * 3600)
        ctime = ctime % (24 * 3600)
        hour = ctime // 3600
        ctime %= 3600
        minutes = ctime // 60
        content.add_field(name="Uptime", value=f"{day:.0f} days\n{hour:.0f} hours\n{minutes:.0f} minutes")
        await ctx.respond(embed=content)

    @discord.slash_command(name='invite',
                           description='Create a link to invite the bot to your server.')
    async def invite(self,
                     ctx: discord.ApplicationContext):
        url = await self.generate_invite_link()
        content = discord.Embed(colour=0x1abc9c)
        content.set_author(name=f"{NAME} v{BOTVERSION}", icon_url=self.bot.user.display_avatar.url)
        content.set_footer(text="Fueee~")
        content.add_field(name="Invite Link:", value=url)
        await ctx.respond(embed=content)

    @discord.slash_command(name='support',
                           description='Support the bot by donating for server costs!')
    async def support(self,
                      ctx: discord.ApplicationContext):
        await ctx.respond(embed=gen_embed(title='Support Kanon Bot',
                                          content='Kanon costs money to run. I pay for her server costs out of pocket, '
                                                  'so any donation helps!\nSupport: https://www.patreon.com/kanonbot '
                                                  'or https://ko-fi.com/neonlights'))
        await ctx.send(embed=gen_embed(title='Thank you Kanon Supporters!',
                                       content=('**Thanks to:**\nReileky#4161, SinisterSmiley#0704, Makoto#7777, '
                                                'Vince.#6969, Elise ☆#0001, EN_Gaige#3910, shimmerleaf#2115, '
                                                'Hypnotic Rhythm#1260, wachie#0320, Ashlyne#8080, nehelenia#4489, '
                                                'careblaire#6969, Reileky#4161')))

    async def unload_autocomplete(self,
                                  ctx: discord.ApplicationContext):
        cog_list = []
        for x, y in self.bot.extensions.items():
            cog_name = x.replace('commands.', '')
            cog_list.append(cog_name)
        return [cog for cog in cog_list if cog.startswith(ctx.value.lower())]

    @discord.slash_command(name='unload',
                           description='Unload a cog/extension.')
    @is_owner()
    async def unload(self,
                     ctx: discord.ApplicationContext,
                     cog: Option(str, 'Name of cog/extension',
                                 autocomplete=unload_autocomplete)):
        await ctx.interaction.response.defer()
        cog = cog.lower()
        self.bot.unload_extension(f'commands.{cog}')
        await self.bot.sync_commands(force=True, guild_ids=[911509078038151168])
        await ctx.interaction.followup.send(
            embed=gen_embed(title='Unload', content=f'Extension {cog} has been unloaded.')
        )

    async def load_autocomplete(self,
                                ctx: discord.ApplicationContext):
        return [cog for cog in EXTENSIONS if cog.startswith(ctx.value.lower())]

    @discord.slash_command(name='load',
                           description='Load a cog/extension.')
    @is_owner()
    async def load(self,
                   ctx: discord.ApplicationContext,
                   cog: Option(str, 'Name of cog/extension',
                               autocomplete=load_autocomplete)):
        await ctx.interaction.response.defer()
        cog = cog.lower()
        self.bot.load_extension(f'commands.{cog}')
        await self.bot.sync_commands()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='Load', content=f'Extension {cog} has been loaded.')
        )

    @discord.slash_command(name='reload',
                           description='Reload a cog/extension.')
    @is_owner()
    async def reload(self,
                     ctx: discord.ApplicationContext,
                     cog: Option(str, 'Name of cog/extension',
                                 autocomplete=unload_autocomplete)):
        await ctx.interaction.response.defer()
        cog = cog.lower()
        self.bot.reload_extension(f'commands.{cog}')
        await self.bot.sync_commands()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='Reload', content=f'Extension {cog} has been reloaded.')
        )

    @discord.slash_command(name='announce',
                           description='Developer Only. Creates an announcement to send to all servers.')
    @is_owner()
    async def announce(self,
                       ctx: discord.ApplicationContext,
                       attachment: Option(SlashCommandOptionType.attachment,
                                          'Image to attach to the message',
                                          required=False)):

        # check file type
        valid_media_type = ['image/jpeg', 'image/png', 'image/svg+xml', 'image/avif',
                            'image/heif',
                            'image/bmp', 'image/gif', 'image/vnd.mozilla.apng',
                            'image/tiff']
        if attachment:
            if attachment.content_type not in valid_media_type:
                raise commands.UserInputError(message='This is not a valid media type!')

        class AnnouncementModal(Modal):
            def __init__(self, bot, *args, **kwargs) -> None:
                super().__init__(*args, **kwargs)
                self.bot = bot
                self.add_item(
                    InputText(
                        label='Announcement Message',
                        value='Type the announcement here',
                        style=discord.InputTextStyle.long
                    )
                )

            async def callback(self, interaction: discord.Interaction):
                await interaction.response.defer()
                embed = gen_embed(title='Global Announcement',
                                  content=(f'Admins of the server can always toggle announcements from the bot creator'
                                           f' on/off by using /settings.\n\n{self.children[0].value}'))
                if attachment:
                    embed.set_image(url=attachment.url)

                # await interaction.followup.send(embed=embed)

                for guild in self.bot.guilds:
                    document = await db.servers.find_one({'server_id': guild.id})
                    log.info(f'Announcement Workflow - Checking document for {guild.name}')
                    if document['announcements']:
                        log.info(f'Announcement Workflow - Announcements enabled for {guild.name}, sending...')
                        sent = False
                        if document['announcement_channel']:
                            try:
                                channel = self.bot.get_channel(document['announcement_channel'])
                                if channel.permissions_for(guild.me).send_messages:
                                    await channel.send(embed=embed)
                                    log.info(f'Announcement sent for {guild.name} in #{channel.name}')
                                    sent = True
                                    continue
                                else:
                                    raise Exception
                            except Exception as e:
                                pass
                        try:
                            if (guild.public_updates_channel
                                    and guild.public_updates_channel.permissions_for(guild.me).send_messages
                                    and not sent):
                                await guild.public_updates_channel.send(embed=embed)
                                log.info(
                                    f'Announcement sent for {guild.name} in #{guild.public_updates_channel.name} (Public Update Channel)')
                                sent = True
                                continue
                        except Exception as e:
                            pass
                        try:
                            if (guild.system_channel
                                    and guild.system_channel.permissions_for(guild.me).send_messages
                                    and not sent):
                                await guild.system_channel.send(embed=embed)
                                log.info(
                                    f'Announcement sent for {guild.name} in #{guild.system_channel.name} (System Channel)')
                                sent = True
                                continue
                        except Exception as e:
                            pass
                        try:
                            general = discord.utils.find(lambda x: x.name == 'general', guild.text_channels)
                            if general and general.permissions_for(guild.me).send_messages and not sent:
                                await general.send(embed=embed)
                                log.info(f'Announcement sent for {guild.name} in #{general.name} (General Channel)')
                                sent = True
                                continue
                        except Exception as e:
                            pass
                        finally:
                            for channel in guild.text_channels:
                                try:
                                    if channel.permissions_for(guild.me).send_messages and not sent:
                                        await channel.send(embed=embed)
                                        log.info(
                                            f'Announcement sent for {guild.name} in #{channel.name} (First available channel)')
                                        break
                                except Exception as e:
                                    pass
                            if not sent:
                                log.info(f'Could not send announcement for {guild.name}. Skipping...')
                await interaction.followup.send(embed=
                                                gen_embed(title='Announce',
                                                          content='Announcement sent out successfully.'),
                                                ephemeral=True)

        modal = AnnouncementModal(title='Prepare KanonBot Announcement', bot=self.bot)
        await ctx.send_modal(modal)

    datadeletion = SlashCommandGroup('delete', 'Delete guild/user data')

    @datadeletion.command(name='guild',
                          description='Delete all data for specified guild')
    @is_owner()
    async def del_guild(self,
                        ctx: discord.ApplicationContext,
                        guild: Option(discord.Guild, 'Guild ID of the guild you wish to delete data for')):
        await ctx.interaction.response.defer()
        await db.msgid.delete_many({'server_id': guild.id})
        await db.warns.delete_many({'server_id': guild.id})
        await db.rolereact.delete_many({'server_id': guild.id})
        await db.servers.delete_one({'server_id': guild.id})
        await db.emoji.delete_many({'server_id': guild.id})
        await db.reminders.delete_many({'server_id': guild.id})
        await guild.leave()
        await ctx.interaction.followup.send(
            embed=gen_embed(title='delete guild',
                            content=f'Guild {guild.name} (ID: {guild.id} data has been deleted.'),
            ephemeral=True)

    @datadeletion.command(name='user',
                          description='Delete all data for specified user')
    @is_owner()
    async def del_user(self,
                       ctx: discord.ApplicationContext,
                       user: Option(discord.User, 'User you wish to delete data for')):
        await ctx.interaction.response.defer()
        await db.msgid.delete_many({'author_id': user.id})
        await db.warns.delete_many({'user_id': user.id})
        await db.reminders.delete_many({'user_id': user.id})
        await ctx.interaction.followup.send(
            embed=gen_embed(title='delete user',
                            content=f'User {user.name}#{user.discriminator} (ID: {user.id}) data '
                                    f'has been deleted.'),
            ephemeral=True)

    @discord.slash_command(name='patreonmagic',
                           description='Fix patreon roles, DEV ONLY')
    @is_owner()
    async def patreon_magic(self,
                            ctx: discord.ApplicationContext):
        # BREAKING CHANGES BELOW - DO NOT ACTIVATE UNTIL READY
        await ctx.interaction.response.defer(ephemeral=True)

        patreon = ctx.guild.get_role(201966886861275137)
        guild = ctx.guild
        if patreon:
            log.info('patreon role found')
            # To prevent search through the entire audit log, limit to 1 minute in the past
            async for entry in guild.audit_logs(action=discord.AuditLogAction.member_role_update,
                                                user=self.bot.get_user(216303189073461248),
                                                after=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(weeks=52))):
                try:
                    await entry.target.add_roles(patreon, reason="Auto-reassignment of patron role")

                except discord.Forbidden:
                    raise commands.CommandError("I don't have permission to modify a user's roles.")

                except discord.HTTPException:
                    raise commands.CommandError("Something happened while attempting to add role.")
        await ctx.interaction.followup.send('Readded patreon roles',
                                            ephemeral=True)


def setup(bot):
    bot.add_cog(Miscellaneous(bot))
