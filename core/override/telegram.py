"""重写 telegram.request.HTTPXRequest 使其使用 ujson 库进行 json 序列化"""
from typing import Any, AsyncIterable, Optional

import httpcore
from httpx import (
    AsyncByteStream,
    AsyncHTTPTransport as DefaultAsyncHTTPTransport,
    Limits,
    Response as DefaultResponse,
    Timeout,
)
from telegram.request import HTTPXRequest as DefaultHTTPXRequest

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

__all__ = ("HTTPXRequest",)


class Response(DefaultResponse):
    def json(self, **kwargs: Any) -> Any:
        # noinspection PyProtectedMember
        from httpx._utils import guess_json_utf

        if self.charset_encoding is None and self.content and len(self.content) > 3:
            encoding = guess_json_utf(self.content)
            if encoding is not None:
                return jsonlib.loads(self.content.decode(encoding), **kwargs)
        return jsonlib.loads(self.text, **kwargs)


# noinspection PyProtectedMember
class AsyncHTTPTransport(DefaultAsyncHTTPTransport):
    async def handle_async_request(self, request) -> Response:
        from httpx._transports.default import (
            map_httpcore_exceptions,
            AsyncResponseStream,
        )

        if not isinstance(request.stream, AsyncByteStream):
            raise AssertionError

        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)

        if not isinstance(resp.stream, AsyncIterable):
            raise AssertionError

        return Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(resp.stream),
            extensions=resp.extensions,
        )


class HTTPXRequest(DefaultHTTPXRequest):
    def __init__(  # pylint: disable=W0231
        self,
        connection_pool_size: int = 1,
        proxy_url: str = None,
        read_timeout: Optional[float] = 5.0,
        write_timeout: Optional[float] = 5.0,
        connect_timeout: Optional[float] = 5.0,
        pool_timeout: Optional[float] = 1.0,
        http_version: str = "1.1",
    ):
        self._http_version = http_version
        timeout = Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )
        limits = Limits(
            max_connections=connection_pool_size,
            max_keepalive_connections=connection_pool_size,
        )
        if http_version not in ("1.1", "2"):
            raise ValueError("`http_version` must be either '1.1' or '2'.")
        http1 = http_version == "1.1"
        self._client_kwargs = dict(
            timeout=timeout,
            proxies=proxy_url,
            limits=limits,
            transport=AsyncHTTPTransport(limits=limits),
            http1=http1,
            http2=not http1,
        )

        try:
            self._client = self._build_client()
        except ImportError as exc:
            if "httpx[http2]" not in str(exc) and "httpx[socks]" not in str(exc):
                raise exc

            if "httpx[socks]" in str(exc):
                raise RuntimeError(
                    "To use Socks5 proxies, PTB must be installed via `pip install " "python-telegram-bot[socks]`."
                ) from exc
            raise RuntimeError(
                "To use HTTP/2, PTB must be installed via `pip install " "python-telegram-bot[http2]`."
            ) from exc
