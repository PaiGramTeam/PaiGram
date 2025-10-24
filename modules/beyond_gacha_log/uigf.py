import ujson
from abc import abstractmethod
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

from modules.gacha_log.models import ImportType, UIGFInfo
from modules.beyond_gacha_log.models import UIGFListInfo, UIGFModel

if TYPE_CHECKING:
    from modules.beyond_gacha_log.models import BeyondGachaLogInfo


class BeyondGachaLogUigfConverter:
    """抽卡记录导出为 uigf 标准"""

    gacha_log_path: Path

    @staticmethod
    @abstractmethod
    async def load_json(path):
        """加载json文件"""

    @staticmethod
    @abstractmethod
    async def save_json(path, data):
        """保存json文件"""

    @abstractmethod
    async def load_history_info(
        self, user_id: str, uid: str, only_status: bool = False
    ) -> Tuple[Optional["BeyondGachaLogInfo"], bool]:
        """读取历史抽卡记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :param only_status: 是否只读取状态
        :return: 抽卡记录数据
        """

    async def gacha_log_to_uigf(self, user_id: str, uid: str, append_path: "Path") -> Optional[Path]:
        """抽卡记录转换为 UIGF 格式
        :param user_id: 用户ID
        :param uid: 游戏UID
        :param append_path: 追加路径
        :return: 转换是否成功、转换信息、UIGF文件目录
        """
        data, state = await self.load_history_info(user_id, uid)
        if not state:
            return None
        i = UIGFInfo(export_app=ImportType.PaiGram.value, export_app_version="v4")
        list_info = UIGFListInfo(uid=int(uid), list=[])
        info = UIGFModel(info=i, hk4e_beyond=[list_info])
        for items in data.item_list.values():
            list_info.list.extend(items)

        if append_path:
            save_path = append_path
            info = await self.load_json(append_path)
            info["hk4e_beyond"] = [ujson.loads(list_info.model_dump_json())]
            await self.save_json(save_path, info)
        else:
            save_path = self.gacha_log_path / f"{user_id}-{uid}-uigf.json"
            await self.save_json(save_path, ujson.loads(info.model_dump_json()))

        return save_path
