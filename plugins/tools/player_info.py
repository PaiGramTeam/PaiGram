from typing import TYPE_CHECKING, Optional

from core.dependence.assets import AssetsService
from core.plugin import Plugin
from core.services.players.services import PlayerInfoService, PlayersService
from metadata.genshin import AVATAR_DATA

if TYPE_CHECKING:
    from telegram import User


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

    async def get_player_info(self, player_id: int, user: "User"):
        player = await self.player_service.get(user.id, player_id)
        player_info = await self.player_info_service.get(player)
        nickname = user.full_name
        name_card: Optional[str] = None
        avatar: Optional[str] = None
        rarity: int = 5
        if player_info is not None:
            if player_info.nickname is not None:
                nickname = player_info.nickname
            if player_info.name_card is not None:
                name_card = (await self.assets_service.namecard(int(player_info.name_card)).navbar()).as_uri()
            if player_info.hand_image is not None:
                avatar = (await self.assets_service.avatar(player_info.hand_image).icon()).as_uri()
                rarity = {k: v["rank"] for k, v in AVATAR_DATA.items()}[str(player_info.hand_image)]
        if name_card is not None:  # 默认
            name_card = (await self.assets_service.namecard(210001).navbar()).as_uri()
        return name_card, avatar, nickname, rarity
