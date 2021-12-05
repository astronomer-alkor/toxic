import logging

logging.getLogger('aiohttp').setLevel(logging.WARNING)
logging.getLogger('matplotlib').setLevel(logging.WARNING)

logging.basicConfig(
    format='%(asctime)s [%(levelname)-5.5s]  %(pathname)s:%(lineno)d  %(message)s',
    level=logging.INFO
)
