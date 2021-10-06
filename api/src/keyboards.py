from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from .users import Users

block_size_keyboard = InlineKeyboardMarkup(row_width=1).add(
    InlineKeyboardButton(text='100', callback_data='change_block_size 100'),
    InlineKeyboardButton(text='500', callback_data='change_block_size 500'),
    InlineKeyboardButton(text='1000', callback_data='change_block_size 1000'),
    InlineKeyboardButton(text='Назад', callback_data='settings')
)


def get_settings_keyboard(user_id: int):
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
