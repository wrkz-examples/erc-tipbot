import asyncio
# Eth wallet py
import functools
import json
import logging
import math
import os
# for randomString
import random
import string
import sys
import time
import traceback

import click
import discord
# redis
import redis
from discord.ext import commands
from discord.ext.commands import AutoShardedBot, when_mentioned_or
from discord_webhook import DiscordWebhook
from pywallet import wallet as ethwallet

import store
from config import config

redis_pool = None
redis_conn = None
redis_expired = 120

logging.basicConfig(level=logging.INFO)

TOKEN_NAME = config.moon.ticker.upper()
MOD_LIST = config.discord.mod_list.split(",")

EMOJI_ERROR = "\u274C"
EMOJI_OK_BOX = "\U0001F197"
EMOJI_RED_NO = "\u26D4"
EMOJI_OK_HAND = "\U0001F44C"
EMOJI_MONEYBAG = "\U0001F4B0"
EMOJI_QUESTEXCLAIM = "\u2049"
EMOJI_ARROW_RIGHTHOOK = "\u21AA"
EMOJI_ZIPPED_MOUTH = "\U0001F910"
EMOJI_MONEYFACE = "\U0001F911"
EMOJI_BELL_SLASH = "\U0001F515"
EMOJI_BELL = "\U0001F514"
EMOJI_HOURGLASS_NOT_DONE = "\u23F3"
EMOJI_PARTY = "\U0001F389"
EMOJI_SPEAK = "\U0001F4AC"
EMOJI_INFORMATION = "\u2139"
EMOJI_WARNING = "\u26A1"

NOTIFICATION_OFF_CMD = 'Type: `.notifytip off` to turn off this DM notification.'

bot_help_admin_shutdown = "Restart bot."
bot_help_admin_maintenance = "Bot to be in maintenance mode ON / OFF"

intents = discord.Intents.default()
intents.members = True
intents.presences = True


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=8)


def openRedis():
    global redis_pool, redis_conn
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


async def logchanbot(content: str):
    filterword = config.moon.logfilterword.split(",")
    for each in filterword:
        content = content.replace(each, config.moon.filteredwith)
    try:
        webhook = DiscordWebhook(url=config.moon.webhook_url, content=f'```{discord.utils.escape_markdown(content)}```')
        webhook.execute()
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# Steal from https://github.com/cree-py/RemixBot/blob/master/bot.py#L49
async def get_prefix(bot, message):
    """Gets the prefix for the guild"""
    pre_cmd = config.discord.prefixCmd
    if isinstance(message.channel, discord.DMChannel):
        extras = [pre_cmd, 'm!', 'moon!', '?', '.', '+', '!', '-']
        return when_mentioned_or(*extras)(bot, message)

    serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo is None:
        # Let's add some info if guild return None
        add_server_info = await store.sql_addinfo_by_server(str(message.guild.id), message.guild.name,
                                                            config.discord.prefixCmd)
        serverinfo = await store.sql_info_by_server(str(message.guild.id))
    if serverinfo and 'prefix' in serverinfo:
        pre_cmd = serverinfo['prefix']
    else:
        pre_cmd = config.discord.prefixCmd
    extras = [pre_cmd, 'm!', 'moon!']
    return when_mentioned_or(*extras)(bot, message)


bot = AutoShardedBot(command_prefix=get_prefix, owner_id=config.discord.ownerID, case_insensitive=True, intents=intents)
bot.remove_command('help')
bot.owner_id = config.discord.ownerID
bot.TX_IN_PROCESS = []


# Create ETH
def create_eth_wallet():
    seed = ethwallet.generate_mnemonic()
    w = ethwallet.create_wallet(network="ETH", seed=seed, children=1)
    return w


async def create_address_eth():
    wallet_eth = functools.partial(create_eth_wallet)
    create_wallet = await bot.loop.run_in_executor(None, wallet_eth)
    return create_wallet


@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    game = discord.Game(name="m.")
    await bot.change_presence(status=discord.Status.online, activity=game)


@bot.command(usage="load <cog>")
@commands.is_owner()
async def load(ctx, extension):
    """Load specified cog"""
    extension = extension.lower()
    bot.load_extension(f'cogs.{extension}')
    await ctx.send('{} has been loaded.'.format(extension.capitalize()))


@bot.command(usage="unload <cog>")
@commands.is_owner()
async def unload(ctx, extension):
    """Unload specified cog"""
    extension = extension.lower()
    bot.unload_extension(f'cogs.{extension}')
    await ctx.send('{} has been unloaded.'.format(extension.capitalize()))


@bot.command(usage="reload <cog/guilds/utils/all>")
@commands.is_owner()
async def reload(ctx, extension):
    """Reload specified cog"""
    extension = extension.lower()
    bot.reload_extension(f'cogs.{extension}')
    await ctx.send('{} has been reloaded.'.format(extension.capitalize()))


async def add_msg_redis(msg: str, delete_temp: bool = False):
    try:
        openRedis()
        key = "MOONTIPBOT:MSG"
        if redis_conn:
            if delete_temp:
                redis_conn.delete(key)
            else:
                redis_conn.lpush(key, msg)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        await logchanbot(traceback.format_exc())


async def store_message_list():
    while True:
        interval_msg_list = 15 # in second
        try:
            openRedis()
            key = "MOONTIPBOT:MSG"
            if redis_conn and redis_conn.llen(key) > 0 :
                temp_msg_list = []
                for each in redis_conn.lrange(key, 0, -1):
                    temp_msg_list.append(tuple(json.loads(each)))
                try:
                    num_add = await store.sql_add_messages(temp_msg_list)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                    await logchanbot(traceback.format_exc())
                if num_add and num_add > 0:
                    redis_conn.delete(key)
                else:
                    redis_conn.delete(key)
                    print(f"MOONTIPBOT:MSG: Failed delete {key}")
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())
        await asyncio.sleep(interval_msg_list)


# Let's run balance update by a separate process
async def update_balance():
    INTERVAL_EACH = 10
    while True:
        await asyncio.sleep(INTERVAL_EACH)
        start = time.time()
        try:
            await store.sql_check_minimum_deposit()
        except Exception as e:
            print(e)
        end = time.time()
        await asyncio.sleep(INTERVAL_EACH)


async def unlocked_move_pending():
    INTERVAL_EACH = 10
    while True:
        await asyncio.sleep(INTERVAL_EACH)
        start = time.time()
        try:
            await store.sql_check_pending_move_deposit()
        except Exception as e:
            print(e)
        end = time.time()
        await asyncio.sleep(INTERVAL_EACH)


async def notify_new_confirmed_spendable():
    INTERVAL_EACH = 10
    is_notify_failed = False
    while True:
        await asyncio.sleep(INTERVAL_EACH)
        start = time.time()
        try:
            notify_list = await store.sql_get_pending_notification_users()
            if notify_list and len(notify_list) > 0:
                for each_notify in notify_list:
                    member = bot.get_user(id=int(each_notify['user_id']))
                    if member:
                        msg = "You got a new deposit confirmed: ```" + "Amount: {}{}".format(each_notify['real_amount'], TOKEN_NAME) + "```"
                        try:
                            await member.send(msg)
                        except (discord.Forbidden, discord.errors.Forbidden) as e:
                            is_notify_failed = True
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                            await logchanbot(traceback.format_exc())
                        update_status = await store.sql_updating_pending_move_deposit(True, is_notify_failed, each_notify['txn'])
        except Exception as e:
            print(e)
        end = time.time()
        await asyncio.sleep(INTERVAL_EACH)


async def get_guild_prefix(ctx):
    if isinstance(ctx.channel, discord.DMChannel) == True: return "."
    serverinfo = await store.sql_info_by_server(str(ctx.guild.id))
    if serverinfo is None:
        return "."
    else:
        return serverinfo['prefix']


# function to return if input string is ascii
def is_ascii(s):
    return all(ord(c) < 128 for c in s)


def seconds_str(time: float):
    # day = time // (24 * 3600)
    # time = time % (24 * 3600)
    hour = time // 3600
    time %= 3600
    minutes = time // 60
    time %= 60
    seconds = time
    return "{:02d}:{:02d}:{:02d}".format(hour, minutes, seconds)


def num_format_coin(amount):
    return '{:.4f}'.format(amount)


def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper


@click.command()
def main():
    bot.loop.create_task(update_balance())
    bot.loop.create_task(unlocked_move_pending())
    bot.loop.create_task(notify_new_confirmed_spendable())
    bot.loop.create_task(store_message_list())

    for filename in os.listdir('./cogs/'):
        if filename.endswith('.py'):
            bot.load_extension(f'cogs.{filename[:-3]}')

    bot.run(config.discord.token, reconnect=True)

if __name__ == '__main__':
    main()