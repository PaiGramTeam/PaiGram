import typing

import httpx

from utils.patch.methods import patch, patchable

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


@patch(httpx.Response)
class Response:
    @patchable
    def json(self, **kwargs: typing.Any) -> typing.Any:
        return jsonlib.loads(self.content, **kwargs)
