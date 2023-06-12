from contextlib import asynccontextmanager

from typing import Optional

from simnet import GenshinClient
from simnet.utils.enum_ import Region
from simnet.errors import InvalidCookies, BadRequest as SimnetBadRequest, TooManyRequests

from core.basemodel import RegionEnum
from core.error import ServiceNotFoundError
from core.plugin import Plugin
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.services import PlayersService
from core.services.users.services import UserService


class PlayerNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"User not found, user_id: {user_id}")


class CookiesNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"{user_id} cookies not found")


class SIMNetClient(Plugin):
    def __init__(
        self,
        cookies: CookiesService,
        public_cookies: PublicCookiesService,
        user: UserService,
        player: PlayersService,
    ) -> None:
        self.cookies_service = cookies
        self.public_cookies_service = public_cookies
        self.user_service = user
        self.players_service = player

        if None in (temp := [self.user_service, self.cookies_service, self.players_service]):
            raise ServiceNotFoundError(*filter(lambda x: x is None, temp))

    @asynccontextmanager
    def genshin(self, user_id: int, region: Optional[RegionEnum] = None) -> GenshinClient:
        player = await self.players_service.get_player(user_id, region)
        if player is None:
            raise PlayerNotFoundError(user_id)

        if player.account_id is None:
            raise CookiesNotFoundError(user_id)
        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model is None:
            raise CookiesNotFoundError(user_id)
        cookies = cookie_model.data

        region = player.region
        if region == RegionEnum.HYPERION:  # 国服
            game_region = Region.CHINESE
        elif region == RegionEnum.HOYOLAB:  # 国际服
            game_region = Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        async with GenshinClient(
            cookies, region=game_region, account_id=player.account_id, player_id=player.player_id
        ) as client:
            yield client

    async def get_genshin_client(self, user_id: int, region: Optional[RegionEnum] = None) -> GenshinClient:
        player = await self.players_service.get_player(user_id, region)
        if player is None:
            raise PlayerNotFoundError(user_id)

        if player.account_id is None:
            raise CookiesNotFoundError(user_id)
        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model is None:
            raise CookiesNotFoundError(user_id)
        cookies = cookie_model.data

        region = player.region
        if region == RegionEnum.HYPERION:
            game_region = Region.CHINESE
        elif region == RegionEnum.HOYOLAB:
            game_region = Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        return GenshinClient(cookies, region=game_region, account_id=player.account_id, player_id=player.player_id)

    @asynccontextmanager
    def public_genshin(self, user_id: int, region: Optional[RegionEnum] = None) -> GenshinClient:
        player = await self.players_service.get_player(user_id, region)

        region = player.region
        cookies = await self.public_cookies_service.get_cookies(user_id, region)

        uid = player.player_id
        if region is RegionEnum.HYPERION:
            game_region = Region.CHINESE
        elif region is RegionEnum.HOYOLAB:
            game_region = Region.OVERSEAS
        else:
            raise TypeError("Region is not `RegionEnum.NULL`")

        async with GenshinClient(cookies, region=game_region, account_id=player.account_id, player_id=uid) as client:
            try:
                yield client
            except SimnetBadRequest as exc:
                if exc.ret_code == 1034:
                    await self.public_cookies_service.undo(user_id)
                raise exc
