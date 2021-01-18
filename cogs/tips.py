import asyncio
import re
import sys
import time
import traceback
from datetime import datetime
import random

import discord
from discord.ext import commands

import store
import utils
from Bot import TOKEN_NAME, create_address_eth, num_format_coin, EMOJI_OK_HAND, EMOJI_OK_BOX, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, \
    EMOJI_MONEYFACE, NOTIFICATION_OFF_CMD, EMOJI_SPEAK, EMOJI_BELL, EMOJI_BELL_SLASH, EMOJI_HOURGLASS_NOT_DONE, EMOJI_INFORMATION, EMOJI_PARTY, seconds_str
from config import config


class Tips(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(usage='notifytip <on/off>', description="Toggle notify tip notification from bot ON|OFF")
    async def notifytip(self, ctx, onoff: str):
        if onoff.upper() not in ["ON", "OFF"]:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} You need to use only `ON` or `OFF`.')
            return

        onoff = onoff.upper()
        notifyList = await store.sql_get_tipnotify()
        if onoff == "ON":
            if str(ctx.message.author.id) in notifyList:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "ON")
                await ctx.send(f'{ctx.author.mention} OK, you will get all notification when tip.')
                await ctx.message.add_reaction(EMOJI_BELL)
                return
            else:
                await ctx.send(f'{ctx.author.mention} You already have notification ON by default.')
                await ctx.message.add_reaction(EMOJI_BELL)
                return
        elif onoff == "OFF":
            if str(ctx.message.author.id) in notifyList:
                await ctx.send(f'{ctx.author.mention} You already have notification OFF.')
                await ctx.message.add_reaction(EMOJI_BELL_SLASH)
                return
            else:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
                await ctx.send(f'{ctx.author.mention} OK, you will not get any notification when anyone tips.')
                await ctx.message.add_reaction(EMOJI_BELL_SLASH)
                return

    @commands.command(usage='randtip <amount> [all/online/last]', aliases=['randomtip'], description='Tip to random user in the guild')
    async def randtip(self, ctx, amount: str, *, rand_option: str = None):
        # Check if tx in progress
        if ctx.message.author.id in self.bot.TX_IN_PROCESS:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        amount = amount.replace(",", "")

        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        # Get a random user in the guild, except bots. At least 3 members for random.
        has_last = False
        message_talker = None
        listMembers = None
        minimum_users = 2
        try:
            # Check random option
            if rand_option is None or rand_option.upper().startswith("ALL"):
                listMembers = [member for member in ctx.guild.members if member.bot is False]
            elif rand_option and rand_option.upper().startswith("ONLINE"):
                listMembers = [member for member in ctx.guild.members if member.bot is False and member.status != discord.Status.offline]
            elif rand_option and rand_option.upper().strip().startswith("LAST "):
                argument = rand_option.strip().split(" ")
                if len(argument) == 2:
                    # try if the param is 1111u
                    num_user = argument[1].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "")
                        num_user = num_user.replace("person", "")
                        num_user = num_user.replace("users", "")
                        num_user = num_user.replace("user", "")
                        num_user = num_user.replace("u", "")
                        try:
                            num_user = int(num_user)
                            if num_user < minimum_users:
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Number of random users cannot below **{minimum_users}**.')
                                return
                            elif num_user >= minimum_users:
                                message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                                if ctx.message.author.id in message_talker:
                                    message_talker.remove(ctx.message.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) < minimum_users:
                                    await ctx.message.add_reaction(EMOJI_ERROR)
                                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count for random tip.')
                                    return
                                elif len(message_talker) < num_user:
                                    try:
                                        await ctx.message.add_reaction(EMOJI_INFORMATION)
                                        await ctx.send(
                                            f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                            f' and will random to one of those **{len(message_talker)}** users.')
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # Let it still go through
                                        # return
                            has_last = True
                        except ValueError:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                            return
                    else:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                        return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST** for random tip. Support only *LAST* **X**u right now.')
                    return
            if has_last is False and listMembers and len(listMembers) >= minimum_users:
                rand_user = random.choice(listMembers)
                max_loop = 0
                while True:
                    if rand_user != ctx.message.author and rand_user.bot is False:
                        break
                    else:
                        rand_user = random.choice(listMembers)
                    max_loop += 1
                    if max_loop >= 5:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {TOKEN_NAME} Please try again, maybe guild doesnot have so many users.')
                        return

            elif has_last is True and message_talker and len(message_talker) >= minimum_users:
                rand_user_id = random.choice(message_talker)
                max_loop = 0
                while True:
                    rand_user = self.bot.get_user(id=rand_user_id)
                    if rand_user and rand_user != ctx.message.author and rand_user.bot is False and rand_user in ctx.guild.members:
                        break
                    else:
                        rand_user_id = random.choice(message_talker)
                        rand_user = self.bot.get_user(id=rand_user_id)
                    max_loop += 1
                    if max_loop >= 10:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {TOKEN_NAME} Please try again, maybe guild doesnot have so many users.')
                        return
                        break
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {TOKEN_NAME} not enough member for random tip.')
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
            return

        notifyList = await store.sql_get_tipnotify()
        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tip'])
        MaxTX = float(token_info['real_max_tip'])

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            return

        # add queue also randtip
        if ctx.message.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.message.author.id)
        else:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        print('random get user: {}/{}'.format(rand_user.name, rand_user.id))

        tip = None
        user_to = await store.sql_get_userwallet(str(rand_user.id), TOKEN_NAME)
        if user_to is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(rand_user.id), TOKEN_NAME, w, 'DISCORD')
            user_to = await store.sql_get_userwallet(str(rand_user.id), TOKEN_NAME)

        try:
            tip = await store.sql_mv_erc_single(str(ctx.message.author.id), str(rand_user.id), amount, TOKEN_NAME, "RANDTIP", token_info['contract'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        # remove queue from randtip
        if ctx.message.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.message.author.id)

        if tip:
            randtip_public_respond = False
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {rand_user.name}#{rand_user.discriminator} got your random tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} in server `{ctx.guild.name}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            if str(rand_user.id) not in notifyList:
                try:
                    await rand_user.send(
                        f'{EMOJI_MONEYFACE} You got a random tip of {num_format_coin(amount)} '
                        f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                        f'{NOTIFICATION_OFF_CMD}')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    await store.sql_toggle_tipnotify(str(user.id), "OFF")
            try:
                # try message in public also
                msg = await ctx.send(
                    f'{rand_user.name}#{rand_user.discriminator} got a random tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator}')
                await msg.add_reaction(EMOJI_OK_BOX)
                randtip_public_respond = True
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                pass
            serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
            if randtip_public_respond is False and serverinfo and 'botchan' in serverinfo and serverinfo['botchan']:
                # It has bot channel, let it post in bot channel
                try:
                    bot_channel = self.bot.get_channel(id=int(serverinfo['botchan']))
                    msg = await bot_channel.send(
                        f'{rand_user.name}#{rand_user.discriminator} got a random tip of {num_format_coin(amount)} '
                        f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in {ctx.channel.mention}')
                    await msg.add_reaction(EMOJI_OK_BOX)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
            await ctx.message.add_reaction(EMOJI_OK_BOX)
            return

    @commands.command(usage='freetip <amount> <duration> [comment]', description="Spread free tip by user reacting with emoji")
    async def freetip(self, ctx, amount: str, duration: utils.Duration, *, comment: str = None):
        # Check if tx in progress
        if ctx.message.author.id in self.bot.TX_IN_PROCESS:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        amount = amount.replace(",", "")
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        try:
            duration_s = int((duration - datetime.utcnow()).total_seconds())
        except Exception as e:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration.')
            return

        print('get duration: {}'.format(duration_s))
        if duration_s == 0:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use time format: XXs')
            return
        elif duration_s < config.freetip.duration_min or duration_s > config.freetip.duration_max:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. Please use between {str(config.freetip.duration_min)}s to {str(config.freetip.duration_max)}s.')
            return

        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        notifyList = await store.sql_get_tipnotify()
        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tip'])
        MaxTX = float(token_info['real_max_tip'])

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            return

        attend_list = []
        ts = datetime.utcnow()
        embed = discord.Embed(title=f"Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"React {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
        add_index = 0
        try:
            if comment and len(comment) > 0:
                add_index = 1
                embed.add_field(name="Comment", value=comment, inline=True)
            embed.add_field(name="Attendees", value="React below to join!", inline=False)
            embed.add_field(name="Individual Tip Amount", value=f"{num_format_coin(amount)}{TOKEN_NAME}", inline=True)
            embed.add_field(name="Num. Attendees", value="**0** members", inline=True)
            embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(duration_s)}")
            msg: discord.Message = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_PARTY)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            return await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            return await logchanbot(traceback.format_exc())

        if ctx.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.author.id)

        prev = []
        start_time = time.time()
        time_left = duration_s
        while time_left > 0:
            # Retrieve new reactions
            try:
                _msg: discord.Message = await ctx.fetch_message(msg.id)

                # Find reaction we're looking for
                r = discord.utils.get(_msg.reactions, emoji=EMOJI_PARTY)
                if r:
                    # Get list of Users that reacted & filter bots out
                    attend_list = [i for i in await r.users().flatten() if not i.bot and i != ctx.message.author]

                    # Check if there's been a change, otherwise delay & recheck
                    if set(attend_list) == set(prev) or len(attend_list) == 0:
                        time_left = duration_s - (time.time() - start_time)
                        if int(time_left) % 3 == 0:  # Update embed every 3s with current time left
                            time_left = 0 if time_left <= 0 else time_left
                            embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(int(time_left))}")
                            await _msg.edit(embed=embed)
                        if time_left <= 0:
                            break
                        await asyncio.sleep(1)
                        continue

                    attend_list_names = " | ".join([str(u.name) + "#" + str(u.discriminator) for u in attend_list])
                    if len(attend_list_names) >= 1000:
                        attend_list_names = attend_list_names[:1000]
                    try:
                        embed.set_field_at(index=add_index, name='Attendees', value=attend_list_names, inline=False)
                        embed.set_field_at(index=1 + add_index, name='Each Member Receives:', value=f"{num_format_coin(round(amount / len(attend_list), 4))}{TOKEN_NAME}",
                                           inline=True)
                        embed.set_field_at(index=2 + add_index, name="Num. Attendees", value=f"**{len(attend_list)}** members", inline=True)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(int(time_left))}")
                    await msg.edit(embed=embed)
                    prev = attend_list

                time_left = duration_s - (time.time() - start_time)

            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())

        try:
            _msg: discord.Message = await ctx.fetch_message(msg.id)
            # Find reaction we're looking for
            r = discord.utils.get(_msg.reactions, emoji=EMOJI_PARTY)
            if r:
                # Get list of Users that reacted & filter bots out
                tmp_attend_list = [i for i in await r.users().flatten() if not i.bot and i != ctx.message.author]
                if len(tmp_attend_list) > len(attend_list):
                    attend_list = tmp_attend_list
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        try:
            await msg.clear_reaction(EMOJI_PARTY)
        except discord.Forbidden or discord.HTTPException:
            pass

        if len(attend_list) == 0:
            embed = discord.Embed(title=f"Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"Already expired", timestamp=ts, color=0x00ff00)
            if comment and len(comment) > 0:
                embed.add_field(name="Comment", value=comment, inline=False)
            embed.set_footer(text=f"Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, and no one collected!")
            try:
                await msg.edit(embed=embed)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        attend_list_id = [u.id for u in attend_list if not u.bot and u != ctx.message.author]

        # re-check balance
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            if ctx.author.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.author.id)
            return
        # end of re-check balance

        # Multiple tip here
        notifyList = await store.sql_get_tipnotify()
        amountDiv = round(amount / len(attend_list_id), 4)
        tips = None

        try:
            tips = await store.sql_mv_erc_multiple(str(ctx.message.author.id), attend_list_id, amountDiv, TOKEN_NAME, "FREETIP", token_info['contract'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.author.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.author.id)

        if tips:
            tipAmount = num_format_coin(amount)
            ActualSpend_str = num_format_coin(amountDiv * len(attend_list_id))
            amountDiv_str = num_format_coin(amountDiv)
            numMsg = 0
            for each_id in attend_list_id:
                member = self.bot.get_user(id=each_id)
                # TODO: set limit here 100
                dm_user = bool(random.getrandbits(1)) if len(attend_list_id) > 100 else True
                if ctx.message.author.id != member.id and member.id != self.bot.user.id and str(member.id) not in notifyList:
                    try:
                        if dm_user:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You had collected a free tip of {amountDiv_str} '
                                                  f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                                                  f'{NOTIFICATION_OFF_CMD}')
                                numMsg += 1
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(member.id), "OFF")
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            # free tip shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Free tip of {tipAmount} '
                    f'{TOKEN_NAME} '
                    f'was sent spread to ({len(attend_list_id)}) members in server `{ctx.guild.name}`.\n'
                    f'Each member got: `{amountDiv_str}{TOKEN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{TOKEN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            # Edit embed
            try:
                embed = discord.Embed(title=f"Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"React {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
                if comment and len(comment) > 0:
                    embed.add_field(name="Comment", value=comment, inline=False)
                if len(attend_list_names) >= 1000: attend_list_names = attend_list_names[:1000]
                try:
                    if len(attend_list) > 0:
                        embed.add_field(name='Attendees', value=attend_list_names, inline=False)
                        embed.add_field(name='Individual Tip amount', value=f"{num_format_coin(round(amount / len(attend_list), 4))}{TOKEN_NAME}", inline=True)
                        embed.add_field(name="Num. Attendees", value=f"**{len(attend_list)}** members", inline=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                embed.set_footer(text=f"Completed! Collected by {len(attend_list_id)} member(s)")
                await msg.edit(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='gfreetip <amount> <duration> [comment]', aliases=['mfreetip', 'guildfreetip'], description="Spread guild free tip by reacting with emoji")
    @commands.has_permissions(manage_channels=True)
    async def gfreetip(self, ctx, amount: str, duration: utils.Duration, *, comment: str = None):

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        # Check if tx in progress
        if ctx.guild.id in self.bot.TX_IN_PROCESS:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} This guild has another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        amount = amount.replace(",", "")
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        try:
            duration_s = int((duration - datetime.utcnow()).total_seconds())
        except Exception as e:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration.')
            return

        print('get duration: {}'.format(duration_s))
        if duration_s == 0:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use time format: XXs')
            return
        elif duration_s < config.freetip.duration_min or duration_s > config.freetip.duration_max:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid duration. Please use between {str(config.freetip.duration_min)}s to {str(config.freetip.duration_max)}s.')
            return

        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        notifyList = await store.sql_get_tipnotify()
        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tip'])
        MaxTX = float(token_info['real_max_tip'])

        user_from = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.guild.id), TOKEN_NAME, w, 'DISCORD')
        userdata_balance = await store.sql_user_balance(str(ctx.guild.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a guild free tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            return

        attend_list = []
        ts = datetime.utcnow()
        embed = discord.Embed(title=f"Guild Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"React {EMOJI_PARTY} to collect", timestamp=ts, color=0x00ff00)
        add_index = 0
        try:
            if comment and len(comment) > 0:
                add_index = 1
                embed.add_field(name="Comment", value=comment, inline=True)
            embed.add_field(name="Attendees", value="*", inline=True)
            embed.add_field(name="Individual Tip Amount", value=f"{num_format_coin(amount)}{TOKEN_NAME}", inline=True)
            embed.add_field(name="Num. Attendees", value="**0** members", inline=True)
            embed.set_footer(
                text=f"Guild Free Tip by in {ctx.guild.name} / issued by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(duration_s)}")
            msg: discord.Message = await ctx.send(embed=embed)
            await msg.add_reaction(EMOJI_PARTY)
        except (discord.errors.NotFound, discord.errors.Forbidden) as e:
            await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        if ctx.guild.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.guild.id)

        prev = []
        start_time = time.time()
        time_left = duration_s
        while time_left > 0:
            # Retrieve new reactions
            try:
                _msg: discord.Message = await ctx.fetch_message(msg.id)

                # Find reaction we're looking for
                r = discord.utils.get(_msg.reactions, emoji=EMOJI_PARTY)
                if r:
                    # Get list of Users that reacted & filter bots out
                    attend_list = [i for i in await r.users().flatten() if not i.bot and i != ctx.message.author]

                    # Check if there's been a change, otherwise delay & recheck
                    if set(attend_list) == set(prev) or len(attend_list) == 0:
                        time_left = duration_s - (time.time() - start_time)
                        if int(time_left) % 3 == 0:  # Update embed every 3s with current time left
                            time_left = 0 if time_left <= 0 else time_left
                            embed.set_footer(text=f"Guild Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(int(time_left))}")
                            await _msg.edit(embed=embed)
                        if time_left <= 0:
                            break
                        await asyncio.sleep(1)
                        continue

                    attend_list_names = " | ".join([str(u.name) + "#" + str(u.discriminator) for u in attend_list])
                    if len(attend_list_names) >= 1000:
                        attend_list_names = attend_list_names[:1000]
                    try:
                        embed.set_field_at(index=add_index, name='Attendees', value=attend_list_names, inline=False)
                        embed.set_field_at(index=1 + add_index, name='Each Member Receives:', value=f"{num_format_coin(round(amount / len(attend_list), 4))}{TOKEN_NAME}",
                                           inline=True)
                        embed.set_field_at(index=2 + add_index, name="Num. Attendees", value=f"**{len(attend_list)}** members", inline=True)
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

                    embed.set_footer(text=f"Guild Free tip by {ctx.message.author.name}#{ctx.message.author.discriminator}, Time Left: {seconds_str(int(time_left))}")
                    await msg.edit(embed=embed)
                    prev = attend_list

                time_left = duration_s - (time.time() - start_time)

            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())

        try:
            _msg: discord.Message = await ctx.fetch_message(msg.id)
            # Find reaction we're looking for
            r = discord.utils.get(_msg.reactions, emoji=EMOJI_PARTY)
            if r:
                # Get list of Users that reacted & filter bots out
                tmp_attend_list = [i for i in await r.users().flatten() if not i.bot and i != ctx.message.author]
                if len(tmp_attend_list) > len(attend_list):
                    attend_list = tmp_attend_list
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        try:
            await msg.clear_reaction(EMOJI_PARTY)
        except discord.Forbidden or discord.HTTPException:
            pass

        if len(attend_list) == 0:
            embed = discord.Embed(title=f"Guild Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"Already expired", timestamp=ts, color=0x00ff00)
            if comment and len(comment) > 0:
                embed.add_field(name="Comment", value=comment, inline=False)
            embed.set_footer(text=f"Guild Free tip in {ctx.guild.name} / issued by {ctx.message.author.name}#{ctx.message.author.discriminator}, and no one collected!")
            try:
                await msg.edit(embed=embed)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            if ctx.guild.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.guild.id)
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        attend_list_id = [u.id for u in attend_list if not u.bot and u != ctx.message.author]

        # TODO, add one by one
        # re-check balance
        userdata_balance = await store.sql_user_balance(str(ctx.guild.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to do a free tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            if ctx.guild.id in self.bot.TX_IN_PROCESS:
                self.bot.TX_IN_PROCESS.remove(ctx.guild.id)
            return
        # end of re-check balance

        # Multiple tip here
        notifyList = await store.sql_get_tipnotify()
        amountDiv = round(amount / len(attend_list_id), 4)
        tips = None

        try:
            tips = await store.sql_mv_erc_multiple(str(ctx.guild.id), attend_list_id, amountDiv, TOKEN_NAME, "FREETIP", token_info['contract'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if ctx.guild.id in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(ctx.guild.id)

        if tips:
            tipAmount = num_format_coin(amount)
            ActualSpend_str = num_format_coin(amountDiv * len(attend_list_id))
            amountDiv_str = num_format_coin(amountDiv)
            numMsg = 0
            for each_id in attend_list_id:
                member = self.bot.get_user(id=each_id)
                # TODO: set limit here 100
                dm_user = bool(random.getrandbits(1)) if len(attend_list_id) > 100 else True
                if ctx.message.author.id != member.id and member.id != self.bot.user.id and str(member.id) not in notifyList:
                    try:
                        if dm_user:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You had collected a guild free tip of {amountDiv_str} '
                                                  f'{TOKEN_NAME} from {ctx.guild.name} / issued by {ctx.author.name}#{ctx.author.discriminator}\n'
                                                  f'{NOTIFICATION_OFF_CMD}')
                                numMsg += 1
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(member.id), "OFF")
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            # free tip shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Guild free tip of {tipAmount} '
                    f'{TOKEN_NAME} '
                    f'was sent spread to ({len(attend_list_id)}) members in server `{ctx.guild.name}`.\n'
                    f'Each member got: `{amountDiv_str}{TOKEN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{TOKEN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            # Edit embed
            try:
                embed = discord.Embed(title=f"Guild Free Tip appears {num_format_coin(amount)}{TOKEN_NAME}", description=f"React {EMOJI_PARTY} to collect", timestamp=ts,
                                      color=0x00ff00)
                if comment and len(comment) > 0:
                    embed.add_field(name="Comment", value=comment, inline=False)
                if len(attend_list_names) >= 1000: attend_list_names = attend_list_names[:1000]
                try:
                    if len(attend_list) > 0:
                        embed.add_field(name='Attendees', value=attend_list_names, inline=False)
                        embed.add_field(name='Individual Tip amount', value=f"{num_format_coin(round(amount / len(attend_list), 4))}{TOKEN_NAME}", inline=True)
                        embed.add_field(name="Num. Attendees", value=f"**{len(attend_list)}** members", inline=True)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                embed.set_footer(text=f"Completed! Collected by {len(attend_list_id)} member(s)")
                await msg.edit(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='tip <amount> <*args>', description='Tip other people')
    async def tip(self, ctx, amount: str, *args):
        amount = amount.replace(",", "")
        token_info = await store.get_token_info(TOKEN_NAME)
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        if len(ctx.message.mentions) == 0 and len(ctx.message.role_mentions) == 0:
            # Use how time.
            if len(args) >= 2:
                time_given = None
                if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                    # try if the param is 1111u
                    num_user = None
                    if args[0].upper() == "LAST":
                        num_user = args[1].lower()
                    elif args[1].upper() == "LAST":
                        num_user = args[2].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "")
                        num_user = num_user.replace("person", "")
                        num_user = num_user.replace("users", "")
                        num_user = num_user.replace("user", "")
                        num_user = num_user.replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use normal tip command. There are only few users.')
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    await ctx.message.add_reaction(EMOJI_INFORMATION)
                                    await ctx.send(f'{ctx.author.mention} Boss, you want to tip more than the number of people in this guild!?.'
                                                   ' Can be done :). Wait a while.... I am doing it. (**counting..**)')
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    return
                                message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, len(ctx.guild.members))
                                if ctx.message.author.id in message_talker:
                                    message_talker.remove(ctx.message.author.id)
                                if len(message_talker) == 0:
                                    await ctx.message.add_reaction(EMOJI_ERROR)
                                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                                elif len(message_talker) < len(ctx.guild.members) - 1:  # minus bot
                                    await ctx.send(
                                        f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                        f' and tip to those **{len(message_talker)}** users if they are still here.')
                                    # tip all user who are in the list
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                                if ctx.message.author.id in message_talker:
                                    message_talker.remove(ctx.message.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) == 0:
                                    await ctx.message.add_reaction(EMOJI_ERROR)
                                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                                elif len(message_talker) < num_user:
                                    try:
                                        await ctx.message.add_reaction(EMOJI_INFORMATION)
                                        await ctx.send(
                                            f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                            f' and tip to those **{len(message_talker)}** users if they are still here.')
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        return
                                    # tip all user who are in the list
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                else:
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                    return
                                return
                            else:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} What is this **{num_user}** number? Please give a number bigger than 0 :) ')
                                return
                        except ValueError:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST**.')
                        return
                    time_string = ctx.message.content.lower().split("last", 1)[1].strip()
                    time_second = None
                    try:
                        time_string = time_string.replace("years", "y")
                        time_string = time_string.replace("yrs", "y")
                        time_string = time_string.replace("yr", "y")
                        time_string = time_string.replace("year", "y")
                        time_string = time_string.replace("months", "mon")
                        time_string = time_string.replace("month", "mon")
                        time_string = time_string.replace("mons", "mon")
                        time_string = time_string.replace("weeks", "w")
                        time_string = time_string.replace("week", "w")

                        time_string = time_string.replace("day", "d")
                        time_string = time_string.replace("days", "d")

                        time_string = time_string.replace("hours", "h")
                        time_string = time_string.replace("hour", "h")
                        time_string = time_string.replace("hrs", "h")
                        time_string = time_string.replace("hr", "h")

                        time_string = time_string.replace("minutes", "mn")
                        time_string = time_string.replace("mns", "mn")
                        time_string = time_string.replace("mins", "mn")
                        time_string = time_string.replace("min", "mn")
                        time_string = time_string.replace("m", "mn")

                        mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60, 'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                        time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use this example: `.tip 10 last 12mn`')
                        return
                    try:
                        time_given = int(time_second)
                    except ValueError:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                        return
                    if time_given:
                        if time_given < 5 * 60 or time_given > 2 * 24 * 60 * 60:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please give try time inteval between 5minutes to 24hours.')
                            return
                        else:
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given, None)
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                                return
                            else:
                                try:
                                    async with ctx.typing():
                                        await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await self._tip_talker(ctx, amount, message_talker, False, TOKEN_NAME)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot(traceback.format_exc())
                                return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        elif len(ctx.message.mentions) == 1 and (self.bot.user in ctx.message.mentions):
            # Tip to TipBot
            member = ctx.message.mentions[0]
            print('TipBot is receiving tip from {} amount: {}{}'.format(ctx.message.author.name, amount, TOKEN_NAME))
        elif len(ctx.message.mentions) == 1 and (self.bot.user not in ctx.message.mentions):
            member = ctx.message.mentions[0]
            if ctx.message.author.id == member.id:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tip me if you want.')
                return
        elif len(ctx.message.role_mentions) >= 1:
            mention_roles = ctx.message.role_mentions
            if "@everyone" in mention_roles:
                mention_roles.remove("@everyone")
                if len(mention_roles) < 1:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not find user to tip to.')
                    return
            async with ctx.typing():
                await self._tip(ctx, amount, TOKEN_NAME)
                return
        elif len(ctx.message.mentions) > 1:
            async with ctx.typing():
                await self._tip(ctx, amount, TOKEN_NAME)
                return

        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME)

        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])
        if amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                                  f'{num_format_coin(MinTx)} '
                                  f'{TOKEN_NAME}.')
            return
        elif amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                                  f'{num_format_coin(MaxTX)} '
                                  f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                                  f'{num_format_coin(amount)} '
                                  f'{TOKEN_NAME} to {member.name}#{member.discriminator}.')
            return
        if ctx.message.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                tip = await store.sql_mv_erc_single(str(ctx.message.author.id), str(member.id), amount, TOKEN_NAME, "TIP", token_info['contract'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        notifyList = await store.sql_get_tipnotify()
        if tip:
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} '
                    f'was sent to {member.name}#{member.discriminator} in server `{ctx.guild.name}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            try:
                await ctx.send(
                    f'{EMOJI_MONEYFACE} {member.mention} got a tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                if self.bot.user.id != member.id and str(member.id) not in notifyList:
                    try:
                        await member.send(f'{EMOJI_MONEYFACE} You got a tip of {num_format_coin(amount)} '
                                          f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                                          f'{NOTIFICATION_OFF_CMD}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                        await store.sql_toggle_tipnotify(str(member.id), "OFF")
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='gtip <amount> <*args>', aliases=['guildtip', 'mtip'], description='Tip other people from guild balance')
    @commands.has_permissions(manage_channels=True)
    async def gtip(self, ctx, amount: str, *args):
        amount = amount.replace(",", "")
        token_info = await store.get_token_info(TOKEN_NAME)
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        if len(ctx.message.mentions) == 0 and len(ctx.message.role_mentions) == 0:
            # Use how time.
            if len(args) >= 2:
                time_given = None
                if args[0].upper() == "LAST" or args[1].upper() == "LAST":
                    # try if the param is 1111u
                    num_user = None
                    if args[0].upper() == "LAST":
                        num_user = args[1].lower()
                    elif args[1].upper() == "LAST":
                        num_user = args[2].lower()
                    if 'u' in num_user or 'user' in num_user or 'users' in num_user or 'person' in num_user or 'people' in num_user:
                        num_user = num_user.replace("people", "")
                        num_user = num_user.replace("person", "")
                        num_user = num_user.replace("users", "")
                        num_user = num_user.replace("user", "")
                        num_user = num_user.replace("u", "")
                        try:
                            num_user = int(num_user)
                            if len(ctx.guild.members) <= 2:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please use normal tip command. There are only few users.')
                                return
                            # Check if we really have that many user in the guild 20%
                            elif num_user >= len(ctx.guild.members):
                                try:
                                    await ctx.message.add_reaction(EMOJI_INFORMATION)
                                    await ctx.send(f'{ctx.author.mention} Boss, you want to tip more than the number of people in this guild!?.'
                                                   ' Can be done :). Wait a while.... I am doing it. (**counting..**)')
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    # No need to tip if failed to message
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    return
                                message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, len(ctx.guild.members))
                                if ctx.message.author.id in message_talker:
                                    message_talker.remove(ctx.message.author.id)
                                if len(message_talker) == 0:
                                    await ctx.message.add_reaction(EMOJI_ERROR)
                                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                                elif len(message_talker) < len(ctx.guild.members) - 1:  # minus bot
                                    await ctx.send(
                                        f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                        f' and tip to those **{len(message_talker)}** users if they are still here.')
                                    # tip all user who are in the list
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                return
                            elif num_user > 0:
                                message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), 0, num_user + 1)
                                if ctx.message.author.id in message_talker:
                                    message_talker.remove(ctx.message.author.id)
                                else:
                                    # remove the last one
                                    message_talker.pop()
                                if len(message_talker) == 0:
                                    await ctx.message.add_reaction(EMOJI_ERROR)
                                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is not sufficient user to count.')
                                elif len(message_talker) < num_user:
                                    try:
                                        await ctx.message.add_reaction(EMOJI_INFORMATION)
                                        await ctx.send(
                                            f'{EMOJI_INFORMATION} {ctx.author.mention} I could not find sufficient talkers up to **{num_user}**. I found only **{len(message_talker)}**'
                                            f' and tip to those **{len(message_talker)}** users if they are still here.')
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        # No need to tip if failed to message
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        return
                                    # tip all user who are in the list
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                else:
                                    try:
                                        async with ctx.typing():
                                            await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                        # zipped mouth but still need to do tip talker
                                        await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                        await logchanbot(traceback.format_exc())
                                    return
                                return
                            else:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} What is this **{num_user}** number? Please give a number bigger than 0 :) ')
                                return
                        except ValueError:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid param after **LAST**.')
                        return
                    time_string = ctx.message.content.lower().split("last", 1)[1].strip()
                    time_second = None
                    try:
                        time_string = time_string.replace("years", "y")
                        time_string = time_string.replace("yrs", "y")
                        time_string = time_string.replace("yr", "y")
                        time_string = time_string.replace("year", "y")
                        time_string = time_string.replace("months", "mon")
                        time_string = time_string.replace("month", "mon")
                        time_string = time_string.replace("mons", "mon")
                        time_string = time_string.replace("weeks", "w")
                        time_string = time_string.replace("week", "w")

                        time_string = time_string.replace("day", "d")
                        time_string = time_string.replace("days", "d")

                        time_string = time_string.replace("hours", "h")
                        time_string = time_string.replace("hour", "h")
                        time_string = time_string.replace("hrs", "h")
                        time_string = time_string.replace("hr", "h")

                        time_string = time_string.replace("minutes", "mn")
                        time_string = time_string.replace("mns", "mn")
                        time_string = time_string.replace("mins", "mn")
                        time_string = time_string.replace("min", "mn")
                        time_string = time_string.replace("m", "mn")

                        mult = {'y': 12 * 30 * 24 * 60 * 60, 'mon': 30 * 24 * 60 * 60, 'w': 7 * 24 * 60 * 60, 'd': 24 * 60 * 60, 'h': 60 * 60, 'mn': 60}
                        time_second = sum(int(num) * mult.get(val, 1) for num, val in re.findall('(\d+)(\w+)', time_string))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given. Please use this example: `.tip 1,000 last 5h 12mn`')
                        return
                    try:
                        time_given = int(time_second)
                    except ValueError:
                        await ctx.message.add_reaction(EMOJI_ERROR)
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid time given check.')
                        return
                    if time_given:
                        if time_given < 5 * 60 or time_given > 60 * 24 * 60 * 60:
                            await ctx.message.add_reaction(EMOJI_ERROR)
                            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please try time inteval between 5minutes to 24hours.')
                            return
                        else:
                            message_talker = await store.sql_get_messages(str(ctx.message.guild.id), str(ctx.message.channel.id), time_given, None)
                            if len(message_talker) == 0:
                                await ctx.message.add_reaction(EMOJI_ERROR)
                                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period.')
                                return
                            else:
                                try:
                                    async with ctx.typing():
                                        await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                                    # zipped mouth but still need to do tip talker
                                    await self._tip_talker(ctx, amount, message_talker, True, TOKEN_NAME)
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                                    await logchanbot(traceback.format_exc())
                                return
                else:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    try:
                        await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        try:
                            await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            return
                    return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                try:
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    try:
                        await ctx.message.author.send(f'{EMOJI_RED_NO} {ctx.author.mention} You need at least one person to tip to.')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        return
                return
        elif len(ctx.message.mentions) == 1 and (self.bot.user in ctx.message.mentions):
            # Tip to TipBot
            member = ctx.message.mentions[0]
            print('TipBot is receiving tip from {} amount: {}{}'.format(ctx.message.author.name, amount, TOKEN_NAME))
        elif len(ctx.message.mentions) == 1 and (self.bot.user not in ctx.message.mentions):
            member = ctx.message.mentions[0]
            if ctx.message.author.id == member.id:
                await ctx.message.add_reaction(EMOJI_ERROR)
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Tip me if you want.')
                return
        elif len(ctx.message.role_mentions) >= 1:
            mention_roles = ctx.message.role_mentions
            if "@everyone" in mention_roles:
                mention_roles.remove("@everyone")
                if len(mention_roles) < 1:
                    await ctx.message.add_reaction(EMOJI_ERROR)
                    await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Can not find user to tip to.')
                    return
            async with ctx.typing():
                await self._tip(ctx, amount, TOKEN_NAME, True)
                return
        elif len(ctx.message.mentions) > 1:
            async with ctx.typing():
                await self._tip(ctx, amount, TOKEN_NAME, True)
                return

        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']
        user_from = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.guild.id), TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME)
        userdata_balance = await store.sql_user_balance(str(ctx.guild.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])
        if amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient guild balance to send tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME} to {member.name}#{member.discriminator}.')
            return
        if ctx.guild.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.guild.id)
            try:
                tip = await store.sql_mv_erc_single(str(ctx.guild.id), str(member.id), amount, TOKEN_NAME, "TIP", token_info['contract'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.guild.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Your guild has another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        notifyList = await store.sql_get_tipnotify()

        if tip:
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Guild Tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} '
                    f'was sent to {member.name}#{member.discriminator} in server `{ctx.guild.name}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            try:
                await ctx.send(
                    f'{EMOJI_MONEYFACE} {member.mention} got a guild tip of {num_format_coin(amount)} '
                    f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator}')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                if self.bot.user.id != member.id and str(member.id) not in notifyList:
                    try:
                        await member.send(f'{EMOJI_MONEYFACE} You got a guild tip of {num_format_coin(amount)} '
                                          f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                                          f'{NOTIFICATION_OFF_CMD}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                        await store.sql_toggle_tipnotify(str(member.id), "OFF")
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='tipall <amount> <any/online>', description='Tip all online user')
    async def tipall(self, ctx, amount: str, user: str = 'ONLINE'):

        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = token_info['real_min_tip']
        MaxTX = token_info['real_max_tip']

        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} This command can not be in private.')
            return

        amount = amount.replace(",", "")
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])
        if amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send tip of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            return

        listMembers = [member for member in ctx.guild.members if member.status != discord.Status.offline and member.bot is False]
        if user.upper() == "ANY":
            listMembers = [member for member in ctx.guild.members]
        if len(listMembers) <= 1:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no number of users.')
            return

        notifyList = await store.sql_get_tipnotify()
        print("Number of tip-all in {}: {}".format(ctx.guild.name, len(listMembers)))
        memids = []  # list of member ID
        for member in listMembers:
            # print(member.name) # you'll just print out Member objects your way.
            if ctx.message.author.id != member.id:
                memids.append(str(member.id))
        amountDiv = round(amount / len(memids), 4)
        if (amount / len(memids)) < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME} for each member. You need at least {num_format_coin(len(memids) * MinTx)}{TOKEN_NAME}.')
            return
        if ctx.message.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                tips = await store.sql_mv_erc_multiple(str(ctx.message.author.id), memids, amountDiv, TOKEN_NAME, "TIPALL", token_info['contract'])
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if tips:
            tipAmount = num_format_coin(amount)
            ActualSpend_str = num_format_coin(amountDiv * len(memids))
            amountDiv_str = num_format_coin(amountDiv)
            numMsg = 0
            for member in listMembers:
                # TODO: set limit here 50
                dm_user = bool(random.getrandbits(1)) if len(listMembers) > 50 else True
                if ctx.message.author.id != member.id and member.id != self.bot.user.id and str(member.id) not in notifyList:
                    try:
                        if dm_user:
                            try:
                                await member.send(f'{EMOJI_MONEYFACE} You got a tip of {amountDiv_str} '
                                                  f'{TOKEN_NAME} from {ctx.message.author.name}#{ctx.message.author.discriminator} `{config.discord.prefixCmd}tipall` in server `{ctx.guild.name}`\n'
                                                  f'{NOTIFICATION_OFF_CMD}')
                                numMsg += 1
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(member.id), "OFF")
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} Tip of {tipAmount} '
                    f'{TOKEN_NAME} '
                    f'was sent spread to ({len(memids)}) members in server `{ctx.guild.name}`.\n'
                    f'Each member got: `{amountDiv_str}{TOKEN_NAME}`\n'
                    f'Actual spending: `{ActualSpend_str}{TOKEN_NAME}`')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    # Multiple tip
    async def _tip(self, ctx, amount, coin: str, if_guild: bool = False):
        TOKEN_NAME = coin.upper()
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.message.author.id)

        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tip'])
        MaxTX = float(token_info['real_max_tip'])

        user_from = await store.sql_get_userwallet(id_tipper, TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(id_tipper, TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(id_tipper, TOKEN_NAME)

        userdata_balance = await store.sql_user_balance(id_tipper, TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])
        if amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                                 f'{num_format_coin(MinTx)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        elif amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                                 f'{num_format_coin(MaxTX)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send {tip_type_text} of '
                                 f'{num_format_coin(amount)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        listMembers = []
        if ctx.message.role_mentions and len(ctx.message.role_mentions) >= 1:
            mention_roles = ctx.message.role_mentions
            if "@everyone" in mention_roles:
                mention_roles.remove("@everyone")
            if len(mention_roles) >= 1:
                for each_role in mention_roles:
                    role_listMember = [member for member in ctx.guild.members if member.bot is False and each_role in member.roles]
                    if len(role_listMember) >= 1:
                        for each_member in role_listMember:
                            if each_member not in listMembers:
                                listMembers.append(each_member)
        else:
            listMembers = ctx.message.mentions

        if len(listMembers) == 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} detect zero users.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        memids = []  # list of member ID
        for member in listMembers:
            if ctx.message.author.id != member.id and member in ctx.guild.members:
                memids.append(str(member.id))
        TotalAmount = amount * len(memids)

        if TotalAmount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transaction cannot be bigger than '
                                 f'{num_format_coin(MaxTX, TOKEN_NAME)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        elif actual_balance < TotalAmount:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You don\'t have sufficient balance. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        notifyList = await store.sql_get_tipnotify()
        try:
            tips = await store.sql_mv_erc_multiple(id_tipper, memids, amount, TOKEN_NAME, "TIPS", token_info['contract'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        if tips:
            tipAmount = num_format_coin(TotalAmount)
            amountDiv_str = num_format_coin(amount)
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {tipAmount} '
                    f'{TOKEN_NAME} '
                    f'was sent to ({len(memids)}) members in server `{ctx.guild.name}`.\n'
                    f'Each member got: `{amountDiv_str}{TOKEN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            for member in ctx.message.mentions:
                # print(member.name) # you'll just print out Member objects your way.
                if ctx.message.author.id != member.id and member.id != self.bot.user.id and str(member.id) not in notifyList:
                    try:
                        await member.send(f'{EMOJI_MONEYFACE} You got a {tip_type_text} of `{amountDiv_str}{TOKEN_NAME}` '
                                          f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}`\n'
                                          f'{NOTIFICATION_OFF_CMD}')
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        await store.sql_toggle_tipnotify(str(member.id), "OFF")
            await ctx.message.add_reaction(EMOJI_OK_HAND)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    # Multiple tip
    async def _tip_talker(self, ctx, amount, list_talker, if_guild: bool = False, coin: str = None):

        guild_or_tip = 'GUILDTIP' if if_guild else 'TIPS'
        guild_name = '**{}**'.format(ctx.guild.name) if if_guild else ''
        tip_type_text = 'guild tip' if if_guild else 'tip'
        id_tipper = str(ctx.guild.id) if if_guild else str(ctx.message.author.id)

        TOKEN_NAME = coin.upper()
        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tip'])
        MaxTX = float(token_info['real_max_tip'])

        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid amount.')
            return

        notifyList = await store.sql_get_tipnotify()

        user_from = await store.sql_get_userwallet(id_tipper, TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(id_tipper, TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(id_tipper, TOKEN_NAME)

        userdata_balance = await store.sql_user_balance(id_tipper, TOKEN_NAME)
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        if amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send {tip_type_text} of '
                           f'{num_format_coin(amount)} '
                           f'{TOKEN_NAME}.')
            return

        list_receivers = []
        for member_id in list_talker:
            try:
                member = self.bot.get_user(id=int(member_id))
                if member and member in ctx.guild.members and ctx.message.author.id != member.id:
                    user_to = await store.sql_get_userwallet(str(member_id), TOKEN_NAME)
                    if user_to is None:
                        w = await create_address_eth()
                        userregister = await store.sql_register_user(str(member_id), TOKEN_NAME, w, 'DISCORD')
                        user_to = await store.sql_get_userwallet(str(member_id), TOKEN_NAME)
                    try:
                        list_receivers.append(str(member_id))
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                        print('Failed creating wallet for tip talk for userid: {}'.format(member_id))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())

        # Check number of receivers.
        if len(list_receivers) > config.tipallMax:
            await ctx.message.add_reaction(EMOJI_ERROR)
            try:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} The number of receivers are too many.')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await ctx.message.author.send(f'{EMOJI_RED_NO} The number of receivers are too many in `{ctx.guild.name}`.')
            return
        # End of checking receivers numbers.

        TotalAmount = amount * len(list_receivers)

        if TotalAmount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be bigger than '
                           f'{num_format_coin(MaxTX)} '
                           f'{TOKEN_NAME}.')
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Total transactions cannot be smaller than '
                           f'{num_format_coin(MinTx)} '
                           f'{TOKEN_NAME}.')
            return
        elif TotalAmount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} {guild_name} Insufficient balance to send total {tip_type_text} of '
                           f'{num_format_coin(TotalAmount)} '
                           f'{TOKEN_NAME}.')
            return

        if len(list_receivers) < 1:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} There is no active talker in such period. Please increase more duration or tip directly!')
            return

        # add queue also tip
        if int(id_tipper) not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(int(id_tipper))
        else:
            await ctx.message.add_reaction(EMOJI_HOURGLASS_NOT_DONE)
            msg = await ctx.send(f'{EMOJI_ERROR} {ctx.author.mention} You have another tx in progress.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        tip = None
        try:
            tip = await store.sql_mv_erc_multiple(id_tipper, list_receivers, amount, TOKEN_NAME, "TIPS", token_info['contract'])
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

        # remove queue from tip
        if int(id_tipper) in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.remove(int(id_tipper))

        if tip:
            # tipper shall always get DM. Ignore notifyList
            try:
                await ctx.message.author.send(
                    f'{EMOJI_ARROW_RIGHTHOOK} {tip_type_text} of {num_format_coin(TotalAmount)} '
                    f'{TOKEN_NAME} '
                    f'was sent to ({len(list_receivers)}) members in server `{ctx.guild.name}` for active talking.\n'
                    f'Each member got: `{num_format_coin(amount)}{TOKEN_NAME}`\n')
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                await store.sql_toggle_tipnotify(str(ctx.message.author.id), "OFF")
            mention_list_name = ''
            for member_id in list_talker:
                # print(member.name) # you'll just print out Member objects your way.
                if ctx.message.author.id != int(member_id):
                    member = self.bot.get_user(id=int(member_id))
                    if member and member.bot is False and member in ctx.guild.members:
                        mention_list_name += '{}#{} '.format(member.name, member.discriminator)
                        if str(member_id) not in notifyList:
                            try:
                                await member.send(
                                    f'{EMOJI_MONEYFACE} You got a {tip_type_text} of `{num_format_coin(amount)} {TOKEN_NAME}` '
                                    f'from {ctx.message.author.name}#{ctx.message.author.discriminator} in server `{ctx.guild.name}` #{ctx.channel.name} for active talking.\n'
                                    f'{NOTIFICATION_OFF_CMD}')
                            except (discord.Forbidden, discord.errors.Forbidden) as e:
                                await store.sql_toggle_tipnotify(str(member.id), "OFF")
            await ctx.message.add_reaction(EMOJI_MONEYFACE)
            try:
                await ctx.send(
                    f'{discord.utils.escape_markdown(mention_list_name)}\n\n**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
                await ctx.message.add_reaction(EMOJI_SPEAK)
            except discord.errors.Forbidden:
                await ctx.message.add_reaction(EMOJI_SPEAK)
                await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
            except discord.errors.HTTPException:
                await ctx.message.add_reaction(EMOJI_SPEAK)
                await ctx.send(f'**({len(list_receivers)})** members got {tip_type_text} :) for active talking in `{ctx.guild.name}` {ctx.channel.mention} :)')
            return
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            return

    @freetip.error
    async def freetip_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                           f'You need to tell me **amount** and **duration** in seconds (with s).\nExample: {config.discord.prefixCmd}freetip **10 300s** or {config.discord.prefixCmd}freetip **10 300s Hello World**')
        return

    @gfreetip.error
    async def gfreetip_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                           f'You need to tell me **amount** and **duration** in seconds (with s) [With comments].\n'
                           f'Example: {config.discord.prefixCmd}gfreetip **10 300s** or {config.discord.prefixCmd}gfreetip **10 300s Hello World**\n')
        elif isinstance(ctx.channel, discord.DMChannel):
            await ctx.send('This command is not available in DM.')
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f'{ctx.author.mention} You do not have permission in this guild **{ctx.guild.name}** Please use normal {ctx.prefix}freetip command instead.')

    @tip.error
    async def tip_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing arguments. '
                           f'You need to tell me **amount** and who you want to tip to.\nExample: {config.discord.prefixCmd}tip **1,000** {self.bot.user.mention}')
        return

    @gtip.error
    async def gtip_error(self, ctx, error):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send('This command is not available in DM.')
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f'{ctx.author.mention} You do not have permission in this guild **{ctx.guild.name}** Please use normal {ctx.prefix}tip command instead.')


def setup(bot):
    bot.add_cog(Tips(bot))
