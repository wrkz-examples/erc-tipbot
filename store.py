from typing import List, Dict
from datetime import datetime
import time, json
import aiohttp, asyncio, aiomysql
from aiomysql.cursors import DictCursor

from config import config
import sys, traceback
import os.path

from web3 import Web3
from web3.middleware import geth_poa_middleware
from ethtoken.abi import EIP20_ABI

# For seed to key
from eth_account import Account
Account.enable_unaudited_hdwallet_features()

TOKEN_NAME = config.moon.ticker.upper()

pool = None
sys.path.append("..")

async def openConnection():
    global pool
    try:
        if pool is None:
            pool = await aiomysql.create_pool(host=config.mysql.host, port=3306, minsize=5, maxsize=10, 
                                                   user=config.mysql.user, password=config.mysql.password,
                                                   db=config.mysql.db, cursorclass=DictCursor, autocommit=True)
    except:
        print("ERROR: Unexpected error: Could not connect to MySql instance.")
        sys.exit()


async def get_token_info(coin: str):
    global pool
    TOKEN_NAME = coin.upper()
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_contract WHERE `token_name`=%s LIMIT 1 """
                await cur.execute(sql, (TOKEN_NAME))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def validate_address(address: str):
    try:
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider('http://'+config.moon.eth_default_rpc))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        return w3.toChecksumAddress(address)
    except ValueError:
        traceback.print_exc(file=sys.stdout)
    return None


async def http_wallet_getbalance(address: str, coin: str) -> Dict:
    TOKEN_NAME = coin.upper()
    timeout = 64
    if TOKEN_NAME == "ETH":
        data = '{"jsonrpc":"2.0","method":"eth_getBalance","params":["'+address+'", "latest"],"id":1}'
        url = 'http://' + config.moon.eth_default_rpc
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    else:
        token_info = await get_token_info(TOKEN_NAME)
        contract = token_info['contract']
        data = '{"jsonrpc":"2.0","method":"eth_call","params":[{"to": "'+contract+'", "data": "0x70a08231000000000000000000000000'+address[2:]+'"}, "latest"],"id":1}'
        url = 'http://' + token_info['http_address']
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                    if response.status == 200:
                        res_data = await response.read()
                        res_data = res_data.decode('utf-8')
                        await session.close()
                        decoded_data = json.loads(res_data)
                        if decoded_data and 'result' in decoded_data:
                            return int(decoded_data['result'], 16)
        except asyncio.TimeoutError:
            print('TIMEOUT: get balance {} for {}s'.format(TOKEN_NAME, timeout))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    return None


async def sql_register_user(userID, coin: str, w, user_server: str):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    contract = token_info['contract']
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_user WHERE `user_id`=%s AND `token_name` = %s AND `contract`=%s AND `user_server`=%s LIMIT 1 """
                await cur.execute(sql, (str(userID), TOKEN_NAME, contract, user_server))
                result = await cur.fetchone()
                if result is None:
                    try:
                        balance_address = {}
                        balance_address['balance_wallet_address'] = w['address']
                        token_info = await get_token_info(TOKEN_NAME)
                        sql = """ INSERT INTO erc_user (`token_name`, `contract`, `user_id`, `balance_wallet_address`, `address_ts`, 
                                  `token_decimal`, `seed`, `create_dump`, `private_key`, `public_key`, `xprivate_key`, `xpublic_key`, 
                                  `user_server`) 
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (TOKEN_NAME, contract, str(userID), w['address'], int(time.time()), 
                                          token_info['token_decimal'], w['seed'], str(w), w['private_key'], w['public_key'], 
                                          w['xprivate_key'], w['xpublic_key'], user_server))
                        await conn.commit()
                        return balance_address
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                else:
                    return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


# Updated
async def sql_get_userwallet(userID, coin: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    contract = token_info['contract']
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return

    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_user WHERE `user_id`=%s 
                          AND `token_name` = %s AND `contract`=%s AND `user_server` = %s LIMIT 1 """
                await cur.execute(sql, (str(userID), TOKEN_NAME, contract, user_server))
                result = await cur.fetchone()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_update_user(userID: str, user_wallet_address: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    user_server = user_server.upper()
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE erc_user SET `user_wallet_address`=%s WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s LIMIT 1 """               
                await cur.execute(sql, (user_wallet_address, userID, TOKEN_NAME, user_server))
                await conn.commit()
                return user_wallet_address  # return userwallet
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_user_balance(userID: str, coin: str, user_server: str = 'DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    user_server = user_server.upper()
    token_info = await get_token_info(TOKEN_NAME)
    confirmed_depth = token_info['deposit_confirm_depth']
    if user_server not in ['DISCORD', 'TELEGRAM']:
        return
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                # When sending tx out, (negative)
                sql = """ SELECT SUM(real_amount+real_external_fee) AS SendingOut FROM erc_external_tx 
                          WHERE `user_id`=%s AND `token_name` = %s AND `user_server`=%s """
                await cur.execute(sql, (userID, TOKEN_NAME, user_server))
                result = await cur.fetchone()
                if result:
                    SendingOut = result['SendingOut']
                else:
                    SendingOut = 0

                sql = """ SELECT SUM(real_amount) AS Expense FROM erc_mv_tx WHERE `from_userid`=%s AND `token_name` = %s """
                await cur.execute(sql, (userID, TOKEN_NAME))
                result = await cur.fetchone()
                if result:
                    Expense = result['Expense']
                else:
                    Expense = 0

                sql = """ SELECT SUM(real_amount) AS Income FROM erc_mv_tx WHERE `to_userid`=%s AND `token_name` = %s """
                await cur.execute(sql, (userID, TOKEN_NAME))
                result = await cur.fetchone()
                if result:
                    Income = result['Income']
                else:
                    Income = 0
                # in case deposit fee -real_deposit_fee
                sql = """ SELECT SUM(real_amount) AS Deposit FROM erc_move_deposit WHERE `user_id`=%s 
                          AND `token_name` = %s AND `confirmed_depth`> %s """
                await cur.execute(sql, (userID, TOKEN_NAME, confirmed_depth))
                result = await cur.fetchone()
                if result:
                    Deposit = result['Deposit']
                else:
                    Deposit = 0

            balance = {}
            balance['Adjust'] = 0
            balance['Expense'] = float(Expense) if Expense else 0
            balance['Income'] = float(Income) if Income else 0
            balance['SendingOut'] = float(SendingOut) if SendingOut else 0
            balance['Deposit'] = float(Deposit) if Deposit else 0
            balance['Adjust'] = balance['Income'] - balance['SendingOut'] - balance['Expense'] + balance['Deposit']
            return balance
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


# XMR Based
async def sql_mv_erc_single(user_from: str, to_user: str, amount: float, coin: str, tiptype: str, contract: str):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    if tiptype.upper() not in ["TIP", "DONATE", "FAUCET", "FREETIP", "FREETIPS"]:
        return False
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (TOKEN_NAME, contract, user_from, to_user, amount, token_info['token_decimal'], tiptype.upper(), int(time.time()),))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


async def sql_mv_erc_multiple(user_from: str, user_tos, amount_each: float, coin: str, tiptype: str, contract: str):
    # user_tos is array "account1", "account2", ....
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    token_decimal = token_info['token_decimal']
    TOKEN_NAME = coin.upper()
    if tiptype.upper() not in ["TIPS", "TIPALL", "FREETIP", "FREETIPS"]:
        return False
    values_str = []
    currentTs = int(time.time())
    for item in user_tos:
        values_str.append(f"('{TOKEN_NAME}', '{contract}', '{user_from}', '{item}', {amount_each}, {token_decimal}, '{tiptype.upper()}', {currentTs})\n")
    values_sql = "VALUES " + ",".join(values_str)
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_mv_tx (`token_name`, `contract`, `from_userid`, `to_userid`, `real_amount`, `token_decimal`, `type`, `date`) 
                          """+values_sql+""" """
                await cur.execute(sql,)
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False


# TODO: send tx
async def sql_external_erc_single(user_id: str, to_address: str, amount: float, coin: str, user_server: str='DISCORD'):
    global pool
    TOKEN_NAME = coin.upper()
    token_info = await get_token_info(TOKEN_NAME)
    user_server = user_server.upper()
    
    try:
        # HTTPProvider:
        w3 = Web3(Web3.HTTPProvider('http://'+config.moon.eth_default_rpc))

        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        unicorns = w3.eth.contract(address=w3.toChecksumAddress(token_info['contract']), abi=EIP20_ABI)
        nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))
                        
        unicorn_txn = unicorns.functions.transfer(
            w3.toChecksumAddress(to_address),
            int(amount * 10**token_info['token_decimal']) # amount to send
         ).buildTransaction({
            'from': w3.toChecksumAddress(config.eth.MainAddress),
            'gasPrice': w3.eth.gasPrice,
            'nonce': nonce
         })

        acct = Account.from_mnemonic(
            mnemonic=config.eth.MainAddress_seed)
        signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
        sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
        if signed_txn and sent_tx:
            # Add to SQL
            try:
                await openConnection()
                async with pool.acquire() as conn:
                    await conn.ping(reconnect=True)
                    async with conn.cursor() as cur:
                        sql = """ INSERT INTO erc_external_tx (`token_name`, `contract`, `user_id`, `real_amount`, 
                                  `real_external_fee`, `token_decimal`, `to_address`, `date`, `txn`, 
                                  `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                        await cur.execute(sql, (TOKEN_NAME, token_info['contract'], user_id, amount, token_info['real_withdraw_fee'], token_info['token_decimal'], 
                                                to_address, int(time.time()), sent_tx.hex(), user_server))
                        await conn.commit()
                        return sent_tx.hex()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)


async def sql_check_minimum_deposit():
    global pool
    token_info = await get_token_info(TOKEN_NAME)
    list_user_addresses = await sql_get_all_erc_user()
    # get withdraw gas balance
    gas_main_balance = await http_wallet_getbalance(config.eth.MainAddress, "ETH")
    
    # main balance has gas?
    main_balance_gas_sufficient = True
    if gas_main_balance and gas_main_balance / 10**18 >= config.eth.min_gas_tx:
        # OK can move
        #print('There is sufficient gas: {}ETH'.format(gas_main_balance / 10**18))
        pass
    else:
        main_balance_gas_sufficient = False
        #print('No sufficient gas to move balance. We have only {}ETH'.format(gas_main_balance / 10**18))
        pass
    if list_user_addresses and len(list_user_addresses) > 0:
        # OK check them one by one
        for each_address in list_user_addresses:
            deposited_balance = await http_wallet_getbalance(each_address['balance_wallet_address'], TOKEN_NAME)
            real_deposited_balance = deposited_balance / 10**token_info['token_decimal']
            if real_deposited_balance < config.moon.min_move_deposit:
                #print('address: {} has less than minimum deposit required: {}'.format(each_address['balance_wallet_address'], config.moon.min_move_deposit))
                pass
            else:
                #print('OK, let s move address: {} with balance {}'.format(each_address['balance_wallet_address'], real_deposited_balance))
                # Check if there is gas remaining to spend there
                gas_of_address = await http_wallet_getbalance(each_address['balance_wallet_address'], "ETH")
                if gas_of_address / 10**18 >= config.eth.min_gas_move:
                    print('Address {} still has gas {}ETH'.format(each_address['balance_wallet_address'], gas_of_address / 10**18))
                    # TODO: Let's move balance from there to withdraw address and save Tx
                    # HTTPProvider:
                    w3 = Web3(Web3.HTTPProvider('http://'+config.moon.eth_default_rpc))

                    # inject the poa compatibility middleware to the innermost layer
                    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

                    unicorns = w3.eth.contract(address=w3.toChecksumAddress(token_info['contract']), abi=EIP20_ABI)
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(each_address['balance_wallet_address']))
                    
                    unicorn_txn = unicorns.functions.transfer(
                         w3.toChecksumAddress(config.eth.MainAddress),
                         deposited_balance # amount to send
                     ).buildTransaction({
                         'from': w3.toChecksumAddress(each_address['balance_wallet_address']),
                         'gasPrice': w3.eth.gasPrice,
                         'nonce': nonce
                     })

                    acct = Account.from_mnemonic(
                        mnemonic=each_address['seed'])
                    signed_txn = w3.eth.account.signTransaction(unicorn_txn, private_key=acct.key)
                    sent_tx = w3.eth.sendRawTransaction(signed_txn.rawTransaction)
                    if signed_txn and sent_tx:
                        # Add to SQL
                        try:
                            inserted = await sql_move_deposit_for_spendable(TOKEN_NAME, token_info['contract'], each_address['user_id'], each_address['balance_wallet_address'], 
                                                                            config.eth.MainAddress, real_deposited_balance, token_info['real_deposit_fee'],  token_info['token_decimal'],
                                                                            sent_tx.hex())
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                elif gas_of_address / 10**18 < config.eth.min_gas_move and main_balance_gas_sufficient:
                    print('Address {} has not sufficient gas. Currently {}ETH'.format(each_address['balance_wallet_address'], gas_of_address / 10**18))
                    # HTTPProvider:
                    w3 = Web3(Web3.HTTPProvider('http://'+config.moon.eth_default_rpc))

                    # inject the poa compatibility middleware to the innermost layer
                    # w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    # TODO: Let's move gas from main to have sufficient to move
                    nonce = w3.eth.getTransactionCount(w3.toChecksumAddress(config.eth.MainAddress))
                    
                    print('nonce of main address: '+str(nonce))
                    # get gas price
                    gasPrice = w3.eth.gasPrice
                    print('gasPrice: '+str(gasPrice))
                    estimateGas = w3.eth.estimateGas({'to': w3.toChecksumAddress(each_address['balance_wallet_address']), 'from': w3.toChecksumAddress(config.eth.MainAddress), 'value':  int(config.eth.move_gas_amount * 10**18)})
                    print('estimateGas: '+str(estimateGas))
                    amount_gas_move = int(config.eth.move_gas_amount * 10**18) * config.eth.move_gas_factored_estimate
                    if amount_gas_move < config.eth.move_gas_amount * 10**18: amount_gas_move = int(config.eth.move_gas_amount * 10**18)
                    transaction = {
                            'from': w3.toChecksumAddress(config.eth.MainAddress),
                            'to': w3.toChecksumAddress(each_address['balance_wallet_address']),
                            'value': amount_gas_move,
                            'nonce': nonce,
                            'gasPrice': gasPrice,
                            'gas': estimateGas,
                            'chainId': 4
                        }
                    key = config.eth.MainAddress_key
                    signed = w3.eth.account.sign_transaction(transaction, key)
                    # send Transaction for gas:
                    send_gas_tx = w3.eth.sendRawTransaction(signed.rawTransaction)
                    if send_gas_tx:
                        print('send_gas_tx: '+ send_gas_tx.hex())
                elif gas_of_address / 10**18 < config.eth.min_gas_move and main_balance_gas_sufficient == False:
                    print('Main address has no sufficient balance to supply gas {}'.format(each_address['balance_wallet_address']))
                else:
                    print('Internal error for gas checking {}'.format(each_address['balance_wallet_address']))


async def sql_move_deposit_for_spendable(token_name: str, contract: str, user_id: str, balance_wallet_address: str, to_main_address: str, \
real_amount: float, real_deposit_fee: float, token_decimal: int, txn: str, user_server: str='DISCORD'):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ INSERT INTO erc_move_deposit (`token_name`, `contract`, `user_id`, `balance_wallet_address`, 
                          `to_main_address`, `real_amount`, `real_deposit_fee`, `token_decimal`, `txn`, `time_insert`, 
                          `user_server`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                await cur.execute(sql, (token_name, contract, user_id, balance_wallet_address, to_main_address, real_amount, 
                                        real_deposit_fee, token_decimal, txn, int(time.time()), user_server.upper()))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return False

async def sql_check_pending_move_deposit():
    global pool
    topBlock = await sql_get_block_number()
    if topBlock is None:
        print('Can not get top block.')
        return

    token_info = await get_token_info(TOKEN_NAME)
    list_pending = await sql_get_pending_move_deposit()
    if list_pending and len(list_pending) > 0:
        # Have pending, let's check
        for each_tx in list_pending:
            # Check tx from RPC
            check_tx = await sql_get_tx_info(each_tx['txn'])
            if check_tx:
                tx_block_number = int(check_tx['blockNumber'], 16)
                if topBlock - config.eth.confirmation > tx_block_number:
                    print('{} has more block confirmation!'.format(each_tx['txn']))
                    confirming_tx = await sql_update_confirming_move_tx(each_tx['txn'], tx_block_number, topBlock - tx_block_number)
                    # TODO update status from pending to confirm
                else:
                    print('{} has not sufficient block confirmation!'.format(each_tx['txn']))
    else:
        print('There is no pending Tx to confirm in moving')
        

async def sql_update_confirming_move_tx(tx: str, blockNumber: int, confirmed_depth: int):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE erc_move_deposit SET `status`=%s, `blockNumber`=%s, `confirmed_depth`=%s WHERE `txn`=%s """
                await cur.execute(sql, ('CONFIRMED', blockNumber, confirmed_depth, tx))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_tx_info(tx: str):
    timeout = 64
    data = '{"jsonrpc":"2.0", "method": "eth_getTransactionByHash", "params":["'+tx+'"], "id":1}'
    url = 'http://' + config.moon.eth_default_rpc
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return decoded_data['result']
    except asyncio.TimeoutError:
        print('TIMEOUT: get block number {}s'.format(timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_block_number():
    timeout = 64
    data = '{"jsonrpc":"2.0", "method":"eth_blockNumber", "params":[], "id":1}'
    url = 'http://' + config.moon.eth_default_rpc
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers={'Content-Type': 'application/json'}, json=json.loads(data), timeout=timeout) as response:
                if response.status == 200:
                    res_data = await response.read()
                    res_data = res_data.decode('utf-8')
                    await session.close()
                    decoded_data = json.loads(res_data)
                    if decoded_data and 'result' in decoded_data:
                        return int(decoded_data['result'], 16)
    except asyncio.TimeoutError:
        print('TIMEOUT: get block number {}s'.format(timeout))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_pending_move_deposit():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_move_deposit 
                          WHERE `status`=%s AND `token_name`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('PENDING', TOKEN_NAME, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_pending_notification_users():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT * FROM erc_move_deposit 
                          WHERE `status`=%s AND `token_name`=%s 
                          AND `notified_confirmation`=%s """
                await cur.execute(sql, ('CONFIRMED', TOKEN_NAME, 'NO'))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_updating_pending_move_deposit(notified_confirmation: bool, failed_notification: bool, txn: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ UPDATE erc_move_deposit 
                          SET `notified_confirmation`=%s, `failed_notification`=%s, `time_notified`=%s
                          WHERE `txn`=%s """
                await cur.execute(sql, ('YES' if notified_confirmation else 'NO', 'YES' if failed_notification else 'NO', int(time.time()), txn))
                await conn.commit()
                return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_get_all_erc_user():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT `user_id`, `token_name`, `contract`, `balance_wallet_address`, `seed` FROM erc_user 
                          WHERE `user_id`<>%s AND `token_name`=%s """
                await cur.execute(sql, ('WITHDRAW', TOKEN_NAME))
                result = await cur.fetchall()
                if result: return result
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_check_balance_address_in_users(address: str):
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                sql = """ SELECT `balance_wallet_address` FROM erc_user 
                          WHERE `token_name`=%s AND LOWER(`balance_wallet_address`)=LOWER(%s) LIMIT 1 """
                await cur.execute(sql, (TOKEN_NAME, address))
                result = await cur.fetchone()
                if result: return True
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
    return None


async def sql_toggle_tipnotify(user_id: str, onoff: str):
    # Bot will add user_id if it failed to DM
    global pool
    onoff = onoff.upper()
    if onoff == "OFF":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `bot_tipnotify_user` WHERE `user_id` = %s LIMIT 1 """
                    await cur.execute(sql, (user_id))
                    result = await cur.fetchone()
                    if result is None:
                        sql = """ INSERT INTO `bot_tipnotify_user` (`user_id`, `date`)
                                  VALUES (%s, %s) """    
                        await cur.execute(sql, (user_id, int(time.time())))
                        await conn.commit()
        except pymysql.err.Warning as e:
            await logchanbot(traceback.format_exc())
        except Exception as e:
            await logchanbot(traceback.format_exc())
    elif onoff == "ON":
        try:
            await openConnection()
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ DELETE FROM `bot_tipnotify_user` WHERE `user_id` = %s """
                    await cur.execute(sql, str(user_id))
                    await conn.commit()
        except Exception as e:
            await logchanbot(traceback.format_exc())


async def sql_get_tipnotify():
    global pool
    try:
        await openConnection()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                sql = """ SELECT `user_id`, `date` FROM bot_tipnotify_user """
                await cur.execute(sql,)
                result = await cur.fetchall()
                ignorelist = []
                for row in result:
                    ignorelist.append(row['user_id'])
                return ignorelist
    except Exception as e:
        await logchanbot(traceback.format_exc())