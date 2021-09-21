import asyncio
import logging
import pickle
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, List

import psutil
from aiogram.types import Message
from aiogram.utils.exceptions import (
    MessageCantBeDeleted,
    MessageToDeleteNotFound
)
from aiohttp import ClientSession


def cached(func: Callable):
    latest_call_time = datetime.now()
    latest_result = None

    async def wrapper(*args, **kwargs) -> Any:
        nonlocal latest_call_time
        nonlocal latest_result

        now = datetime.now()
        if latest_result and now - latest_call_time < timedelta(seconds=5):
            return deepcopy(latest_result)

        latest_call_time = now
        latest_result = await func(*args, **kwargs)
        return deepcopy(latest_result)

    return wrapper


def cached_with_result(func: Callable):
    cache = {}

    async def wrapper(*args, **kwargs) -> Any:
        now = datetime.now()

        key = pickle.dumps((args, sorted(kwargs.items())))

        if value := cache.get(key):
            latest_result, latest_call_time = value
            if now - latest_call_time < timedelta(seconds=5):
                return deepcopy(latest_result)

        latest_result = await func(*args, **kwargs)
        cache[key] = latest_result, now
        return deepcopy(latest_result)

    return wrapper


def delete_incoming(func: Callable):
    async def wrapper(message: Message, **_):
        result = await func(message)
        with suppress(MessageCantBeDeleted, MessageToDeleteNotFound):
            await message.delete()
        return result

    return wrapper


def log_incoming(func: Callable):
    async def wrapper(message: Message, **_):
        logging.info(
            f'Message: {message.text}\n'
            f'User ID: {message.from_user.id}\n'
            f'User: {message.from_user.first_name} {message.from_user.last_name}\n'
            f'Username: {message.from_user.username}'
        )
        return await func(message)
    return wrapper


def disable_for_group(func: Callable):
    async def wrapper(message: Message, **_):
        if message.chat.id > 0:
            return await func(message)
        reply = await message.reply('Это функция недоступна для группы. Пишите в бота напрямую')
        await asyncio.sleep(5)
        await message.delete()
        await reply.delete()
    return wrapper


@cached_with_result
async def get_last_funding(requested_tickers: List[str]) -> str:
    for index, item in enumerate(requested_tickers):
        item = item.upper()
        if not item.endswith('USDT') and not item.endswith('BUSD'):
            item = f'{item}USDT'
        requested_tickers[index] = item
    requested_tickers = requested_tickers or ('BTCUSDT', 'ETHUSDT')
    async with ClientSession() as session:
        async with session.get('https://www.binance.com/fapi/v1/premiumIndex') as response:
            data = await response.json()
    funding = []
    for item in data:
        if (symbol := item['symbol']) in requested_tickers:
            funding_value = str(Decimal(item['lastFundingRate']) * 100).rstrip('0') or '0'
            item = f'{symbol} {funding_value}%'
            funding.append(item)
    if funding:
        return '\n'.join(funding)
    return 'Неверные названия тикеров'


def get_system_usage() -> str:
    return (
        f'Memory usage: {psutil.virtual_memory()[2]} %\n'
        f'CPU usage: {psutil.cpu_percent(4)}'
    )
