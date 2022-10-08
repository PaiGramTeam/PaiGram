import contextlib
import datetime
import json
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union

import aiofiles
from genshin import Client, InvalidAuthkey
from genshin.models import BannerType
from pydantic import BaseModel

from core.base.assets import AssetsService
from metadata.pool.pool import get_pool_by_id
from metadata.shortname import roleToId, weaponToId
from utils.const import PROJECT_ROOT

GACHA_LOG_PATH = PROJECT_ROOT.joinpath("data", "apihelper", "gacha_log")
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
    isUp: bool
    isBig: bool
    time: datetime.datetime


class FourStarItem(BaseModel):
    name: str
    icon: str
    count: int
    type: str
    time: datetime.datetime


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


class Pool:
    def __init__(self, five: List[str], four: List[str], name: str, to: str, **kwargs):
        self.five = five
        self.real_name = name
        self.name = "、".join(self.five)
        self.four = four
        self.from_ = kwargs.get("from")
        self.to = to
        self.from_time = datetime.datetime.strptime(self.from_, "%Y-%m-%d %H:%M:%S")
        self.to_time = datetime.datetime.strptime(self.to, "%Y-%m-%d %H:%M:%S")
        self.start = self.from_time
        self.start_init = False
        self.end = self.to_time
        self.dict = {}
        self.count = 0

    def parse(self, item: Union[FiveStarItem, FourStarItem]):
        if self.from_time <= item.time <= self.to_time:
            if self.dict.get(item.name):
                self.dict[item.name]["count"] += 1
            else:
                self.dict[item.name] = {
                    "name": item.name,
                    "icon": item.icon,
                    "count": 1,
                    "rank_type": 5 if isinstance(item, FiveStarItem) else 4,
                }

    def count_item(self, item: List[GachaItem]):
        for i in item:
            if self.from_time <= i.time <= self.to_time:
                self.count += 1
                if not self.start_init:
                    self.start = i.time
                self.end = i.time

    def to_list(self):
        return list(self.dict.values())


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
        """读取历史抽卡记录数据
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
        """保存抽卡记录数据
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
        """抽卡日记转换为 UIGF 格式
        :param user_id: 用户ID
        :param uid: 游戏UID
        :return: 转换是否成功、转换信息、UIGF文件目录
        """
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
        except Exception:
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

    @staticmethod
    def check_avatar_up(name: str, gacha_time: datetime.datetime) -> bool:
        if name in {'莫娜', '七七', '迪卢克', '琴'}:
            return False
        elif name == "刻晴":
            start_time = datetime.datetime.strptime("2021-02-17 18:00:00", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.strptime("2021-03-02 15:59:59", "%Y-%m-%d %H:%M:%S")
            if not (start_time < gacha_time < end_time):
                return False
        elif name == "提纳里":
            start_time = datetime.datetime.strptime("2022-08-24 06:00:00", "%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.strptime("2022-09-09 17:59:59", "%Y-%m-%d %H:%M:%S")
            if not (start_time < gacha_time < end_time):
                return False
        return True

    @staticmethod
    async def get_all_5_star_items(data: List[GachaItem], assets: AssetsService, pool_name: str = "角色祈愿"):
        """
        获取所有5星角色
        :param data: 抽卡记录
        :param assets: 资源服务
        :param pool_name: 池子名称
        :return: 5星角色列表
        """
        count = 0
        result = []
        for item in data:
            count += 1
            if item.rank_type == '5':
                if item.item_type == "角色" and pool_name in {"角色祈愿", "常驻祈愿"}:
                    result.append(
                        FiveStarItem(
                            name=item.name,
                            icon=(await assets.avatar(roleToId(item.name)).icon()).as_uri(),
                            count=count,
                            type="角色",
                            isUp=GachaLog.check_avatar_up(item.name, item.time) if pool_name == "角色祈愿" else False,
                            isBig=(not result[-1].isUp) if result and pool_name == "角色祈愿" else False,
                            time=item.time,
                        )
                    )
                elif item.item_type == "武器" and pool_name in {"武器祈愿", "常驻祈愿"}:
                    result.append(
                        FiveStarItem(
                            name=item.name,
                            icon=(await assets.weapon(weaponToId(item.name)).icon()).as_uri(),
                            count=count,
                            type="武器",
                            isUp=False,
                            isBig=False,
                            time=item.time,
                        )
                    )
                count = 0
        result.reverse()
        return result, count

    @staticmethod
    async def get_all_4_star_items(data: List[GachaItem], assets: AssetsService):
        """
        获取 no_fout_star
        :param data: 抽卡记录
        :param assets: 资源服务
        :return: no_fout_star
        """
        count = 0
        result = []
        for item in data:
            count += 1
            if item.rank_type == '4':
                if item.item_type == "角色":
                    result.append(
                        FourStarItem(
                            name=item.name,
                            icon=(await assets.avatar(roleToId(item.name)).icon()).as_uri(),
                            count=count,
                            type="角色",
                            time=item.time,
                        )
                    )
                elif item.item_type == "武器":
                    result.append(
                        FourStarItem(
                            name=item.name,
                            icon=(await assets.weapon(weaponToId(item.name)).icon()).as_uri(),
                            count=count,
                            type="武器",
                            time=item.time,
                        )
                    )
                count = 0
        result.reverse()
        return result, count

    @staticmethod
    def get_301_pool_data(total: int,
                          all_five: List[FiveStarItem],
                          no_five_star: int,
                          no_four_star: int):
        # 总共五星
        five_star = len(all_five)
        five_star_up = len([i for i in all_five if i.isUp])
        five_star_big = len([i for i in all_five if i.isBig])
        # 五星平均
        five_star_avg = round(total / five_star, 2) if five_star != 0 else 0
        # 小保底不歪
        small_protect = round((five_star_up - five_star_big) / (five_star - five_star_big) * 100.0, 1) if \
            five_star - five_star_big != 0 else "0.0"
        # 五星常驻
        five_star_const = five_star - five_star_up
        # UP 平均
        up_avg = round(total / five_star_up, 2) if five_star_up != 0 else 0
        # UP 花费原石
        up_cost = sum(i.count * 160 for i in all_five if i.isUp)
        up_cost = f"{round(up_cost / 10000, 2)}w" if up_cost >= 10000 else up_cost
        return [
            [
                {"num": no_five_star, "unit": "抽", "lable": "未出五星"},
                {"num": five_star, "unit": "个", "lable": "五星"},
                {"num": five_star_avg, "unit": "抽", "lable": "五星平均"},
                {"num": small_protect, "unit": "%", "lable": "小保底不歪"},
            ],
            [
                {"num": no_four_star, "unit": "抽", "lable": "未出四星"},
                {"num": five_star_const, "unit": "个", "lable": "五星常驻"},
                {"num": up_avg, "unit": "抽", "lable": "UP平均"},
                {"num": up_cost, "unit": "", "lable": "UP花费原石"},
            ]
        ]

    @staticmethod
    def get_200_pool_data(total: int, all_five: List[FiveStarItem], all_four: List[FourStarItem],
                          no_five_star: int, no_four_star: int):
        # 总共五星
        five_star = len(all_five)
        # 五星平均
        five_star_avg = round(total / five_star, 2) if five_star != 0 else 0
        # 五星武器
        five_star_weapon = len([i for i in all_five if i.type == "武器"])
        # 总共四星
        four_star = len(all_four)
        # 四星平均
        four_star_avg = round(total / four_star, 2) if four_star != 0 else 0
        # 四星最多
        four_star_name_list = [i.name for i in all_four]
        four_star_max = max(four_star_name_list, key=four_star_name_list.count)
        four_star_max_count = four_star_name_list.count(four_star_max)
        return [
            [
                {"num": no_five_star, "unit": "抽", "lable": "未出五星"},
                {"num": five_star, "unit": "个", "lable": "五星"},
                {"num": five_star_avg, "unit": "抽", "lable": "五星平均"},
                {"num": five_star_weapon, "unit": "个", "lable": "五星武器"},
            ],
            [
                {"num": no_four_star, "unit": "抽", "lable": "未出四星"},
                {"num": four_star, "unit": "个", "lable": "四星"},
                {"num": four_star_avg, "unit": "抽", "lable": "四星平均"},
                {"num": four_star_max_count, "unit": four_star_max, "lable": "四星最多"},
            ]
        ]

    @staticmethod
    def get_302_pool_data(total: int, all_five: List[FiveStarItem], all_four: List[FourStarItem],
                          no_five_star: int, no_four_star: int):
        # 总共五星
        five_star = len(all_five)
        # 五星平均
        five_star_avg = round(total / five_star, 2) if five_star != 0 else 0
        # 四星武器
        four_star_weapon = len([i for i in all_four if i.type == "武器"])
        # 总共四星
        four_star = len(all_four)
        # 四星平均
        four_star_avg = round(total / four_star, 2) if four_star != 0 else 0
        # 四星最多
        four_star_name_list = [i.name for i in all_four]
        four_star_max = max(four_star_name_list, key=four_star_name_list.count)
        four_star_max_count = four_star_name_list.count(four_star_max)
        return [
            [
                {"num": no_five_star, "unit": "抽", "lable": "未出五星"},
                {"num": five_star, "unit": "个", "lable": "五星"},
                {"num": five_star_avg, "unit": "抽", "lable": "五星平均"},
                {"num": four_star_weapon, "unit": "个", "lable": "四星武器"},
            ],
            [
                {"num": no_four_star, "unit": "抽", "lable": "未出四星"},
                {"num": four_star, "unit": "个", "lable": "四星"},
                {"num": four_star_avg, "unit": "抽", "lable": "四星平均"},
                {"num": four_star_max_count, "unit": four_star_max, "lable": "四星最多"},
            ]
        ]

    @staticmethod
    async def get_analysis(user_id: int, client: Client, pool: BannerType, assets: AssetsService):
        """
        获取抽卡记录分析数据
        :param user_id: 用户id
        :param client: genshin client
        :param pool: 池子类型
        :param assets: 资源服务
        :return: 分析数据
        """
        gacha_log, status = await GachaLog.load_history_info(str(user_id), str(client.uid))
        if not status:
            return "获取数据失败，未找到抽卡记录"
        pool_name = GACHA_TYPE_LIST[pool]
        data = gacha_log.item_list[pool_name]
        total = len(data)
        if total == 0:
            return "获取数据失败，未找到抽卡记录"
        all_five, no_five_star = await GachaLog.get_all_5_star_items(data, assets, pool_name)
        all_four, no_four_star = await GachaLog.get_all_4_star_items(data, assets)
        summon_data = None
        if pool == BannerType.CHARACTER1:
            summon_data = GachaLog.get_301_pool_data(total, all_five, no_five_star, no_four_star)
        elif pool == BannerType.WEAPON:
            summon_data = GachaLog.get_302_pool_data(total, all_five, all_four, no_five_star, no_four_star)
        elif pool == BannerType.PERMANENT:
            summon_data = GachaLog.get_200_pool_data(total, all_five, all_four, no_five_star, no_four_star)
        last_time = data[0].time.strftime("%Y-%m-%d %H:%M")
        first_time = data[-1].time.strftime("%Y-%m-%d %H:%M")
        return {
            "uid": client.uid,
            "allNum": total,
            "type": pool.value,
            "typeName": pool_name,
            "line": summon_data,
            "firstTime": first_time,
            "lastTime": last_time,
            "fiveLog": all_five,
            "fourLog": all_four[:18],
        }

    @staticmethod
    async def get_pool_analysis(user_id: int, client: Client, pool: BannerType, assets: AssetsService, group: bool):
        """
        获取抽卡记录分析数据
        :param user_id: 用户id
        :param client: genshin client
        :param pool: 池子类型
        :param assets: 资源服务
        :param group: 是否群组
        :return: 分析数据
        """
        gacha_log, status = await GachaLog.load_history_info(str(user_id), str(client.uid))
        if not status:
            return "获取数据失败，未找到抽卡记录"
        pool_name = GACHA_TYPE_LIST[pool]
        data = gacha_log.item_list[pool_name]
        total = len(data)
        if total == 0:
            return "获取数据失败，未找到抽卡记录"
        all_five, _ = await GachaLog.get_all_5_star_items(data, assets, pool_name)
        all_four, _ = await GachaLog.get_all_4_star_items(data, assets)
        pool_data = []
        up_pool_data = [Pool(**i) for i in get_pool_by_id(pool.value)]
        for up_pool in up_pool_data:
            for item in all_five:
                up_pool.parse(item)
            for item in all_four:
                up_pool.parse(item)
            up_pool.count_item(data)
        for up_pool in up_pool_data:
            pool_data.append({
                "count": up_pool.count,
                "list": up_pool.to_list(),
                "name": up_pool.name,
                "start": up_pool.start.strftime("%Y-%m-%d"),
                "end": up_pool.end.strftime("%Y-%m-%d"),
            })
        pool_data = [i for i in pool_data if i["count"] > 0]
        return {
            "uid": client.uid,
            "typeName": pool_name,
            "pool": pool_data[:6] if group else pool_data,
            "hasMore": len(pool_data) > 6,
        }
