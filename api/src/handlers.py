import asyncio
from contextlib import suppress

from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.exceptions import (
    BotBlocked,
    ChatNotFound,
    MessageCantBeDeleted,
    MessageToDeleteNotFound,
)

from .apps.order_book import book
from .config import TelegramConfig
from .users import Users
from .utils import delete_incoming, log_incoming, get_last_funding, get_system_usage

bot = Bot(TelegramConfig().bot_token.get_secret_value(), loop=asyncio.get_event_loop())
dp = Dispatcher(bot, loop=bot.loop, storage=MemoryStorage())


@dp.message_handler(commands=['start'])
@log_incoming
async def process_start_command(msg: Message):
    if msg.chat.id > 0:
        await msg.answer('Добро пожаловать в Toxic Traders бот', reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['funding'])
@log_incoming
@delete_incoming
async def funding(msg: Message):
    await msg.answer(await get_last_funding(), reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['orders'])
@log_incoming
@delete_incoming
async def orders(msg: Message):
    message = await book.draw()
    if isinstance(message, str):
        await msg.answer(message, reply_markup=ReplyKeyboardRemove())
    else:
        await bot.send_photo(msg.chat.id, message, reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['settings'])
@log_incoming
@delete_incoming
async def settings(msg: Message):
    user = Users().get_user(msg.from_user.id)
    if user and user['subscribe']:
        text = 'Отписаться от рассылки'
        callback_data = 'unsubscribe'
    else:
        text = 'Подписаться на рассылку'
        callback_data = 'subscribe'
    keyboard = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton(text=text, callback_data=callback_data))
    await msg.answer('Настройки', reply_markup=keyboard)


@dp.callback_query_handler(text='unsubscribe')
@dp.callback_query_handler(text='subscribe')
async def subscription(call: CallbackQuery):
    users_repo = Users()
    user = users_repo.get_user(call.from_user.id)
    if call.data == 'subscribe':
        msg = 'Вы уже подписаны на рассылку'
        if not user or not user['subscribe']:
            user = user or {'id': call.from_user.id}
            msg = 'Вы успешно подписались на рассылку'
            user['subscribe'] = True
            users_repo.put_user(**user)
    else:
        msg = 'Вы не подписаны на рассылку'
        if user and user['subscribe']:
            msg = 'Вы отписались от рассылки'
            user['subscribe'] = False
            users_repo.put_user(**user)
    with suppress(MessageCantBeDeleted, MessageToDeleteNotFound):
        await call.message.delete()
    await call.answer(msg, show_alert=True)


@dp.message_handler(commands=['system'])
@log_incoming
async def system_monitor(msg: Message):
    if await Users().is_admin(msg.from_user.id):
        await msg.answer(get_system_usage(), reply_markup=ReplyKeyboardRemove())


async def send_multiple(message: str) -> None:
    users_repo = Users()
    invalid_users = []
    for recipient in users_repo.get_recipients():
        try:
            await bot.send_message(recipient, message, parse_mode='html', reply_markup=ReplyKeyboardRemove())
        except (BotBlocked, ChatNotFound):
            invalid_users.append(recipient)
    bot.loop.create_task(users_repo.delete_users(invalid_users))
