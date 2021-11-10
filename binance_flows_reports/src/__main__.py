import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import boto3
from aiohttp import ClientSession
from boto3.dynamodb.conditions import Key

from .config import AWSConfig, DynamoDBConfig, API

logging.basicConfig(
    format='%(asctime)s [%(levelname)-5.5s]  %(message)s',
    level=logging.INFO
)


def create_resource():
    return boto3.resource(
        'dynamodb',
        region_name=AWSConfig().region,
        endpoint_url=DynamoDBConfig().endpoint_url,
        aws_access_key_id=AWSConfig().access_key.get_secret_value(),
        aws_secret_access_key=AWSConfig().secret_access_key.get_secret_value()
    )


def aggregate_transactions(transactions):
    tickers = defaultdict(int)
    for transaction in transactions:
        if 'binance' in (transaction['from_name'], transaction['to_name']):
            if transaction['from_name'] == transaction['to_name']:
                continue
            multiplier = 1 if transaction['to_name'] == 'binance' else -1
            amount = transaction['amount'] * multiplier
            tickers[transaction['ticker']] += amount
    return tickers


def generate_message(hour_tickers, period, full=False):
    tickers_data = []
    for ticker, amount in hour_tickers.items():
        if not amount:
            continue
        postfix = ''
        if 'usd' in ticker:
            if not full and abs(amount / 10 ** 3) < 1000:
                continue
            elif abs(amount / 10 ** 6) < 1000:
                amount /= 10 ** 6
                postfix = 'млн'
            elif abs(amount / 10 ** 9) < 1000:
                amount /= 10 ** 9
                postfix = 'млрд'

            if not full and postfix != 'млрд':
                continue
        if not full:
            if 'eth' in ticker and abs(amount) < 20_000:
                continue
            elif 'btc' in ticker and abs(amount) < 2_000:
                continue

        ticker = ticker.upper().ljust(4)
        amount = int(amount)
        tickers_data.append(
            f'<pre>{ticker}</pre> {"⬆️ приток" if amount > 0 else "⬇️ отток"} {amount:,} {postfix}'
        )

    if not tickers_data:
        return None

    return f'Binance. Статистика за <pre>{period}</pre>:\n' + '\n'.join(tickers_data)


def get_transactions(dynamodb, now, hours):
    response = dynamodb.Table('Transactions').scan(
        FilterExpression=Key('timestamp').between(
            int((now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours)).timestamp()),
            int(now.replace(minute=0, second=0, microsecond=0).timestamp())
        )
    )
    return response['Items']


async def send_report(dynamodb, now, hours):
    transactions = get_transactions(dynamodb, now, hours)
    tickers = aggregate_transactions(transactions)
    mapping = {1: 'час', 6: 'последние 6 часов'}
    logging.info(tickers)
    if message := generate_message(tickers, period=mapping[hours]):
        async with ClientSession() as session:
            response = await session.post(API().api_url, data={'message': message})
            logging.info(response.status)


async def main():
    dynamodb = create_resource()
    now = datetime.now()
    if now - now.replace(minute=0, second=0, microsecond=0) > timedelta(minutes=10):
        seconds = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, minutes=5) - now).seconds
        logging.info(f'Sleeping {str(timedelta(seconds=seconds))}.')
        await asyncio.sleep(seconds)
        logging.info('Done.')
    while True:
        now = datetime.now()
        logging.info('Sending hourly report.')
        await send_report(dynamodb, now, 1)
        if now.hour in (0, 6, 12, 18):
            logging.info('Sending 6-hourly report.')
            await send_report(dynamodb, now, 6)
        await asyncio.sleep(timedelta(hours=1).seconds)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
