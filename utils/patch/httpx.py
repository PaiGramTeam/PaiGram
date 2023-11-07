from typing import Union

import httpx

from core.config import config
from utils.patch.methods import patch, patchable

WHITE_LIST = ["mihoyo.com", "miyoushe.com"]


@patch(httpx.AsyncClient)
class AsyncClient:
    @patchable
    async def request(
        self,
        method: str,
        url: Union[httpx.URL, str],
        *args,
        **kwargs,
    ):
        if not config.easy_proxy:
            return await self.old_request(method, url, *args, **kwargs)
        old_url = str(url)
        for domain in WHITE_LIST:
            if domain in old_url:
                break
        else:
            return await self.old_request(method, url, *args, **kwargs)
        url = config.easy_proxy + str(url)
        return await self.old_request(method, url, *args, **kwargs)
