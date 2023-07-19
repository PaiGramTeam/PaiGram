import simnet
from httpx import AsyncClient, Timeout, Limits

from core.config import config
from utils.patch.methods import patch, patchable


@patch(simnet.GenshinClient)
class GenshinClient:
    @patchable
    def __init__(self, *args, **kwargs):
        self.old___init__(*args, **kwargs)
        self.client: AsyncClient
        if config.connect_timeout and config.read_timeout and config.write_timeout and config.pool_timeout:
            self.client.timeout = Timeout(
                connect=config.connect_timeout,
                read=config.read_timeout,
                write=config.write_timeout,
                pool=config.pool_timeout,
            )
        self.client.limits = Limits(
            max_connections=config.connection_pool_size,
            max_keepalive_connections=config.connection_pool_size,
        )
