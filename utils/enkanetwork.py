import logging
import warnings
from typing import Dict, Any, Optional, TYPE_CHECKING

from cachetools import TTLCache
from enkanetwork.assets import Assets
from enkanetwork.cache import Cache
from enkanetwork.client import EnkaNetworkAPI as _EnkaNetworkAPI
from enkanetwork.config import Config
from enkanetwork.exception import TimedOut, NetworkError, EnkaServerError, ERROR_ENKA
from enkanetwork.http import HTTPClient as _HTTPClient, Route
from httpx import AsyncClient, TimeoutException, HTTPError, Timeout

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib

if TYPE_CHECKING:
    from redis import asyncio as aioredis

__all__ = ("RedisCache", "StaticCache", "HTTPClient", "EnkaNetworkAPI")


class StaticCache(Cache):
    def __init__(self, maxsize: int, ttl: int) -> None:
        self.cache = TTLCache(maxsize, ttl)

    async def get(self, key) -> Dict[str, Any]:
        data = self.cache.get(key)
        return jsonlib.loads(data) if data is not None else data

    async def set(self, key, value) -> None:
        self.cache[key] = jsonlib.dumps(value)


class RedisCache(Cache):
    def __init__(self, redis: "aioredis.Redis", key: Optional[str] = None, ex: int = 60 * 3) -> None:
        self.redis = redis
        self.ex = ex
        self.key = key

    def get_qname(self, key):
        return f"{self.key}:{key}" if self.key else f"enka_network:{key}"

    async def get(self, key) -> Optional[Dict[str, Any]]:
        qname = self.get_qname(key)
        data = await self.redis.get(qname)
        if data:
            json_data = str(data, encoding="utf-8")
            return jsonlib.loads(json_data)
        return None

    async def set(self, key, value) -> None:
        qname = self.get_qname(key)
        data = jsonlib.dumps(value)
        await self.redis.set(qname, data, ex=self.ex)

    async def exists(self, key) -> int:
        qname = self.get_qname(key)
        return await self.redis.exists(qname)

    async def ttl(self, key) -> int:
        qname = self.get_qname(key)
        return await self.redis.ttl(qname)


class HTTPClient(_HTTPClient):
    async def close(self) -> None:
        if not self.client.is_closed:
            await self.client.aclose()

    def __init__(
        self, *, key: Optional[str] = None, agent: Optional[str] = None, timeout: Optional[Any] = None
    ) -> None:
        if timeout is None:
            timeout = Timeout(
                connect=5.0,
                read=5.0,
                write=5.0,
                pool=1.0,
            )

        if agent is not None:
            Config.init_user_agent(agent)
        agent = agent or Config.USER_AGENT
        if key is None:
            warnings.warn("'key' has depercated.")
        self.client = AsyncClient(timeout=timeout, headers={"User-Agent": agent})

    async def request(self, route: Route, **kwargs: Any) -> Any:
        method = route.method
        url = route.url
        username = route.username

        try:
            response = await self.client.request(method, url, **kwargs)
        except TimeoutException as e:
            raise TimedOut from e
        except HTTPError as e:
            raise NetworkError from e

        _host = response.url.host

        if response.is_error:
            if _host == Config.ENKA_URL:
                err = ERROR_ENKA.get(response.status_code, None)
                if err:
                    raise err[0](err[1].format(uid=username))
            raise EnkaServerError(f"Server error status code: {response.status_code}")

        return {"status": response.status_code, "content": response.content}


class EnkaNetworkAPI(_EnkaNetworkAPI):
    def __init__(
        self,
        *,
        lang: str = "en",
        debug: bool = False,
        key: str = "",
        cache: bool = True,
        user_agent: str = "",
        timeout: int = 10,
    ) -> None:  # noqa: E501
        # Logging
        logging.basicConfig()
        logging.getLogger("enkanetwork").setLevel(logging.DEBUG if debug else logging.ERROR)  # noqa: E501

        # Set language and load config
        self.assets = Assets(lang)

        # Cache
        self._enable_cache = cache
        if self._enable_cache:
            Config.init_cache(StaticCache(1024, 60 * 1))

        # http client
        self.__http = HTTPClient(key=key, agent=user_agent, timeout=timeout)  # skipcq: PTC-W0037
        self._closed = False
