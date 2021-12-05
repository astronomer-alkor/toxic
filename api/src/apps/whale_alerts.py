import json
import logging
from datetime import datetime, timedelta

from src.handlers import send_multiple
from .base import WebSocketConnector

base_url = 'wss://fstream.binance.com/stream?streams=BTCUSDT@aggTrade'

requested_tickers = {
    'btcusdt': 100,
    'ethusdt': 1500
}

connection_data = {
    'method': 'SUBSCRIBE',
    'params': [f'{ticker}@aggTrade' for ticker in requested_tickers],
    'id': 1
}


class WhaleAlerts(WebSocketConnector):
    def __init__(self) -> None:
        super().__init__(connection_url=base_url, connection_data=connection_data)

    async def monitor_whale_trades(self) -> None:
        await self.initialize_connection()
        await self.subscribe()
        start = datetime.now()
        while True:
            trade = json.loads(await self.receive_data())['data']
            expected_amount = requested_tickers[trade['s'].lower()]
            if float(trade['q']) >= expected_amount:
                logging.info(f'Whale found. Sending signal')
                await send_multiple(
                    f'Binance futures. {trade["s"]}\n'
                    f'{"🟥 Продажа" if trade["m"] else "🟩 Покупка"} {trade["q"]} по цене {trade["p"]}'
                )
                logging.info('Done')
            if (now := datetime.now()) - timedelta(minutes=60) > start:
                start = now
                logging.info('Whale alerts works norminal')
