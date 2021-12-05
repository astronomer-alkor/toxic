import json
import logging

import websockets
from websockets.exceptions import ConnectionClosedError


class WebSocketConnector:
    def __init__(self, connection_url: str, connection_data: dict) -> None:
        self.connection = None
        self.connection_url = connection_url
        self.connection_data = connection_data

    async def initialize_connection(self) -> None:
        self.connection = await websockets.connect(self.connection_url)

    async def subscribe(self) -> None:
        await self.connection.send(json.dumps(self.connection_data))
        await self.connection.recv()

    async def receive_data(self):
        is_error = False
        while True:
            try:
                data = await self.connection.recv()
                if is_error:
                    logging.info(f'{self.__class__.__name__} websocket connection stabilized')
                return data
            except ConnectionClosedError as e:
                is_error = True
                logging.warning(
                    f'Websocket connection for {self.__class__.__name__} was closed. Trying to reconnect...'
                )
                await self.initialize_connection()
                await self.subscribe()
