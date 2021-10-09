import asyncio

from src.handlers import send_multiple
from .order_book import book


def describe_wall(wall, wall_type):
    get = max if wall_type == 'ask' else min
    return int(get([i[0] for i in wall]))

    # fig = plt.figure(figsize=(5, 10))
    # ax = fig.subplots()
    # ax.set_facecolor((0.0902, 0.10196, 0.117647))
    # color = '#362328' if wall_type == 'ask' else '#58BE82'
    # ax.bar(x=[i[0] for i in wall], height=[i[1] for i in wall], width=0.8, color=color)
    # plt.show()


def generate_message(ask, bid):
    return f'🔴 Продажа {ask:,d}. Стоп {ask + 50:,d}\n🟢 Покупка {bid:,d}. Стоп {bid - 50:,d}'


async def generate_entry_points():
    prev_alert = None
    await asyncio.sleep(300)
    while True:
        asks, bids = book.get_grouped_orders(100)
        sum_asks, sum_bids = book.sum_groups(asks, bids)
        asks_walls = {k for k, v in sum_asks.items() if v - sum_bids.get(k, 0) > 300}
        bids_walls = {k for k, v in sum_bids.items() if v - sum_asks.get(k, 0) > 300}

        if not all((asks_walls, bids_walls)):
            await asyncio.sleep(5)
            continue

        ask_order = describe_wall(asks[min(asks_walls)], wall_type='ask')
        bid_order = describe_wall(bids[max(bids_walls)], wall_type='bid')

        alert = generate_message(ask_order, bid_order)
        if alert != prev_alert:
            prev_alert = alert
            await send_multiple(alert, check_admin=True)
        await asyncio.sleep(20)
