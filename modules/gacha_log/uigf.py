import ujson
from abc import abstractmethod
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

from metadata.shortname import roleToId, weaponToId
from modules.gacha_log.error import GachaLogNotFound
from modules.gacha_log.models import UIGFModel, UIGFInfo, ImportType, UIGFListInfo, UIGFItem

if TYPE_CHECKING:
    from modules.gacha_log.models import GachaLogInfo


class GachaLogUigfConverter:
    """抽卡记录导出为 uigf 标准"""

    gacha_log_path: Path

    @staticmethod
    @abstractmethod
    async def save_json(path, data):
        """保存json文件"""

    @abstractmethod
    async def load_history_info(
        self, user_id: str, uid: str, only_status: bool = False
    ) -> Tuple[Optional["GachaLogInfo"], bool]:
        """读取历史抽卡记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :param only_status: 是否只读取状态
        :return: 抽卡记录数据
        """

    async def gacha_log_to_uigf(self, user_id: str, uid: str) -> Optional[Path]:
        """抽卡记录转换为 UIGF 格式
        :param user_id: 用户ID
        :param uid: 游戏UID
        :return: 转换是否成功、转换信息、UIGF文件目录
        """
        data, state = await self.load_history_info(user_id, uid)
        if not state:
            raise GachaLogNotFound
        save_path = self.gacha_log_path / f"{user_id}-{uid}-uigf.json"
        i = UIGFInfo(export_app=ImportType.PaiGram.value, export_app_version="v4")
        list_info = UIGFListInfo(uid=int(uid), list=[])
        info = UIGFModel(info=i, hk4e=[list_info], hkrpg=[], nap=[])
        for items in data.item_list.values():
            for item in items:
                list_info.list.append(
                    UIGFItem(
                        id=item.id,
                        name=item.name,
                        gacha_type=item.gacha_type,
                        item_id=roleToId(item.name) if item.item_type == "角色" else weaponToId(item.name),
                        item_type=item.item_type,
                        rank_type=item.rank_type,
                        time=item.time.strftime("%Y-%m-%d %H:%M:%S"),
                        uigf_gacha_type=item.gacha_type if item.gacha_type != "400" else "301",
                    )
                )
        await self.save_json(save_path, ujson.loads(info.model_dump_json()))
        return save_path
