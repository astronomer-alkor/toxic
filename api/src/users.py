from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.config import AWSConfig, DynamoDBConfig


class Users:
    def __init__(self) -> None:
        self.resource = boto3.resource(
            'dynamodb',
            region_name=AWSConfig().region,
            endpoint_url=DynamoDBConfig().endpoint_url,
            aws_access_key_id=AWSConfig().access_key.get_secret_value(),
            aws_secret_access_key=AWSConfig().secret_access_key.get_secret_value()
        )

    def get_recipients(self) -> List[int]:
        recipients = self.resource.Table('Users').scan(
            FilterExpression=Key('subscribe').eq(True),
            ProjectionExpression='id'
        )['Items']
        return [int(recipient['id']) for recipient in recipients]

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        user = self.resource.Table('Users').query(
            KeyConditionExpression=Key('id').eq(user_id)
        )['Items']
        return user[0] if user else None

    def put_user(self, **kwargs) -> None:
        self.resource.Table('Users').put_item(Item=kwargs)

    async def delete_users(self, user_ids: List[int]) -> None:
        table = self.resource.Table('Users')
        for user_id in user_ids:
            table.delete_item(Key={'id': user_id})

    async def is_admin(self, user_id: int) -> bool:
        user = self.get_user(user_id) or {}
        return user.get('admin')
