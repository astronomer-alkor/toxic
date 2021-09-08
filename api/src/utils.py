import logging
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable

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


@cached
async def get_last_funding() -> str:
    requested_tickers = ('BTCUSDT', 'ETHUSDT')
    async with ClientSession() as session:
        async with session.get('https://www.binance.com/fapi/v1/premiumIndex') as response:
            data = await response.json()
    funding = []
    for item in data:
        if (symbol := item['symbol']) in requested_tickers:
            funding_value = str(Decimal(item['lastFundingRate']) * 100).rstrip('0')
            item = f'{symbol} {funding_value}%'
            funding.append(item)
    return '\n'.join(funding)


def get_system_usage() -> str:
    return (
        f'Memory usage: {psutil.virtual_memory()[2]} %\n'
        f'CPU usage: {psutil.cpu_percent(4)}'
    )
