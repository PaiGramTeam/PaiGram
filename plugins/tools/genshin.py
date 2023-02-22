from functools import lru_cache
from typing import Optional, Tuple, Union

import genshin

from core.config import ApplicationConfig, config
from core.dependence.redisdb import RedisDB
from core.error import ServiceNotFoundError
from core.plugin import Plugin
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.models import RegionEnum
from core.services.players.services import PlayersService
from core.services.users import UserService
from utils.const import REGION_MAP

__all__ = ("GenshinHelper", "UserNotFoundError", "CookiesNotFoundError")


class UserNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"User not found, user_id: {user_id}")


class CookiesNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"{user_id} cookies not found")


class GenshinHelper(Plugin):
    def __init__(
        self,
        cookies: CookiesService,
        public_cookies: PublicCookiesService,
        user: UserService,
        redis: RedisDB,
        player: PlayersService,
    ) -> None:
        self.cookies_service = cookies
        self.public_cookies_service = public_cookies
        self.user_service = user
        self.redis_db = redis
        self.players_service = player

        if self.redis_db and config.genshin_ttl:
            self.genshin_cache = genshin.RedisCache(self.redis_db.client, ttl=config.genshin_ttl)
        else:
            self.genshin_cache = None

        if None in (temp := [self.user_service, self.cookies_service, self.players_service]):
            raise ServiceNotFoundError(*filter(lambda x: x is None, temp))

    @staticmethod
    @lru_cache(64)
    def region_server(uid: Union[int, str]) -> RegionEnum:
        if isinstance(uid, (int, str)):
            region = REGION_MAP.get(str(uid)[0])
        else:
            raise TypeError("UID variable type error")
        if region:
            return region
        raise ValueError(f"UID {uid} isn't associated with any region.")

    async def get_genshin_client(
        self, user_id: int, region: Optional[RegionEnum] = None, need_cookie: bool = True
    ) -> Optional[genshin.Client]:
        """通过 user_id 和 region 获取私有的 `genshin.Client`"""
        player = await self.players_service.get_player(user_id, region)
        if player is None:
            raise UserNotFoundError(user_id)
        cookies = None
        if need_cookie:
            cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
            if cookie_model is None:
                raise CookiesNotFoundError(user_id)
            cookies = cookie_model.data

        uid = player.player_id
        region = player.region
        if region == RegionEnum.HYPERION:  # 国服
            game_region = genshin.types.Region.CHINESE
        elif region == RegionEnum.HOYOLAB:  # 国际服
            game_region = genshin.types.Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        client = genshin.Client(cookies, lang="zh-cn", game=genshin.types.Game.GENSHIN, region=game_region, uid=uid)

        if self.genshin_cache is not None:
            client.cache = self.genshin_cache

        return client

    async def get_public_genshin_client(self, user_id: int) -> Tuple[genshin.Client, int]:
        """通过 user_id 获取公共的 `genshin.Client`"""
        player = await self.players_service.get_player(user_id)

        region = player.region
        cookies = await self.public_cookies_service.get_cookies(user_id, region)

        uid = player.player_id
        if region is RegionEnum.HYPERION:
            game_region = genshin.types.Region.CHINESE
        elif region is RegionEnum.HOYOLAB:
            game_region = genshin.types.Region.OVERSEAS
        else:
            raise TypeError("Region is not `RegionEnum.NULL`")

        client = genshin.Client(
            cookies.data, region=game_region, uid=uid, game=genshin.types.Game.GENSHIN, lang="zh-cn"
        )

        if self.genshin_cache is not None:
            client.cache = self.genshin_cache

        return client, uid
