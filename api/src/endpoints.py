from aiohttp import web

from .config import ApiConfig
from .handlers import send_multiple

routes = web.RouteTableDef()


@routes.get('/')
async def index(request: web.Request):
    return web.Response(text='OK')


@routes.post(f'/{ApiConfig().notifications_path.get_secret_value()}')
async def send_notifications(request: web.Request):
    data = await request.post()
    await send_multiple(data['message'])

    return web.Response(text='OK')
