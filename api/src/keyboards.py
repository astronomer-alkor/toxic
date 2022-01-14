from typing import List

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from .dynamo import Users, PaginationItems

block_size_keyboard = InlineKeyboardMarkup(row_width=1).add(
    InlineKeyboardButton(text='5', callback_data='change_block_size 5'),
    InlineKeyboardButton(text='10', callback_data='change_block_size 10'),
    InlineKeyboardButton(text='50', callback_data='change_block_size 50'),
    InlineKeyboardButton(text='100', callback_data='change_block_size 100'),
    InlineKeyboardButton(text='500', callback_data='change_block_size 500'),
    InlineKeyboardButton(text='1000', callback_data='change_block_size 1000'),
    InlineKeyboardButton(text='Назад', callback_data='settings')
)


def get_settings_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = Users().get_user(user_id)
    if user.get('subscribe'):
        text = 'Отписаться от рассылки'
        callback_data = 'unsubscribe'
    else:
        text = 'Подписаться на рассылку'
        callback_data = 'subscribe'

    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text=text, callback_data=callback_data),
        InlineKeyboardButton(text='Размер блоков стакана', callback_data='block_size')
    )


def get_bollinger_tickers_keyboard(items: PaginationItems, subscribed=False) -> InlineKeyboardMarkup:
    buttons = (
        InlineKeyboardButton(
            text=ticker,
            callback_data=f'trading_bb_ticker {ticker} {items.page_num} {int(subscribed)}'
        )
        for ticker in items.items
    )
    kb = InlineKeyboardMarkup(row_width=2).add(*buttons)
    prev_page = InlineKeyboardButton(text='⬅️', callback_data=f'trading_bb_page {items.page_num - 1} {int(subscribed)}')
    next_page = InlineKeyboardButton(text='➡️', callback_data=f'trading_bb_page {items.page_num + 1} {int(subscribed)}')
    if 0 < items.page_num < items.pages_count - 1:
        kb.add(prev_page, next_page)
    elif items.page_num < items.pages_count - 1:
        kb.add(next_page)
    elif items.page_num > 0:
        kb.add(prev_page)
    kb.add(InlineKeyboardButton(text='⬆️ назад', callback_data='trading_bb_start'))
    return kb


def get_bollinger_ticker_timeframes_keyboard(
        page: str,
        ticker: str,
        timeframes: List[str],
        subscribed_tickers: List[str],
        subscriptions=False
) -> InlineKeyboardMarkup:
    buttons = []
    for timeframe in timeframes:
        if timeframe in subscribed_tickers:
            subscribed_sign = '✅'
            subscribed = 1
        else:
            subscribed_sign = '☑️'
            subscribed = 0
        buttons.append(
            InlineKeyboardButton(
                text=f'{subscribed_sign}{timeframe}',
                callback_data=f'trading_bb_tf {ticker} {timeframe} {subscribed}'
            )
        )
    kb = InlineKeyboardMarkup(row_width=2).add(*buttons)
    kb.add(InlineKeyboardButton(text='⬆️ назад', callback_data=f'trading_bb_page {page} {int(subscriptions)}'))
    return kb


def get_traiding_bb_start_keyboard():
    return InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text='Все тикеры', callback_data=f'trading_bb_all'),
        InlineKeyboardButton(text='Мои тикеры', callback_data=f'trading_bb_subscriptions')
    )
