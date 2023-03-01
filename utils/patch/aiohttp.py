import asyncio
from typing import Optional

import aiohttp  # pylint: disable=W0406
from aiohttp import ClientError

from utils.patch.methods import patch, patchable


class AioHttpTimeoutException(ClientError):
    pass


@patch(aiohttp.helpers.TimerContext)
class TimerContext:
    @patchable
    def __exit__(self, *args, **kwargs) -> Optional[bool]:
        try:
            return self.old___exit__(*args, **kwargs)
        except asyncio.TimeoutError:
            raise AioHttpTimeoutException from None
