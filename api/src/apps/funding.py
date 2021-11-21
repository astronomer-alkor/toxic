import asyncio
import logging
import math
import os
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from math import ceil
from multiprocessing import Process
from typing import Dict, List, Tuple
from uuid import uuid4

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from aiohttp import ClientSession
from more_itertools import chunked, flatten

from src.utils import cached


class Funding:
    def __init__(self, callback):
        self.path = f'/tmp/{uuid4()}.png'
        self.callback = callback
        self.tickers = None

    async def send_funding_image(self, message):
        if image := await self.draw(_=message):
            await self.callback(image, is_photo=True)

    def _draw(self, tickers: Dict[str, Tuple[List[Decimal], List[datetime]]]):
        logging.info(f'Start drawing funding image for {len(tickers)} tickers')
        colors = (
            '#6caeb0',
            '#8e3ea0',
            '#e8b941',
        )

        subplots_count = ceil(len(tickers) / len(colors))
        fig_width = 25
        dpi = 70
        plot_adjust_left = None
        if subplots_count > 3:
            plot_adjust_left = 0.05
            if subplots_count > 20:
                ratio = 4
            elif subplots_count > 8:
                ratio = 3
            else:
                ratio = 2

            fig_width *= ratio
            subplots_count = math.ceil(subplots_count / ratio)
            fig = plt.figure(figsize=(fig_width, subplots_count * 10), dpi=dpi)
            axs = list(flatten(fig.subplots(subplots_count, ratio)))
        else:
            fig = plt.figure(figsize=(fig_width, subplots_count * 10), dpi=dpi)
            axs = fig.subplots(subplots_count)
            if subplots_count == 1:
                axs = (axs,)
        fig.patch.set_facecolor((0.0902, 0.10196, 0.117647))

        for ax in axs:
            ax.set_facecolor((0.0902, 0.10196, 0.117647))
            ax.tick_params(axis='both', which='both', length=0)
            ax.set(frame_on=False)
            ax.set_axis_off()

        for ax, chunk in zip(axs, chunked(tickers.items(), len(colors))):
            ax.set_axis_on()
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            ax.grid(color='#9e690b', linestyle='--', linewidth=0.3)
            ax.tick_params(axis='y', direction='in', pad=-30)
            for color, (ticker_name, (x, y)) in zip(colors, chunk):
                ax.plot(y, x, color=color, label=ticker_name)
                legend = ax.legend(loc='upper left', prop={'size': 17}, framealpha=0, bbox_to_anchor=(-0.13, 0.95))
                plt.setp(legend.get_texts(), color='white')

        plt.subplots_adjust(left=plot_adjust_left, right=0.98, bottom=0.07, top=0.98, wspace=0.2, hspace=0.1)
        plt.savefig(self.path, format='png')
        logging.info('Funding image generated')

    @cached(60, only_kwargs=True)
    async def draw(self, *, _):
        if not self.tickers:
            return
        ticker_results = {}
        async with ClientSession() as session:
            for ticker in self.tickers:
                async with session.get(
                        f'https://www.binance.com/fapi/v1/fundingRate?limit=50&symbol={ticker}'
                ) as response:
                    funding = await response.json()

                x = []
                y = []
                for item in funding:
                    y.append(datetime.fromtimestamp(item['fundingTime'] / 1000))
                    x.append(Decimal(item['fundingRate']) * 100)
                ticker_results[ticker] = (x, y)

        Process(target=self._draw, args=(ticker_results,)).start()
        while not os.path.exists(self.path):
            await asyncio.sleep(1)

        file_size = os.path.getsize(self.path)
        while True:
            await asyncio.sleep(1)
            if (new_size := os.path.getsize(self.path)) > file_size:
                file_size = new_size
            else:
                break

        with open(self.path, 'br') as f:
            image = BytesIO(f.read())
        os.remove(self.path)
        return image

    @cached(60, only_kwargs=True)
    async def get_last_funding(self, *, args) -> str:
        deviation = False
        full = False
        requested_tickers = []
        if args == '!':
            deviation = True
        elif args == '*':
            full = True
        else:
            requested_tickers = list(filter(bool, args.split(' ')))

        if not deviation:
            for index, item in enumerate(requested_tickers):
                item = item.upper()
                if not item.endswith('USDT') and not item.endswith('BUSD'):
                    item = f'{item}USDT'
                requested_tickers[index] = item
            requested_tickers = requested_tickers or ('BTCUSDT', 'ETHUSDT')

        async with ClientSession() as session:
            async with session.get('https://www.binance.com/fapi/v1/premiumIndex') as response:
                data = await response.json()

        funding = []
        valid_tickers = []
        for item in data:
            if any((
                    full,
                    (symbol := item['symbol']) in requested_tickers,
                    (deviation and item['lastFundingRate'] != '0.00010000')
            )):
                if symbol.isalpha():
                    funding_value = str(Decimal(item['lastFundingRate']) * 100).rstrip('0') or '0'
                    item = f'{symbol} {funding_value}%'
                    valid_tickers.append(symbol)
                    funding.append(item)
        if valid_tickers:
            self.tickers = valid_tickers
            return '\n'.join(funding)
        return 'Неверные названия тикеров'
