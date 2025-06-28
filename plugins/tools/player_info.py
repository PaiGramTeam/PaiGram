from typing import Optional

from enkanetwork import Assets

from core.dependence.assets.impl.genshin import AssetsService
from core.plugin import Plugin
from core.services.players.services import PlayerInfoService, PlayersService
from utils.log import logger


class PlayerInfoSystem(Plugin):
    def __init__(
        self,
        player_service: PlayersService = None,
        assets_service: AssetsService = None,
        player_info_service: PlayerInfoService = None,
    ) -> None:
        self.assets_service = assets_service
        self.player_info_service = player_info_service
        self.player_service = player_service

    async def get_player_info(self, player_id: int, user_id: Optional[int], user_name: str):
        player = await self.player_service.get(user_id, player_id)
        player_info = await self.player_info_service.get(player)
        nickname = user_name
        name_card: Optional[str] = None
        avatar: Optional[str] = None
        rarity: int = 5
        try:
            if player_info is not None:
                if player_info.nickname is not None:
                    nickname = player_info.nickname
                if player_info.name_card is not None:
                    name_card = self.assets_service.namecard.navbar(int(player_info.name_card)).as_uri()
                if player_info.hand_image is not None:
                    if player_info.hand_image > 10000000:
                        avatar = self.assets_service.avatar.icon(player_info.hand_image).as_uri()
                        try:
                            rarity = self.assets_service.avatar.get_target(player_info.hand_image).rank
                        except KeyError:
                            logger.warning("未找到角色 %s 的星级", player_info.hand_image)
                    else:
                        avatar = Assets.profile_picture(player_info.hand_image).url
                        rarity = 5
        except Exception as exc:  # pylint: disable=W0703
            logger.error("卡片信息请求失败 %s", str(exc))
        if name_card is None:  # 默认
            name_card = self.assets_service.namecard.navbar(0).as_uri()
        if avatar is None:  # 默认
            avatar = self.assets_service.avatar.icon(0).as_uri()
        return name_card, avatar, nickname, rarity

    async def get_name_card(self, player_id: Optional[int], user_id: Optional[int]):
        name_card: Optional[str] = None
        player = await self.player_service.get(user_id, player_id)
        if player:
            player_info = await self.player_info_service.get(player)
            try:
                if player_info is not None and player_info.name_card is not None:
                    name_card = self.assets_service.namecard.navbar(int(player_info.name_card)).as_uri()
            except Exception as exc:  # pylint: disable=W0703
                logger.error("卡片信息请求失败 %s", str(exc))
        if name_card is None:  # 默认
            name_card = self.assets_service.namecard.navbar(0).as_uri()
        return name_card
