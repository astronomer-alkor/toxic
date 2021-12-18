import asyncio
import logging
from asyncio.exceptions import TimeoutError
from datetime import datetime, timedelta
from decimal import Decimal

from aiohttp.client import ClientSession

from .config import WhaleAlertsConfig

tickers = ('btc', 'eth', 'usdc', 'usdt', 'busd')
base_url = 'https://api.whale-alert.io/v1/transactions?min_value=500000'


async def get_json(url):
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
        except TimeoutError as e:
            logging.error('Timeout reached: ' + str(e))
            await asyncio.sleep(10)


async def paginate(url, cursor=None):
    if cursor:
        url = f'{url}&cursor={cursor}'
    data = await get_json(url)

    if data['count']:
        return data['transactions'], data['cursor']
    return None


async def get_transactions(url):
    all_transactions = []
    cursor = None
    while True:
        if result := await paginate(url, cursor):
            await asyncio.sleep(10)
            transactions, cursor = result
            all_transactions.extend(transactions)
        else:
            return all_transactions


def save_transactions(dynamo_resource, items):
    table = dynamo_resource.Table('Transactions')
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)


async def start_monitoring(dynamo_resource):
    logging.info('Starting monitoring.')
    while True:
        try:
            right = int(datetime.now().timestamp())
            left = right - timedelta(minutes=5).seconds
            url = f'{base_url}&start={left}&end={right}'

            transactions = {}
            for transaction in await get_transactions(url):
                if transaction['symbol'] not in tickers:
                    continue
                transactions[transaction['hash']] = {
                    'hash': transaction['hash'],
                    'from_name': transaction['from'].get('owner'),
                    'to_name': transaction['to'].get('owner'),
                    'from_address': transaction['from'].get('address'),
                    'to_address': transaction['to'].get('address'),
                    'ticker': transaction['symbol'],
                    'timestamp': transaction['timestamp'],
                    'amount': Decimal(str(round(transaction['amount'], 2))),
                    'amount_usd': Decimal(str(round(transaction['amount_usd'], 2)))
                }

            logging.info(f'Saving transactions. Count: {len(transactions)}.')
            save_transactions(dynamo_resource, list(transactions.values()))
            logging.info('Saving completed.')

            await asyncio.sleep(15)
        except Exception as e:
            logging.error('An error occurred: ' + str(e))
            raise
