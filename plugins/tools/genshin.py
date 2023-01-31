from functools import lru_cache
from typing import Optional, Tuple, Union

import genshin

from core.config import BotConfig
from core.dependence.redisdb import RedisDB
from core.error import ServiceNotFoundError
from core.plugin import Plugin
from core.services.cookies import CookiesService, PublicCookiesService
from core.services.players import PlayersService
from core.services.users import UserService
from utils.const import REGION_MAP
from utils.models.base import RegionEnum

__all__ = ("GenshinHelper",)


class GenshinHelper(Plugin):
    def __init__(
        self,
        cookies: CookiesService,
        public_cookies: PublicCookiesService,
        user: UserService,
        redis: RedisDB,
        player: PlayersService,
        bot_config: BotConfig,
    ) -> None:
        self.cookies_service = cookies
        self.public_cookies_service = public_cookies
        self.user_service = user
        self.redis_db = redis
        self.players_service = player

        if self.redis_db and bot_config.genshin_ttl:
            self.genshin_cache = genshin.RedisCache(self.redis_db.client, ttl=bot_config.genshin_ttl)
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
            return
        cookies = None
        if need_cookie:
            cookie_model = await self.cookies_service.get(player.user_id, player.region)
            if cookie_model is None:
                return
            cookies = cookie_model.data

        uid = player.player_id
        if region is RegionEnum.HYPERION:  # 国服
            game_region = genshin.types.Region.CHINESE
        elif region is RegionEnum.HOYOLAB:  # 国际服
            game_region = genshin.types.Region.OVERSEAS
        else:
            raise TypeError("Region is not `RegionEnum.NULL`")

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
