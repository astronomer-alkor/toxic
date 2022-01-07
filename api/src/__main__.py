from aiogram.utils import executor

from .apps import WhaleAlerts
from .apps.order_book import start_order_book
from .handlers import dp


def main() -> None:
    dp.loop.create_task(start_order_book())
    dp.loop.create_task(WhaleAlerts().monitor_whale_trades())
    executor.start_polling(dp)


if __name__ == '__main__':
    main()
