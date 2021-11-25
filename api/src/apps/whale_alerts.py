import json
import logging
from datetime import datetime, timedelta

import websockets

from src.handlers import send_multiple

base_url = 'wss://fstream.binance.com/stream?streams=BTCUSDT@aggTrade'

requested_tickers = {
    'btcusdt': 100,
    'ethusdt': 1500
}


async def monitor_whale_trades() -> None:
    connection = await websockets.connect(base_url)
    await connection.send(
        json.dumps(
            {
                'method': 'SUBSCRIBE',
                'params': [f'{ticker}@aggTrade' for ticker in requested_tickers],
                'id': 1
            }
        )
    )
    await connection.recv()
    start = datetime.now()
    while True:
        trade = json.loads(await connection.recv())['data']
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
