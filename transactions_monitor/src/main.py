import asyncio
from asyncio.exceptions import TimeoutError
from datetime import datetime
from decimal import Decimal
import logging

from aiohttp.client import ClientSession

from .config import WhaleAlertsConfig

tickers = ('btc', 'eth', 'usdc', 'usdt', 'busd')
base_url = 'https://api.whale-alert.io/v1/transactions?min_value=500000'


async def get_data(url):
    while True:
        try:
            async with ClientSession() as session:
                r = await session.get(
                    url,
                    headers={'X-WA-API-KEY': WhaleAlertsConfig().api_key.get_secret_value()},
                    timeout=4
                )
            if 'json' in r.headers['Content-Type']:
                return await r.json()
        except TimeoutError:
            await asyncio.sleep(10)


def save_transactions(dynamo_resource, items):
    table = dynamo_resource.Table('Transactions')
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


async def start_monitoring(dynamo_resource):
    logging.info('Starting monitoring.')
    transactions_cache = {}
    start_hour = datetime.now().hour
    while True:
        try:
            now = datetime.now()
            left = int(now.replace(microsecond=0, second=0).timestamp()) - 45
            right = left + 61 + 45
            url = f'{base_url}&start={left}&end={right}'

            data = await get_data(url)
            for transaction in data.get('transactions', ()):
                if transaction['symbol'] not in tickers:
                    continue
                elif transaction['hash'] in transactions_cache:
                    continue
                elif (hour := datetime.fromtimestamp(transaction['timestamp']).hour) > start_hour:
                    logging.info(f'Saving transactions. Count: {len(transactions_cache)}.')
                    save_transactions(dynamo_resource, list(transactions_cache.values()))
                    logging.info('Saving completed.')
                    transactions_cache.clear()
                    start_hour = hour

                transactions_cache[transaction['hash']] = {
                    'hash': transaction['hash'],
                    'from_name': transaction['from'].get('owner'),
                    'to_name': transaction['to'].get('owner'),
                    'ticker': transaction['symbol'],
                    'timestamp': transaction['timestamp'],
                    'amount': Decimal(str(round(transaction['amount'], 2)))
                }

            await asyncio.sleep(15)
        except Exception as e:
            logging.error('An error occurred: ' + str(e))
            raise
