import math
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from src.config import AWSConfig, DynamoDBConfig


class PaginationItems(BaseModel):
    items: List[Any]
    page_num: int
    page_size: int
    pages_count: int


class Base:
    table_name = None

    def __init__(self) -> None:
        self.resource = boto3.resource(
            'dynamodb',
            region_name=AWSConfig().region,
            endpoint_url=DynamoDBConfig().endpoint_url,
            aws_access_key_id=AWSConfig().access_key.get_secret_value(),
            aws_secret_access_key=AWSConfig().secret_access_key.get_secret_value()
        )

    def get_all(self) -> List[Dict[str, Any]]:
        return self.resource.Table(self.table_name).scan()['Items']


class Users(Base):
    table_name = 'Users'

    def get_recipients(self) -> List[int]:
        recipients = self.resource.Table(self.table_name).scan(
            FilterExpression=Key('subscribe').eq(True),
            ProjectionExpression='id'
        )['Items']
        return [int(recipient['id']) for recipient in recipients]

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        user = self.resource.Table(self.table_name).query(
            KeyConditionExpression=Key('id').eq(user_id)
        )['Items']
        return user[0] if user else None

    def put_user(self, **kwargs) -> None:
        self.resource.Table(self.table_name).put_item(Item=kwargs)

    async def delete_users(self, user_ids: List[int]) -> None:
        table = self.resource.Table(self.table_name)
        for user_id in user_ids:
            table.delete_item(Key={'id': user_id})

    async def is_admin(self, user_id: int) -> bool:
        user = self.get_user(user_id) or {}
        return user.get('admin')

    async def get_bollinger_timeframes_by_ticker(self, user_id: int, ticker: str) -> List[str]:
        user = self.get_user(user_id)
        tickers = user.get('bollinger_tickers', ())
        return [item.split('@')[-1] for item in tickers if item.startswith(ticker)]

    async def get_bollinger_tickers(self, user_id: int) -> List[str]:
        return self.get_user(user_id).get('bollinger_tickers', [])

    async def delete_bollinger_ticker(self, user_id: int, ticker: str):
        tickers = self.get_user(user_id).get('bollinger_tickers', ())
        if ticker not in tickers:
            return None
        self.resource.Table(self.table_name).update_item(
            Key={'id': user_id},
            UpdateExpression=f'delete bollinger_tickers :item',
            ExpressionAttributeValues={
                ':item': {ticker}
            }
        )

    async def add_bollinger_ticker(self, user_id: int, ticker: str):
        tickers = self.get_user(user_id).get('bollinger_tickers', ())
        if not tickers:
            self.resource.Table(self.table_name).update_item(
                Key={'id': user_id},
                UpdateExpression='SET bollinger_tickers = :set',
                ExpressionAttributeValues={
                    ':set': {ticker}
                }
            )
        if ticker in tickers:
            return None
        self.resource.Table(self.table_name).update_item(
            Key={'id': user_id},
            UpdateExpression='ADD bollinger_tickers :item',
            ExpressionAttributeValues={
                ':item': {ticker},
            },
        )


class BollingerTickers(Base):
    table_name = 'BollingerTickers'

    async def get_tickers(self, page_num=0, page_size=10, user_id=None) -> PaginationItems:
        tickers = [ticker['ticker'] for ticker in self.get_all()]
        if user_id:
            user_tickers = {ticker.split('@')[0] for ticker in await Users().get_bollinger_tickers(user_id)}
            tickers = [ticker for ticker in tickers if ticker in user_tickers]
        return PaginationItems(
            items=tickers[page_size * page_num: page_size * page_num + page_size],
            page_num=page_num,
            page_size=page_size,
            pages_count=math.ceil(len(tickers) / page_size)
        )

    async def get_ticker_timeframes(self, ticker: str) -> List[str]:
        return self.resource.Table(self.table_name).query(
            KeyConditionExpression=Key('ticker').eq(ticker)
        )['Items'][0]['timeframe']
