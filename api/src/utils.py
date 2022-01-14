import asyncio
import logging
import pickle
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Callable

import psutil
from aiogram.types import Message
from aiogram.utils.exceptions import (
    MessageCantBeDeleted,
    MessageToDeleteNotFound,
    BotKicked,
)

from .dynamo import Users


def cached(seconds=5, only_kwargs=False):
    def outer(func: Callable):
        cache = {}

        def clear_expired():
            for key in list(cache.keys()):
                if value := cache.get(key):
                    _, latest_call_time = value
                    if datetime.now() - latest_call_time > timedelta(seconds):
                        cache.pop(key, None)

        async def wrapper(*args, **kwargs) -> Any:
            clear_expired()
            now = datetime.now()

            params = sorted(kwargs.items()) if only_kwargs else (args, sorted(kwargs.items()))
            key = pickle.dumps(params)

            if value := cache.get(key):
                latest_result, latest_call_time = value
                if now - latest_call_time < timedelta(seconds=seconds):
                    return deepcopy(latest_result)

            latest_result = await func(*args, **kwargs)
            cache[key] = latest_result, now
            return deepcopy(latest_result)

        return wrapper

    return outer


def delete_incoming(func: Callable):
    async def wrapper(message: Message, **_):
        result = await func(message)
        with suppress(MessageCantBeDeleted, MessageToDeleteNotFound, BotKicked):
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
        try:
            reply = await message.reply('Это функция недоступна для группы. Пишите в бота напрямую')
            await asyncio.sleep(5)
            await message.delete()
            await reply.delete()
        except BotKicked:
            logging.warning(f'Bot was kicked for {message.chat.full_name} with ID {message.chat.id}')
        except Exception as e:
            logging.warning(e)

    return wrapper


def save_user(func: Callable):
    async def wrapper(message: Message, **_):
        users_repo = Users()
        user = users_repo.get_user(message.from_user.id)
        last_seen = datetime.now().replace(microsecond=0).isoformat()
        if not user:
            users_repo.put_user(
                id=message.from_user.id,
                last_seen=last_seen,
                name=' '.join((
                    message.from_user.first_name or '',
                    message.from_user.last_name or '',
                    message.from_user.username or ''
                ))
            )
        else:
            users_repo.put_user(**{**user, 'last_seen': last_seen})

        return await func(message)

    return wrapper


def get_system_usage() -> str:
    return (
        f'Memory usage: {psutil.virtual_memory()[2]} %\n'
        f'CPU usage: {psutil.cpu_percent(4)}'
    )
