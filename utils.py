import asyncio
import random
import string

async def generate_btc_address_async():
    return await asyncio.get_event_loop().run_in_executor(None, generate_btc_address)

async def generate_eth_address_async():
    return await asyncio.get_event_loop().run_in_executor(None, generate_eth_address)

async def generate_trc20_address_async():
    return await asyncio.get_event_loop().run_in_executor(None, generate_trc20_address)

async def generate_transaction_hash_async():
    return await asyncio.get_event_loop().run_in_executor(None, generate_transaction_hash)

def generate_btc_address():
    prefix = '1' if random.random() > 0.5 else 'bc1'
    length = 34 if prefix == '1' else 42
    chars = string.ascii_letters + string.digits
    return prefix + ''.join(random.choice(chars) for _ in range(length - len(prefix)))

def generate_eth_address():
    chars = '0123456789abcdef'
    return '0x' + ''.join(random.choice(chars) for _ in range(40))

def generate_trc20_address():
    chars = string.ascii_letters + string.digits
    return 'T' + ''.join(random.choice(chars) for _ in range(33))

def generate_transaction_hash():
    chars = '0123456789abcdef'
    return '0x' + ''.join(random.choice(chars) for _ in range(64))