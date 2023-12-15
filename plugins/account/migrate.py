from typing import Optional, List

from core.services.players.services import PlayerInfoService
from gram_core.plugin.methods.migrate_data import IMigrateData
from gram_core.services.cookies import CookiesService
from gram_core.services.cookies.models import CookiesDataBase as Cookies
from gram_core.services.players import PlayersService
from gram_core.services.players.models import PlayersDataBase as Player, PlayerInfoSQLModel as PlayerInfo


class AccountMigrate(IMigrateData):
    old_user_id: int
    new_user_id: int
    players_service: PlayersService
    player_info_service: PlayerInfoService
    cookies_service: CookiesService
    need_migrate_player: List[Player]
    need_migrate_player_info: List[PlayerInfo]
    need_migrate_cookies: List[Cookies]

    async def migrate_data_msg(self) -> str:
        text = []
        if self.need_migrate_player:
            text.append(f"player 数据 {len(self.need_migrate_player)} 条")
        if self.need_migrate_player_info:
            text.append(f"player_info 数据 {len(self.need_migrate_player_info)} 条")
        if self.need_migrate_cookies:
            text.append(f"cookies 数据 {len(self.need_migrate_cookies)} 条")
        return "、".join(text)

    async def migrate_data(self) -> bool:
        for player in self.need_migrate_player:
            await self.players_service.update(player)
        for player_info in self.need_migrate_player_info:
            await self.player_info_service.update(player_info)
        for cookie in self.need_migrate_cookies:
            await self.cookies_service.update(cookie)
        return True

    @staticmethod
    async def create_players(
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
    ) -> List[Player]:
        players = await players_service.get_all_by_user_id(old_user_id)
        if not players:
            return []
        new_players = await players_service.get_all_by_user_id(new_user_id)
        new_players_index = [(p.account_id, p.player_id, p.region) for p in new_players]
        need_migrate = []
        for player in players:
            if (player.account_id, player.player_id, player.region) not in new_players_index:
                need_migrate.append(player)
        if not need_migrate:
            return []
        for i in need_migrate:
            i.user_id = new_user_id
            i.is_chosen = False
        return need_migrate

    @staticmethod
    async def create_players_info(
        old_user_id: int,
        new_user_id: int,
        player_info_service: PlayerInfoService,
    ) -> List[PlayerInfo]:
        players_info = await player_info_service.get_all_by_user_id(old_user_id)
        if not players_info:
            return []
        new_players_info = await player_info_service.get_all_by_user_id(new_user_id)
        new_players_info_index = [(p.user_id, p.player_id) for p in new_players_info]
        need_migrate = []
        for player in players_info:
            if (player.user_id, player.player_id) not in new_players_info_index:
                need_migrate.append(player)
        if not need_migrate:
            return []
        for i in need_migrate:
            i.user_id = new_user_id
        return need_migrate

    @staticmethod
    async def create_cookies(
        old_user_id: int,
        new_user_id: int,
        cookies_service: CookiesService,
    ) -> List[Cookies]:
        cookies = await cookies_service.get_all(old_user_id)
        if not cookies:
            return []
        new_cookies = await cookies_service.get_all(new_user_id)
        new_cookies_index = [(c.user_id, c.account_id, c.region) for c in new_cookies]
        need_migrate = []
        for cookie in cookies:
            if (cookie.user_id, cookie.account_id, cookie.region) not in new_cookies_index:
                need_migrate.append(cookie)
        if not need_migrate:
            return []
        for i in need_migrate:
            i.user_id = new_user_id
        return need_migrate

    @classmethod
    async def create(
        cls,
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
        player_info_service: PlayerInfoService,
        cookies_service: CookiesService,
    ) -> Optional["AccountMigrate"]:
        need_migrate_player = await cls.create_players(old_user_id, new_user_id, players_service)
        need_migrate_player_info = await cls.create_players_info(old_user_id, new_user_id, player_info_service)
        need_migrate_cookies = await cls.create_cookies(old_user_id, new_user_id, cookies_service)
        if not any([need_migrate_player, need_migrate_player_info, need_migrate_cookies]):
            return None
        self = cls()
        self.old_user_id = old_user_id
        self.new_user_id = new_user_id
        self.need_migrate_player = need_migrate_player
        self.need_migrate_player_info = need_migrate_player_info
        self.need_migrate_cookies = need_migrate_cookies
        return self
