import asyncio
import logging

import boto3

from .config import AWSConfig, DynamoDBConfig
from .main import start_monitoring

logging.basicConfig(
    format='%(asctime)s [%(levelname)-5.5s]  %(message)s',
    level=logging.INFO
)


def create_schema(client):
    client.create_table(
        TableName='Transactions',
        KeySchema=[
            {
                'AttributeName': 'hash',
                'KeyType': 'HASH'
            },
            {
                'AttributeName': 'timestamp',
                'KeyType': 'RANGE'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'hash',
                'AttributeType': 'S'
            },
            {
                'AttributeName': 'timestamp',
                'AttributeType': 'N'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1,
        }
    )

    client.create_table(
        TableName='Users',
        KeySchema=[
            {
                'AttributeName': 'id',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'id',
                'AttributeType': 'N'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 1,
            'WriteCapacityUnits': 1,
        }
    )


async def main():
    kwargs = {
        'region_name': AWSConfig().region,
        'endpoint_url': DynamoDBConfig().endpoint_url,
        'aws_access_key_id': AWSConfig().access_key.get_secret_value(),
        'aws_secret_access_key': AWSConfig().secret_access_key.get_secret_value()
    }
    resource = boto3.resource('dynamodb', **kwargs)
    client = boto3.client('dynamodb', **kwargs)
    if not client.list_tables()['TableNames']:
        logging.info('Creating tables.')
        create_schema(client)
        logging.info('Creation of tables complete.')

    await start_monitoring(resource)


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
