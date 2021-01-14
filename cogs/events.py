import json
import sys
import time
import traceback

import discord
from discord.ext import commands

import Bot
import store
from config import config


class Events(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        botLogChan = self.bot.get_channel(id=int(config.moon.logchan))
        add_server_info = await store.sql_addinfo_by_server(str(guild.id), guild.name,
                                                            config.discord.prefixCmd)
        await botLogChan.send(f'Bot joins a new guild {guild.name} / {guild.id} / Users: {len(guild.members)}. Total guilds: {len(self.bot.guilds)}.')
        return

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        botLogChan = self.bot.get_channel(id=int(config.moon.logchan))
        add_server_info = await store.sql_updateinfo_by_server(str(guild.id), "status", "REMOVED")
        await botLogChan.send(f'Bot was removed from guild {guild.name} / {guild.id}. Total guilds: {len(self.bot.guilds)}')
        return

    @commands.Cog.listener()
    async def on_message(self, message):
        # should ignore webhook message
        if isinstance(message.channel, discord.DMChannel) == False and message.webhook_id:
            return

        if isinstance(message.channel, discord.DMChannel) == False and message.author.bot == False and len(message.content) > 0 and message.author != self.bot.user:
            await Bot.add_msg_redis(json.dumps([str(message.guild.id), message.guild.name, str(message.channel.id), message.channel.name,
                                                str(message.author.id), message.author.name, str(message.id), message.content, int(time.time())]), False)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # If bot react, ignore.
        if user.id == self.bot.user.id:
            return
        # If other people beside bot react.
        else:
            # If reaction is OK box and message author is bot itself
            if reaction.emoji == Bot.EMOJI_OK_BOX and reaction.message.author.id == self.bot.user.id:
                # do not delete some embed message
                if reaction.message.embeds and len(reaction.message.embeds) > 0:
                    try:
                        title = reaction.message.embeds[0].title
                        if title and 'FREE TIP' in str(title.upper()):
                            return
                    except Exception as e:
                        pass
                try:
                    await reaction.message.delete()
                except Exception as e:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id is None:
            return  # Reaction is on a private message
        """Handle a reaction add."""
        try:
            emoji_partial = str(payload.emoji)
            message_id = payload.message_id
            channel_id = payload.channel_id
            user_id = payload.user_id
            guild = self.bot.get_guild(payload.guild_id)
            channel = self.bot.get_channel(id=channel_id)
            if not channel:
                return
            if isinstance(channel, discord.DMChannel):
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await Bot.logchanbot(traceback.format_exc())
            return
        message = None
        author = None
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                author = message.author
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                # No message found
                return
            member = self.bot.get_user(id=user_id)
            if emoji_partial in [Bot.EMOJI_OK_BOX] and message.author.id == self.bot.user.id \
                    and author != member and message:
                # do not delete some embed message
                if message.embeds and len(message.embeds) > 0:
                    try:
                        title = message.embeds[0].title
                        if title and 'FREE TIP' in str(title.upper()):
                            return
                    except Exception as e:
                        pass
                try:
                    await message.delete()
                except Exception as e:
                    pass


def setup(bot):
    bot.add_cog(Events(bot))
