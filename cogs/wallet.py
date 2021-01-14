import sys
import traceback
from datetime import datetime

import discord
from discord.ext import commands

import store
import utils
from Bot import TOKEN_NAME, num_format_coin, EMOJI_OK_HAND, EMOJI_OK_BOX, logchanbot, EMOJI_ZIPPED_MOUTH, EMOJI_ERROR, EMOJI_RED_NO, EMOJI_ARROW_RIGHTHOOK, create_address_eth
from config import config


class Wallet(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(usage='balance', aliases=['bal'], description="Check your tipbot balance.")
    async def balance(self, ctx):
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        if wallet is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        if wallet:
            embed = discord.Embed(title=f'Balance for {ctx.message.author.name}#{ctx.message.author.discriminator}', description='`You need <Spendable> for withdraw/tip.`',
                                  timestamp=datetime.utcnow(), colour=7047495)
            embed.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
            deposit_balance = await store.http_wallet_getbalance(wallet['balance_wallet_address'], TOKEN_NAME)

            token_info = await store.get_token_info(TOKEN_NAME)
            real_deposit_balance = round(deposit_balance / 10 ** token_info['token_decimal'], 6)

            embed.add_field(name="Deposited", value="`{}{}`".format(num_format_coin(real_deposit_balance), TOKEN_NAME), inline=True)
            try:
                note = ''
                if ctx.message.author.id in self.bot.TX_IN_PROCESS:
                    note = '*You have some a tx in progress. Balance is being updated.*'
                userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
                balance_actual = num_format_coin(wallet['real_actual_balance'] + userdata_balance['Adjust'])
                embed.add_field(name="Spendable", value="`{}{}`".format(balance_actual, TOKEN_NAME), inline=True)
                total_balance = real_deposit_balance + wallet['real_actual_balance'] + userdata_balance['Adjust']
                embed.add_field(name="Total", value="`{}{}`".format(num_format_coin(total_balance), TOKEN_NAME), inline=False)
                embed.set_footer(text=f"Minimum {str(config.moon.min_move_deposit)}{config.moon.ticker} in deposit is required to (auto)transfer to **Spendable**.")
                try:
                    # Try DM first, if failed, send to public
                    msg = await ctx.author.send(embed=embed)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    traceback.print_exc(file=sys.stdout)
                    try:
                        msg = await ctx.send(embed=embed)
                        await msg.add_reaction(EMOJI_OK_BOX)
                        await ctx.message.add_reaction(EMOJI_OK_HAND)
                    except (discord.Forbidden, discord.errors.Forbidden) as e:
                        traceback.print_exc(file=sys.stdout)
                        await logchanbot(traceback.format_exc())
                        await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
                return
            except Exception as e:
                await ctx.message.add_reaction(EMOJI_ERROR)
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        return

    @commands.command(usage='register <wallet address>', aliases=['reg'], description="Register or change your deposit address for MoonTipBot.")
    async def register(self, ctx, wallet_address: str):
        if wallet_address.isalnum() == False:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                           f'`{wallet_address}`')
            return

        if wallet_address.upper().startswith("0X0000000000000000000000000000000"):
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                 f'`{wallet_address}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        user = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            user = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)

        existing_user = user
        # correct print(valid_address)
        valid_address = await store.validate_address(wallet_address)
        valid = False
        if valid_address and valid_address.upper() == wallet_address.upper():
            valid = True
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid address:\n'
                                 f'`{wallet_address}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        # if they want to register with tipjar address
        try:
            if user['balance_wallet_address'].upper() == wallet_address.upper():
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not register with your tipjar\'s address.\n'
                                     f'`{wallet_address}`')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                pass
        except Exception as e:
            await ctx.message.add_reaction(EMOJI_ERROR)
            print('Error during register user address:' + str(e))
            return

        # Check if register address in any of user balance address
        check_in_balance_users = await store.sql_check_balance_address_in_users(wallet_address)
        if check_in_balance_users:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You can not register with any of user\'s tipjar\'s address.\n'
                                 f'`{wallet_address}`')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        if 'user_wallet_address' in existing_user and existing_user['user_wallet_address']:
            prev_address = existing_user['user_wallet_address']
            if prev_address.upper() != wallet_address.upper():
                await store.sql_update_user(str(ctx.message.author.id), wallet_address, TOKEN_NAME)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(f'{ctx.author.mention} Your withdraw address has changed from:\n'
                                     f'`{prev_address}`\n to\n '
                                     f'`{wallet_address}`')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            else:
                await ctx.message.add_reaction(EMOJI_ERROR)
                msg = await ctx.send(f'{ctx.author.mention} Your previous and new address is the same.')
                await msg.add_reaction(EMOJI_OK_BOX)
                return
        else:
            try:
                await store.sql_update_user(str(ctx.message.author.id), wallet_address, TOKEN_NAME)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(f'{ctx.author.mention} You have registered a withdraw address.\n'
                                     f'You can use `{config.discord.prefixCmd}withdraw AMOUNT` anytime.')
                await msg.add_reaction(EMOJI_OK_BOX)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            return

    @commands.command(usage='deposit <plain/embed>', description="Get your wallet ticker's deposit address.")
    async def deposit(self, ctx, plain: str = 'embed'):
        wallet = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        if wallet is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        embed = discord.Embed(title=f'Deposit for {ctx.author.name}#{ctx.author.discriminator}', description='This bot\'s still under testing!', timestamp=datetime.utcnow(),
                              colour=7047495)
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

        if wallet['balance_wallet_address']:
            plain_msg = '{}#{} Your deposit address: ```{}```'.format(ctx.author.name, ctx.author.discriminator, wallet['balance_wallet_address'])
            embed.add_field(name="Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)
            if 'user_wallet_address' in wallet and wallet['user_wallet_address'] and isinstance(ctx.channel, discord.DMChannel) == True:
                embed.add_field(name="Withdraw Address", value="`{}`".format(wallet['user_wallet_address']), inline=False)
            elif 'user_wallet_address' in wallet and wallet['user_wallet_address'] and isinstance(ctx.channel, discord.DMChannel) == False:
                embed.add_field(name="Withdraw Address", value="`(Only in DM)`", inline=False)
            embed.set_footer(text=f"Use: {ctx.prefix}deposit plain (for plain text)")
            try:
                # Try DM first
                if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                    msg = await ctx.author.send(plain_msg)
                else:
                    msg = await ctx.author.send(embed=embed)
                await ctx.message.add_reaction(EMOJI_OK_HAND)
            except (discord.Forbidden, discord.errors.Forbidden) as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
                try:
                    if plain.lower() == 'plain' or plain.lower() == 'text':
                        msg = await ctx.author.send(plain_msg)
                    else:
                        msg = await ctx.send(embed=embed)
                    await msg.add_reaction(EMOJI_OK_BOX)
                    await ctx.message.add_reaction(EMOJI_OK_HAND)
                except (discord.Forbidden, discord.errors.Forbidden) as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                    await ctx.message.add_reaction(EMOJI_ZIPPED_MOUTH)
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error')
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='withdraw <amount>', description="Withdraw coins from your MoonTipBot balance.")
    async def withdraw(self, ctx, amount: str):
        amount = amount.replace(",", "")
        try:
            amount = float(amount)
        except ValueError:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Invalid given amount for command withdraw.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        token_info = await store.get_token_info(TOKEN_NAME)
        MinTx = float(token_info['real_min_tx'])
        MaxTX = float(token_info['real_max_tx'])

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)
        if user_from is None:
            w = await create_address_eth()
            user_from = await store.sql_register_user(str(ctx.message.author.id), TOKEN_NAME, w, 'DISCORD')
            user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME)

        CoinAddress = None
        if 'user_wallet_address' in user_from and user_from['user_wallet_address'] is None:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You do not have a withdrawal address, please use '
                                 f'`{config.discord.prefixCmd}register wallet_address` to register.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        else:
            CoinAddress = user_from['user_wallet_address']

        user_from = await store.sql_get_userwallet(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        userdata_balance = await store.sql_user_balance(str(ctx.message.author.id), TOKEN_NAME, 'DISCORD')
        actual_balance = float(user_from['real_actual_balance']) + float(userdata_balance['Adjust'])

        # If balance 0, no need to check anything
        if actual_balance <= 0:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Please check your **{TOKEN_NAME}** balance.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if amount > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                                 f'{num_format_coin(amount)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        NetFee = token_info['real_withdraw_fee']
        if amount + NetFee > actual_balance:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Insufficient balance to send out '
                                 f'{num_format_coin(amount)} '
                                 f'{TOKEN_NAME}. You need to leave at least network fee: {num_format_coin(NetFee)}{TOKEN_NAME}')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        elif amount < MinTx:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be smaller than '
                                 f'{num_format_coin(MinTx)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        elif amount > MaxTX:
            await ctx.message.add_reaction(EMOJI_ERROR)
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Transaction cannot be bigger than '
                                 f'{num_format_coin(MaxTX)} '
                                 f'{TOKEN_NAME}.')
            await msg.add_reaction(EMOJI_OK_BOX)
            return

        SendTx = None
        if ctx.message.author.id not in self.bot.TX_IN_PROCESS:
            self.bot.TX_IN_PROCESS.append(ctx.message.author.id)
            try:
                SendTx = await store.sql_external_erc_single(str(ctx.author.id), CoinAddress, amount, TOKEN_NAME, 'DISCORD')
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
            self.bot.TX_IN_PROCESS.remove(ctx.message.author.id)
        else:
            # reject and tell to wait
            msg = await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} You have another tx in process. Please wait it to finish. ')
            await msg.add_reaction(EMOJI_OK_BOX)
            return
        if SendTx:
            await ctx.message.add_reaction(EMOJI_OK_BOX)
            msg = await ctx.send(f'{EMOJI_ARROW_RIGHTHOOK} You have withdrawn {num_format_coin(amount)} '
                                 f'{TOKEN_NAME} to `{CoinAddress}`.\n'
                                 f'Transaction hash: `{SendTx}`')
            await msg.add_reaction(EMOJI_OK_BOX)
        else:
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='botbalance <member>', aliases=['botbal'], description="Get the bot's balance")
    async def botbalance(self, ctx, member: utils.MemberLookupConverter):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command can not be in DM.')
            return
        if member.bot == False:
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Command is only for bot!!')
            return

        wallet = await store.sql_get_userwallet(str(member.id), TOKEN_NAME, 'DISCORD')
        if wallet is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(member.id), TOKEN_NAME, w, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(member.id), TOKEN_NAME, 'DISCORD')

        if wallet:
            embed = discord.Embed(title=f'Bot balance for {member.name}#{member.discriminator}',
                                  description='`This is bot\'s tipjar address. Do not deposit here unless you want to deposit to this bot`', timestamp=datetime.utcnow(),
                                  colour=7047495)
            embed.add_field(name="Bot Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)
            embed.set_author(name=member.name, icon_url=member.avatar_url)
            deposit_balance = await store.http_wallet_getbalance(wallet['balance_wallet_address'], TOKEN_NAME)

            token_info = await store.get_token_info(TOKEN_NAME)
            real_deposit_balance = deposit_balance / 10 ** token_info['token_decimal']

            embed.add_field(name="Deposited", value="`{}{}`".format(num_format_coin(real_deposit_balance), TOKEN_NAME), inline=True)
            try:
                note = ''
                if ctx.guild.id in self.bot.TX_IN_PROCESS:
                    note = '*There are some a tx in progress. Balance is being updated.*'
                userdata_balance = await store.sql_user_balance(str(member.id), TOKEN_NAME, 'DISCORD')
                balance_actual = num_format_coin(float(wallet['real_actual_balance']) + float(userdata_balance['Adjust']))
                embed.add_field(name="Spendable", value="`{}{}`".format(balance_actual, TOKEN_NAME), inline=True)
                total_balance = real_deposit_balance + float(wallet['real_actual_balance']) + float(userdata_balance['Adjust'])
                embed.add_field(name="Total", value="`{}{}`".format(num_format_coin(total_balance), TOKEN_NAME), inline=False)
                embed.set_footer(text=f"Minimum {str(config.moon.min_move_deposit)}{config.moon.ticker} in deposit is required to (auto)transfer to **Spendable**.")
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            except Exception as e:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error')
                await ctx.message.add_reaction(EMOJI_ERROR)
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error')
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @commands.command(usage='mbalance', aliases=['mbal', 'gbal'], description='Balance and deposit to guild')
    async def mbalance(self, ctx):
        if isinstance(ctx.channel, discord.DMChannel) == True:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} This command can not be in DM.')
            return

        wallet = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME, 'DISCORD')
        if wallet is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.guild.id), TOKEN_NAME, w, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME, 'DISCORD')
        embed = discord.Embed(title=f'Deposit for Guild {ctx.guild.name} / {ctx.guild.id}',
                              description='`This is guild\'s tipjar address. Do not deposit here unless you want to deposit to this guild`', timestamp=datetime.utcnow(),
                              colour=7047495)

        if wallet:
            embed = discord.Embed(title=f'Guild balance for {ctx.guild.name} / {str(ctx.guild.id)}', description='`Guild balance`', timestamp=datetime.utcnow(), colour=7047495)
            embed.add_field(name="Guild Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)
            embed.set_author(name=ctx.message.author.name, icon_url=ctx.message.author.avatar_url)
            deposit_balance = await store.http_wallet_getbalance(wallet['balance_wallet_address'], TOKEN_NAME)

            token_info = await store.get_token_info(TOKEN_NAME)
            real_deposit_balance = round(deposit_balance / 10 ** token_info['token_decimal'], 6)

            embed.add_field(name="Deposited", value="`{}{}`".format(num_format_coin(real_deposit_balance), TOKEN_NAME), inline=True)
            try:
                note = ''
                if ctx.guild.id in self.bot.TX_IN_PROCESS:
                    note = '*There are some a tx in progress. Balance is being updated.*'
                userdata_balance = await store.sql_user_balance(str(ctx.guild.id), TOKEN_NAME, 'DISCORD')
                balance_actual = num_format_coin(wallet['real_actual_balance'] + userdata_balance['Adjust'])
                embed.add_field(name="Spendable", value="`{}{}`".format(balance_actual, TOKEN_NAME), inline=True)
                total_balance = real_deposit_balance + wallet['real_actual_balance'] + userdata_balance['Adjust']
                embed.add_field(name="Total", value="`{}{}`".format(num_format_coin(total_balance), TOKEN_NAME), inline=False)
                embed.set_footer(text=f"Minimum {str(config.moon.min_move_deposit)}{config.moon.ticker} in deposit is required to (auto)transfer to **Spendable**.")
                await ctx.message.add_reaction(EMOJI_OK_HAND)
                msg = await ctx.send(embed=embed)
                await msg.add_reaction(EMOJI_OK_BOX)
                return
            except Exception as e:
                await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error')
                await ctx.message.add_reaction(EMOJI_ERROR)
                traceback.print_exc(file=sys.stdout)
                await logchanbot(traceback.format_exc())
        return

    @commands.command(usage='mdeposit <plain/embed>', description='Deposit to Guild')
    async def mdeposit(self, ctx, plain: str = 'embed'):
        if isinstance(ctx.channel, discord.DMChannel):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{ctx.author.mention} This command can not be in private.')
            return

        wallet = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME, 'DISCORD')
        if wallet is None:
            w = await create_address_eth()
            userregister = await store.sql_register_user(str(ctx.guild.id), TOKEN_NAME, w, 'DISCORD')
            wallet = await store.sql_get_userwallet(str(ctx.guild.id), TOKEN_NAME, 'DISCORD')
        embed = discord.Embed(title=f'Deposit for Guild {ctx.guild.name} / {ctx.guild.id}', description='This bot\'s still under testing!', timestamp=datetime.utcnow(),
                              colour=7047495)
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        if wallet['balance_wallet_address']:
            plain_msg = 'Guild {}/{}\'s deposit address: ```{}```'.format(ctx.guild.name, ctx.guild.id, wallet['balance_wallet_address'])
            embed.add_field(name="Guild Deposit Address", value="`{}`".format(wallet['balance_wallet_address']), inline=False)
            embed.set_footer(text=f"Use: {ctx.prefix}deposit plain (for plain text)")
            if plain and plain.lower() == 'plain' or plain.lower() == 'text':
                msg = await ctx.send(plain_msg)
            else:
                msg = await ctx.send(embed=embed)
            await ctx.message.add_reaction(EMOJI_OK_HAND)
            await msg.add_reaction(EMOJI_OK_BOX)
        else:
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Internal Error')
            await ctx.message.add_reaction(EMOJI_ERROR)
        return

    @register.error
    async def register_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing your wallet address. '
                           f'You need to have a supported coin **address** after `register` command. Example: {config.discord.prefixCmd}register coin_address')
        return

    @withdraw.error
    async def withdraw_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.message.add_reaction(EMOJI_ERROR)
            await ctx.send(f'{EMOJI_RED_NO} {ctx.author.mention} Missing amount. '
                           f'You need to tell me **AMOUNT**.\nExample: {config.discord.prefixCmd}withdraw **1,000**')
        return


def setup(bot):
    bot.add_cog(Wallet(bot))
