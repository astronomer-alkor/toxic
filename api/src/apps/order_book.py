import asyncio
import json
import logging
from datetime import datetime, timedelta
from io import BytesIO
from itertools import groupby
from multiprocessing import connection, Process, Pipe
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import websockets
from aiohttp import ClientSession
from pytz import timezone

from src.utils import cached

base_url = 'wss://fstream.binance.com/stream'


def convert_items(items) -> List[List[float]]:
    return [list(map(float, item)) for item in items]


def round_down(value: float) -> float:
    value = int(value)
    return value - value % 100


def round_down_item(item) -> float:
    return round_down(item[0])


def sum_group(group) -> Tuple[float, int]:
    return round_down_item(group[0]), round(sum(i[1] for i in group))


class OrderBook:
    def __init__(self) -> None:
        self.bids = {}
        self.asks = {}
        self.current_price = None
        self.start_datetime = datetime.now() + timedelta(minutes=5)

    async def initialize(self) -> None:
        url = 'https://fapi.binance.com/fapi/v1/ticker/price?symbol=BTCUSDT'
        async with ClientSession() as session:
            r = await session.get(url)
            self.current_price = float((await r.json())['price'])
        url = 'https://fapi.binance.com/fapi/v1/depth?symbol=BTCUSDT&limit=1000'
        async with ClientSession() as session:
            r = await session.get(url)
            data = await r.json()
        bid = [[float(i) for i in item] for item in data['bids']]
        ask = [[float(i) for i in item] for item in data['asks']]
        self.add_new_data(bid=bid, ask=ask)

    def add_new_data(self, **data_items: List[List[float]]):
        for data_type, items in data_items.items():
            to_update = self.bids if data_type == 'bid' else self.asks
            for item in items:
                if item[1]:
                    to_update[item[0]] = item[1]
                else:
                    to_update.pop(item[0], None)

    def prepare_to_draw(self) -> Tuple[Dict[float, int], Dict[float, int]]:
        asks = [sum_group(list(group)) for _, group in groupby(self.asks.items(), key=round_down_item)]
        bids = [sum_group(list(group)) for _, group in groupby(self.bids.items(), key=round_down_item)]
        asks = dict(sorted(asks))
        bids = dict(reversed(dict(sorted(bids)).items()))
        return asks, bids

    def _draw_asks(self, asks: Dict[float, int], ax) -> None:
        rows = []
        cur_price = round_down(self.current_price)
        index = 0
        while True:
            count_by_price = asks.get(cur_price, 0)
            rows.append((cur_price, count_by_price, index))
            index += 1
            cur_price += 100
            if index == 11:
                break
        ax.barh(y=[i[-1] for i in rows], width=[i[1] for i in rows], height=0.8, color='#362328')
        for index, item in enumerate(rows):
            ax.text(8, index - .2, str(item[1]), color='white')
            ax.text(147, index - .2, str(item[0]), color='#DC535E')

    def _draw_bids(self, bids: Dict[float, int], ax) -> None:
        rows = []
        cur_price = round_down(self.current_price)
        index = -1
        while True:
            count_by_price = bids.get(cur_price, 0)
            rows.append((cur_price, count_by_price, index))
            index -= 1
            cur_price -= 100
            if index == -12:
                break
        ax.barh(y=[i[-1] for i in rows], width=[i[1] for i in rows], height=0.8, color='#21342e')
        for index, item in enumerate(rows):
            ax.text(8, -index - 1.2, str(item[1]), color='white')
            ax.text(147, -index - 1.2, str(item[0]), color='#58BE82')

    @cached
    async def draw(self):
        if (now := datetime.now()) < self.start_datetime:
            delta = (self.start_datetime - now)
            minutes, seconds = divmod(delta.seconds, 60)
            minutes_part = f'{minutes} мин ' if minutes else ''
            return f'Стакан будет досупен через {minutes_part}{seconds} сек'

        receive_end, send_end = Pipe(duplex=False)
        p = Process(target=self._draw, args=(send_end, ))
        p.start()
        p.join()
        buffer = BytesIO()
        buffer.write(receive_end.recv())
        buffer.seek(0)
        return buffer

    def _draw(self, pipe: connection.Connection) -> None:
        asks, bids = self.prepare_to_draw()
        fig = plt.figure(figsize=(5, 10))
        ax = fig.subplots()
        fig.tight_layout()
        plt.subplots_adjust(left=0, top=1, right=1, bottom=0)

        ax.set_facecolor((0.0902, 0.10196, 0.117647))
        ax.set_yticklabels([])
        ax.set_xticklabels([])
        ax.set_yticks([])
        ax.set_xticks([])
        ax.set_xlim([0, 150])
        ax.set_ylim([-12, 11])
        ax.invert_xaxis()
        ax.text(
            147, -11.87,
            f'Last updated at {datetime.now(tz=timezone("Europe/Moscow")).time().replace(microsecond=0)} (GMT+3)',
            color='white'
        )
        self._draw_asks(asks, ax)
        self._draw_bids(bids, ax)

        buffer = BytesIO()
        plt.savefig(buffer, format='png')
        buffer.seek(0)

        plt.close('all')

        pipe.send(buffer.read())


book = OrderBook()


async def start_order_book() -> None:
    logging.info('Initializing Order Book')
    await book.initialize()
    logging.info('Done')
    conn = await websockets.connect(base_url)
    await conn.send(
        json.dumps(
            {
                'method': 'SUBSCRIBE',
                'params': [
                    'btcusdt@depth',
                    'btcusdt@ticker'
                ],
                'id': 1
            }
        )
    )
    await conn.recv()
    while True:
        response = json.loads(await conn.recv())
        data = response['data']
        if '@ticker' in response['stream']:
            book.current_price = float(data['c'])
            continue
        book.add_new_data(bid=convert_items(data['b']), ask=convert_items(data['a']))


if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(start_order_book())
