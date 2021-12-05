import asyncio
import logging

from aiogram.dispatcher.webhook import get_new_configured_app
from aiohttp import web

from .apps import WhaleAlerts
from .apps.order_book import start_order_book
from .config import ApiConfig, TelegramConfig
from .endpoints import routes
from .handlers import bot, dp


async def on_startup(*_) -> None:
    dp.loop.create_task(start_order_book())
    dp.loop.create_task(WhaleAlerts().monitor_whale_trades())

    webhook = await bot.get_webhook_info()
    webhook_url = TelegramConfig().webhook_url
    if webhook.url != webhook_url:
        if not webhook.url:
            await bot.delete_webhook()
        logging.info('Sleeping 1 minute')
        await asyncio.sleep(60)
        logging.info('Setting the webhook')
        await bot.set_webhook(webhook_url)


async def on_shutdown(*_) -> None:
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()


def main() -> None:
    app = get_new_configured_app(dispatcher=dp, path=TelegramConfig().webhook_url_path.get_secret_value())
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    logging.info('Starting server')
    web.run_app(app, host=ApiConfig().host, port=ApiConfig().port)


if __name__ == '__main__':
    main()
