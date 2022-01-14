import asyncio
from datetime import datetime
import requests

from src.apps.currency.utils import generate_signature, convert_payload_to_params

base_url = 'https://demo-api-adapter.backend.currency.com/api/v1'

secret_api_key = 'secret_api_key'
api_key = 'api_key'


async def main():
    timestamp = int(datetime.now().timestamp() * 1000)

    payload = {
        'apiKey': api_key,
        'timestamp': timestamp
    }
    params = convert_payload_to_params(payload)

    payload['signature'] = generate_signature(secret_api_key, params)
    r = requests.get(f'{base_url}/account?{convert_payload_to_params(payload)}', headers={'X-MBX-APIKEY': api_key})

    account = r.json()

    free_amount = account['balances'][0]['free']

    payload = {
        'symbol': 'BTC/USD_LEVERAGE',
        'side': 'BUY',
        'type': 'MARKET',
        'quantity': free_amount / 20,
        'leverage': 20,
        'accountId': account['balances'][0]['accountId'],
        'recvWindow': 5000,
        'apiKey': api_key,
        'timestamp': timestamp,
    }
    params = convert_payload_to_params(payload)

    payload['signature'] = generate_signature(secret_api_key, params)
    r = requests.post(f'{base_url}/order?{convert_payload_to_params(payload)}', headers={'X-MBX-APIKEY': api_key})
    print(r.json())


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
