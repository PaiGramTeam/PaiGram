import datetime
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import aiofiles
import contextlib
from genshin import Client, InvalidAuthkey
from genshin.models import BannerType
from pydantic import BaseModel

from utils.const import PROJECT_ROOT

GACHA_LOG_PATH = PROJECT_ROOT.joinpath("modules", "apihelper", "gacha_log")
GACHA_LOG_PATH.mkdir(parents=True, exist_ok=True)
GACHA_TYPE_LIST = {
    BannerType.NOVICE: '新手祈愿',
    BannerType.PERMANENT: '常驻祈愿',
    BannerType.WEAPON: '武器祈愿',
    BannerType.CHARACTER1: '角色祈愿',
    BannerType.CHARACTER2: '角色祈愿'
}


class FiveStarItem(BaseModel):
    name: str
    icon: str
    count: int
    type: str


class FourStarItem(BaseModel):
    name: str
    icon: str
    type: str
    num: Dict[str, int] = {
        '角色祈愿': 0,
        '武器祈愿': 0,
        '常驻祈愿': 0,
        '新手祈愿': 0}


class GachaItem(BaseModel):
    id: str
    name: str
    gacha_type: str
    item_type: str
    rank_type: str
    time: datetime.datetime


class GachaLogInfo(BaseModel):
    user_id: str
    uid: str
    update_time: datetime.datetime
    item_list: Dict[str, List[GachaItem]] = {
        '角色祈愿': [],
        '武器祈愿': [],
        '常驻祈愿': [],
        '新手祈愿': [],
    }


class GachaLog:
    @staticmethod
    async def load_json(path):
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            return json.loads(await f.read())

    @staticmethod
    async def save_json(path, data):
        async with aiofiles.open(path, 'w', encoding='utf-8') as f:
            if isinstance(data, dict):
                return await f.write(json.dumps(data, ensure_ascii=False, indent=4))
            await f.write(data)

    @staticmethod
    async def load_history_info(user_id: str, uid: str) -> Tuple[GachaLogInfo, bool]:
        """
        读取历史抽卡记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :return: 抽卡记录数据
        """
        file_path = GACHA_LOG_PATH / f'{user_id}-{uid}.json'
        if file_path.exists():
            return GachaLogInfo.parse_obj(await GachaLog.load_json(file_path)), True
        else:
            return GachaLogInfo(user_id=user_id,
                                uid=uid,
                                update_time=datetime.datetime.now()), False

    @staticmethod
    async def save_gacha_log_info(user_id: str, uid: str, info: GachaLogInfo):
        """
        保存抽卡记录数据
        :param user_id: 用户id
        :param uid: 原神uid
        :param info: 抽卡记录数据
        """
        save_path = GACHA_LOG_PATH / f'{user_id}-{uid}.json'
        save_path_bak = GACHA_LOG_PATH / f'{user_id}-{uid}.json.bak'
        # 将旧数据备份一次
        with contextlib.suppress(PermissionError):
            if save_path.exists():
                if save_path_bak.exists():
                    save_path_bak.unlink()
                save_path.rename(save_path.parent / f'{save_path.name}.bak')
        # 写入数据
        await GachaLog.save_json(save_path, info.json())

    @staticmethod
    async def gacha_log_to_uigf(user_id: str, uid: str) -> Tuple[bool, str, Optional[Path]]:
        data, state = await GachaLog.load_history_info(user_id, uid)
        if not state:
            return False, f'UID{uid} 还没有导入任何抽卡记录数据。', None
        save_path = GACHA_LOG_PATH / f'{user_id}-{uid}-uigf.json'
        uigf_dict = {
            'info': {
                'uid': uid,
                'lang': 'zh-cn',
                'export_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'export_timestamp': int(time.time()),
                'export_app': 'TGPaimonBot',
                'export_app_version': "v3",
                'uigf_version': 'v2.2'
            },
            'list': []
        }
        for items in data.item_list.values():
            for item in items:
                uigf_dict['list'].append({
                    'gacha_type': item.gacha_type,
                    'item_id': '',
                    'count': '1',
                    'time': item.time.strftime('%Y-%m-%d %H:%M:%S'),
                    'name': item.name,
                    'item_type': item.item_type,
                    'rank_type': item.rank_type,
                    'id': item.id,
                    'uigf_gacha_type': item.gacha_type
                })
        await GachaLog.save_json(save_path, uigf_dict)
        return True, '', save_path

    @staticmethod
    async def import_gacha_log_data(user_id: int, data: dict):
        new_num = 0
        try:
            uid = data['info']['uid']
            gacha_log, _ = await GachaLog.load_history_info(str(user_id), uid)
            for item in data['list']:
                pool_name = GACHA_TYPE_LIST[BannerType(int(item['gacha_type']))]
                item_info = GachaItem.parse_obj(item)
                if item_info not in gacha_log.item_list[pool_name]:
                    gacha_log.item_list[pool_name].append(item_info)
                    new_num += 1
            for i in gacha_log.item_list.values():
                i.sort(key=lambda x: (x.time, x.id))
            gacha_log.update_time = datetime.datetime.now()
            await GachaLog.save_gacha_log_info(str(user_id), uid, gacha_log)
            return "导入完成，本次没有新增数据" if new_num == 0 else f"导入完成，本次共新增{new_num}条抽卡记录"
        except Exception as e:
            breakpoint()
            return "导入失败，数据格式错误"

    @staticmethod
    async def get_gacha_log_data(user_id: int, client: Client, authkey: str) -> str:
        """
        使用authkey获取抽卡记录数据，并合并旧数据
        :param user_id: 用户id
        :param client: genshin client
        :param authkey: authkey
        :return: 更新结果
        """
        new_num = 0
        gacha_log, _ = await GachaLog.load_history_info(str(user_id), str(client.uid))
        try:
            for pool_id, pool_name in GACHA_TYPE_LIST.items():
                async for data in client.wish_history(pool_id, authkey=authkey):
                    item = GachaItem(
                        id=str(data.id),
                        name=data.name,
                        gacha_type=str(data.banner_type.value),
                        item_type=data.type,
                        rank_type=str(data.rarity),
                        time=datetime.datetime(data.time.year,
                                               data.time.month,
                                               data.time.day,
                                               data.time.hour,
                                               data.time.minute,
                                               data.time.second)
                    )

                    if item not in gacha_log.item_list[pool_name]:
                        gacha_log.item_list[pool_name].append(item)
                        new_num += 1
        except InvalidAuthkey:
            return "更新数据失败，authkey 无效"
        for i in gacha_log.item_list.values():
            i.sort(key=lambda x: (x.time, x.id))
        gacha_log.update_time = datetime.datetime.now()
        await GachaLog.save_gacha_log_info(str(user_id), str(client.uid), gacha_log)
        return '更新完成，本次没有新增数据' if new_num == 0 else f'更新完成，本次共新增{new_num}条抽卡记录'
