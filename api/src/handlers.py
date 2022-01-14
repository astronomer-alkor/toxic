import asyncio
import logging
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timedelta
from functools import partial

from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher
from aiogram.types import (
    CallbackQuery,
    Message,
    ReplyKeyboardRemove,
)
from aiogram.utils.exceptions import (
    BadRequest,
    MessageNotModified,
)

from .apps.funding import Funding
from .apps.order_book import book
from .config import ApiConfig
from .config import TelegramConfig
from .dynamo import Users, BollingerTickers
from .keyboards import (
    block_size_keyboard,
    get_settings_keyboard,
    get_bollinger_tickers_keyboard,
    get_bollinger_ticker_timeframes_keyboard,
    get_traiding_bb_start_keyboard,
)
from .utils import (
    delete_incoming,
    log_incoming,
    get_system_usage,
    disable_for_group,
    save_user,
)

# Commands
# trading - Trading signals
# funding - Current funding
# orders - Order Book Binance BTCUSDT Futures
# settings - Settings

bot = Bot(TelegramConfig().bot_token.get_secret_value(), loop=asyncio.get_event_loop())
dp = Dispatcher(bot, loop=bot.loop, storage=MemoryStorage())


@dp.message_handler(commands=['start'])
@log_incoming
@save_user
@disable_for_group
async def process_start_command(msg: Message):
    await msg.answer('Добро пожаловать в Toxic Traders бот', reply_markup=ReplyKeyboardRemove())


async def send_to_user(user_id, message, is_photo=False):
    logging.info('Funding image received. Sending')
    if is_photo:
        try:
            await bot.send_photo(user_id, deepcopy(message), reply_markup=ReplyKeyboardRemove())
        except BadRequest:
            await bot.send_document(user_id, ('funding.png', message), reply_markup=ReplyKeyboardRemove())
    else:
        await bot.send_message(user_id, message, reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['trading'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def trading(msg: Message):
    await msg.answer('Выберите, что вы хотите сделать', reply_markup=get_traiding_bb_start_keyboard())


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_start'))
async def trading_bb_main(call: CallbackQuery):
    with suppress(MessageNotModified):
        await call.message.edit_text(
            'Выберите, что вы хотите сделать',
            reply_markup=get_traiding_bb_start_keyboard()
        )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_all'))
async def trading_bb_all(call: CallbackQuery):
    tickers = await BollingerTickers().get_tickers()
    with suppress(MessageNotModified):
        await call.message.edit_text(
            'Выберите тикеры для подписки',
            reply_markup=get_bollinger_tickers_keyboard(tickers)
        )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_subscriptions'))
async def trading_bb_subscriptions(call: CallbackQuery):
    tickers = await BollingerTickers().get_tickers(user_id=call.from_user.id)
    if not tickers.items:
        await call.answer('У вас нет активных подписок!', show_alert=True)
        return None

    with suppress(MessageNotModified):
        await call.message.edit_text(
            'Тикеры, на которые вы подписаны',
            reply_markup=get_bollinger_tickers_keyboard(tickers, subscribed=True)
        )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_page'))
async def trading_bb_pagination(call: CallbackQuery):
    page_num, subscribed = call.data.split()[-2:]
    if int(subscribed):
        user_id = call.from_user.id
        text = 'Тикеры, на которые вы подписаны'
    else:
        user_id = None
        text = 'Выберите тикеры для подписки'
    tickers = await BollingerTickers().get_tickers(page_num=int(page_num), user_id=user_id)
    with suppress(MessageNotModified):
        await call.message.edit_text(
            text=text,
            reply_markup=get_bollinger_tickers_keyboard(tickers)
        )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_ticker'))
async def trading_bb_ticker(call: CallbackQuery):
    ticker, page, subscriptions = call.data.split()[-3:]
    timeframes = await BollingerTickers().get_ticker_timeframes(ticker)
    subscribed_tickers = await Users().get_bollinger_timeframes_by_ticker(call.from_user.id, ticker=ticker)
    with suppress(MessageNotModified):
        await call.message.edit_text(
            f'{ticker}. Выберите таймфрейм',
            reply_markup=get_bollinger_ticker_timeframes_keyboard(
                page,
                ticker,
                timeframes,
                subscribed_tickers,
                subscriptions=bool(int(subscriptions))
            )
        )
    await call.answer()


@dp.callback_query_handler(lambda call: call.data.startswith('trading_bb_tf'))
async def trading_bb_tf(call: CallbackQuery):
    ticker, timeframe, subscribed = call.data.split()[-3:]
    full_ticker = f'{ticker}@{timeframe}'
    neg_subscribed = int(not int(subscribed))
    if neg_subscribed:
        await Users().add_bollinger_ticker(call.from_user.id, full_ticker)
    else:
        await Users().delete_bollinger_ticker(call.from_user.id, full_ticker)
    for row in call.message.reply_markup.values['inline_keyboard']:
        for item in row:
            if item.callback_data.split()[-3:] == [ticker, timeframe, subscribed]:
                item.callback_data = f'trading_bb_tf {ticker} {timeframe} {neg_subscribed}'
                item.text = f'✅{timeframe}' if neg_subscribed else f'☑️{timeframe}'
                break
        else:
            continue
        break
    with suppress(MessageNotModified):
        await call.message.edit_text(
            f'{ticker}. Выберите таймфрейм',
            reply_markup=call.message.reply_markup
        )
    await call.answer()


@dp.message_handler(commands=['funding'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def funding(msg: Message):
    args = msg.get_args()
    funding_repo = Funding(callback=partial(send_to_user, msg.from_user.id))
    message = await funding_repo.get_last_funding(args=args)
    dp.loop.create_task(funding_repo.send_funding_image(args))
    await msg.answer(message, reply_markup=ReplyKeyboardRemove())


@dp.message_handler(commands=['orders'])
@log_incoming
@delete_incoming
@save_user
@disable_for_group
async def orders(msg: Message):
    block_size = Users().get_user(msg.from_user.id).get('block_size') or 100
    message = await book.draw(size=block_size)
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
        users = Users().get_all()
        active_users = [
            user for user in users
            if 'last_seen' in user and datetime.fromisoformat(user['last_seen']) > datetime.now() - timedelta(days=7)
        ]
        await msg.answer(
            '\n'.join((
                f'Count: {len(users)}',
                f'Subscribed: {len([user for user in users if user.get("subscribe")])}',
                f'Active: {len(active_users)}'
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
        except Exception as e:
            logging.warning(f'An error during send message to the user {recipient}: {e}')
            if ApiConfig().prod:
                user = users_repo.get_user(recipient)
                user['subscribe'] = False
                users_repo.put_user(**user)
