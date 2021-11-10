import asyncio
import logging
from contextlib import suppress

from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.types import (
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.exceptions import (
    BotBlocked,
    ChatNotFound,
    MessageNotModified,
)

from .apps.order_book import book
from .config import TelegramConfig
from .keyboards import block_size_keyboard, get_settings_keyboard
from .users import Users
from .utils import (
    delete_incoming,
    log_incoming,
    get_last_funding,
    get_system_usage,
    disable_for_group,
    save_user,
)

bot = Bot(TelegramConfig().bot_token.get_secret_value(), loop=asyncio.get_event_loop())
dp = Dispatcher(bot, loop=bot.loop, storage=MemoryStorage())


@dp.message_handler(commands=['start'])
@log_incoming
@save_user
@disable_for_group
async def process_start_command(msg: Message):
    await msg.answer('Добро пожаловать в Toxic Traders бот', reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['funding'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def funding(msg: Message):
    await msg.answer(await get_last_funding(msg.get_args()), reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['orders'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def orders(msg: Message):
    block_size = Users().get_user(msg.from_user.id).get('block_size') or 100
    message = await book.draw(block_size)
    if isinstance(message, str):
        await msg.answer(message, reply_markup=ReplyKeyboardRemove())
    else:
        await bot.send_photo(msg.chat.id, message, reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['settings'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def settings(msg: Message):
    await msg.answer('Настройки', reply_markup=get_settings_keyboard(msg.from_user.id))


@dp.callback_query_handler(text='unsubscribe')
@dp.callback_query_handler(text='subscribe')
async def subscription(call: CallbackQuery):
    users_repo = Users()
    user = users_repo.get_user(call.from_user.id)
    if call.data == 'subscribe':
        msg = 'Вы уже подписаны на рассылку'
        if not user.get('subscribe'):
            msg = 'Вы успешно подписались на рассылку'
            user['subscribe'] = True
            users_repo.put_user(**user)
    else:
        msg = 'Вы не подписаны на рассылку'
        if user.get('subscribe'):
            msg = 'Вы отписались от рассылки'
            user['subscribe'] = False
            users_repo.put_user(**user)
    with suppress(MessageNotModified):
        await call.message.edit_text('Настройки', reply_markup=get_settings_keyboard(call.from_user.id))
    await call.answer(msg, show_alert=True)


@dp.callback_query_handler(text='block_size')
async def block_size_settings(call: CallbackQuery):
    users_repo = Users()
    user = users_repo.get_user(call.from_user.id)

    block_size = user.get('block_size') or 100

    text = f'Текущий размер блока = <b>{block_size}</b>'

    with suppress(MessageNotModified):
        await call.message.edit_text(text, parse_mode='html', reply_markup=block_size_keyboard)
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('change_block_size'))
async def change_block_size(call: CallbackQuery):
    users_repo = Users()
    user = users_repo.get_user(call.from_user.id)

    block_size = int(call.data.split()[-1])
    user['block_size'] = block_size

    users_repo.put_user(**user)

    text = f'Текущий размер блока = <b>{block_size}</b>'

    with suppress(MessageNotModified):
        await call.message.edit_text(text, parse_mode='html', reply_markup=block_size_keyboard)
    await call.answer()


@dp.callback_query_handler(text='settings')
async def return_to_settings(call: CallbackQuery):
    with suppress(MessageNotModified):
        await call.message.edit_text('Настройки', reply_markup=get_settings_keyboard(call.from_user.id))
    await call.answer()


@dp.message_handler(commands=['system'])
@log_incoming
async def system_monitor(msg: Message):
    if await Users().is_admin(msg.from_user.id):
        await msg.answer(get_system_usage(), reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['users'])
@log_incoming
async def all_users(msg: Message):
    if await Users().is_admin(msg.from_user.id):
        users = Users().get_all_users()
        await msg.answer(
            '\n'.join((
                f'Count: {len(users)}',
                f'Subscribed: {len([user for user in users if user.get("subscribe")])}'
            )),
            reply_markup=ReplyKeyboardRemove()
        )


async def send_multiple(message: str, check_admin=False) -> None:
    users_repo = Users()
    for recipient in users_repo.get_recipients():
        try:
            kwargs = {}
            try:
                chat = await bot.get_chat(recipient)
                if not chat.type == 'channel':
                    kwargs = {'reply_markup': ReplyKeyboardRemove()}
            except Exception as e:
                logging.info(f'An error during get_chat operation: {e}')
            if not check_admin or (check_admin and await users_repo.is_admin(recipient)):
                logging.info(f'Sending alert to {recipient}')
                await bot.send_message(recipient, message, parse_mode='html', **kwargs)
        except (BotBlocked, ChatNotFound) as e:
            logging.warning(f'An error during send message to the user {recipient}: {e}')
            user = users_repo.get_user(recipient)
            user['subscribe'] = False
            users_repo.put_user(**user)
