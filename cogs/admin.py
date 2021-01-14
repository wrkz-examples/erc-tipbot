import sys
import traceback
from datetime import datetime

import discord
from discord.ext import commands

import Bot
import store


class Admin(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return commands.is_owner()

    @commands.command(usage='pending', description='Check pending things')
    async def pending(self, ctx):
        if str(ctx.author.id) not in [str(each) for each in Bot.MOD_LIST]:
            return

        ts = datetime.utcnow()
        embed = discord.Embed(title='Pending Actions', timestamp=ts)
        embed.add_field(name="Pending Tx", value=str(len(self.bot.TX_IN_PROCESS)), inline=True)
        if len(self.bot.TX_IN_PROCESS) > 0:
            string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
            list_pending = '{' + ', '.join(string_ints) + '}'
            embed.add_field(name="List Pending By", value=list_pending, inline=True)
        embed.set_footer(text=f"Pending requested by {ctx.message.author.name}#{ctx.message.author.discriminator}")
        try:
            msg = await ctx.author.send(embed=embed)
            await msg.add_reaction(Bot.EMOJI_OK_BOX)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await Bot.logchanbot(traceback.format_exc())
        return

    @commands.command(usage='cleartx', description='Clear TX_IN_PROCESS')
    async def cleartx(self, ctx):
        if str(ctx.author.id) not in [str(each) for each in Bot.MOD_LIST]:
            return

        if len(self.bot.TX_IN_PROCESS) == 0:
            await ctx.author.send(f'{ctx.author.mention} Nothing in tx pending to clear.')
        else:
            try:
                string_ints = [str(num) for num in self.bot.TX_IN_PROCESS]
                list_pending = '{' + ', '.join(string_ints) + '}'
                await ctx.message.add_reaction(Bot.EMOJI_WARNING)
                await Bot.logchanbot(f'{ctx.author.mention} Clearing {str(len(self.bot.TX_IN_PROCESS))} {list_pending} in pending...')
                await ctx.author.send(f'Clearing {str(len(self.bot.TX_IN_PROCESS))} {list_pending} in pending...')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await Bot.logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS = []
        return

    @commands.command(usage='fetchtalk <channel> <countmsg: int>', description="Fetch messages from channel")
    async def fetchtalk(self, ctx, talk_channel: discord.TextChannel, countmsg: int = 5000):
        count = 0
        temp_msg_list = []
        if talk_channel:
            messages = await talk_channel.history(limit=countmsg).flatten()
            try:
                if messages and len(messages) > 0:
                    for each in messages:
                        # ignore bot messages
                        if each.author != self.bot.user:
                            count += 1
                            # add to DB
                            timestamp = datetime.timestamp(each.created_at)
                            temp_msg_list.append((str(talk_channel.guild.id), talk_channel.guild.name, str(talk_channel.id), talk_channel.name, str(each.author.id),
                                                  each.author.name,
                                                  str(each.id), each.content, timestamp))
                            print((str(talk_channel.guild.id), talk_channel.guild.name, str(talk_channel.id), talk_channel.name, str(each.author.id), each.author.name,
                                   str(each.id),
                                   each.content, timestamp))
                if len(temp_msg_list) > 0:
                    try:
                        num_add = await store.sql_add_messages(temp_msg_list)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await Bot.logchanbot(traceback.format_exc())
                    await ctx.send(f'{ctx.author.mention} Found {len(temp_msg_list)} message(s) and added {str(num_add)}.')
                    return
            except Exception as e:
                print(traceback.format_exc())
        else:
            await ctx.message.add_reaction(Bot.EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} I can not find channel **{talk_channel}**.')
            return

    @commands.command(usage='prefix', description='Get current prefix')
    async def prefix(self, ctx):
        prefix = await Bot.get_guild_prefix(ctx)
        try:
            msg = await ctx.send(f'{Bot.EMOJI_INFORMATION} {ctx.author.mention}, the prefix here is **{prefix}**')
            await msg.add_reaction(Bot.EMOJI_OK_BOX)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await msg.add_reaction(Bot.EMOJI_ERROR)
            await Bot.logchanbot(traceback.format_exc())
        return


def setup(bot):
    bot.add_cog(Admin(bot))
