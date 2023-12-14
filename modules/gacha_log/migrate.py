from typing import Optional, List

from gram_core.plugin.methods.migrate_data import IMigrateData
from gram_core.services.players import PlayersService
from modules.gacha_log.log import GachaLog


class GachaLogMigrate(IMigrateData, GachaLog):
    old_user_id: int
    new_user_id: int
    old_uid_list: List[int]

    async def migrate_data_msg(self) -> str:
        return f"{len(self.old_uid_list)} 个账号的抽卡数据"

    async def migrate_data(self) -> bool:
        for uid in self.old_uid_list:
            if not await self.move_history_info(str(self.old_user_id), str(uid), str(self.new_user_id)):
                return False
        return True

    @classmethod
    async def create(
        cls,
        old_user_id: int,
        new_user_id: int,
        players_service: PlayersService,
    ) -> Optional["GachaLogMigrate"]:
        players = await players_service.get_all_by_user_id(old_user_id)
        if not players:
            return None
        _uid_list = [player.player_id for player in players if player and player.player_id]
        if not _uid_list:
            return None
        self = cls()
        old_uid_list = []
        for uid in _uid_list:
            _, status = await self.load_history_info(str(old_user_id), str(uid), True)
            if status:
                old_uid_list.append(uid)
        if not old_uid_list:
            return None
        self.old_user_id = old_user_id
        self.new_user_id = new_user_id
        self.old_uid_list = old_uid_list
        return self
