import re
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Union, TYPE_CHECKING

from httpx import AsyncClient

from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToId
from modules.apihelper.client.components.remote import Remote
from modules.apihelper.models.genshin.calendar import Date, FinalAct, ActEnum, ActDetail, ActTime, BirthChar
from modules.wiki.character import Character


if TYPE_CHECKING:
    from core.dependence.assets import AssetsService


class Calendar:
    """原神活动日历"""

    ANNOUNCEMENT_LIST = "https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnList"
    ANNOUNCEMENT_CONTENT = "https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnContent"
    ANNOUNCEMENT_PARAMS = {
        "game": "hk4e",
        "game_biz": "hk4e_cn",
        "lang": "zh-cn",
        "bundle_id": "hk4e_cn",
        "platform": "pc",
        "region": "cn_gf01",
        "level": "55",
        "uid": "100000000",
    }
    MIAO_API = "http://miaoapi.cn/api/calendar"
    IGNORE_IDS = [
        495,  # 有奖问卷调查开启！
        1263,  # 米游社《原神》专属工具一览
        423,  # 《原神》玩家社区一览
        422,  # 《原神》防沉迷系统说明
        762,  # 《原神》公平运营声明
        762,  # 《原神》公平运营声明
    ]
    IGNORE_RE = re.compile(r"(内容专题页|版本更新说明|调研|防沉迷|米游社|专项意见|更新修复与优化|问卷调查|版本更新通知|更新时间说明|预下载功能|周边限时|周边上新|角色演示)")
    FULL_TIME_RE = re.compile(r"(魔神任务)")

    def __init__(self):
        self.client = AsyncClient()

    @staticmethod
    async def async_gen_birthday_list() -> Dict[str, List[str]]:
        """生成生日列表并且合并云端生日列表"""
        birthday_list = Calendar.gen_birthday_list()
        remote_data = await Remote.get_remote_birthday()
        if remote_data:
            birthday_list.update(remote_data)
        return birthday_list

    @staticmethod
    def gen_birthday_list() -> Dict[str, List[str]]:
        """生成生日列表"""
        birthday_list = {}
        for value in AVATAR_DATA.values():
            key = "_".join([str(i) for i in value["birthday"]])
            data = birthday_list.get(key, [])
            data.append(value["name"])
            birthday_list[key] = data
        return birthday_list

    @staticmethod
    def get_now_hour() -> datetime:
        """获取当前时间"""
        return datetime.now().replace(minute=0, second=0, microsecond=0)

    async def parse_official_content_date(self) -> Dict[str, ActTime]:
        """解析官方内容时间"""
        time_map = {}
        req = await self.client.get(self.ANNOUNCEMENT_CONTENT, params=self.ANNOUNCEMENT_PARAMS)
        if req.status_code != 200:
            return time_map
        detail_data = req.json()
        for data in detail_data.get("data", {}).get("list", []):
            ann_id = data.get("ann_id", 0)
            title = data.get("title", "")
            content = data.get("content", "")
            if ann_id in self.IGNORE_IDS or self.IGNORE_RE.findall(title):
                continue
            content = re.sub(r'(<|&lt;)[\w "%:;=\-\\/\\(\\),\\.]+(>|&gt;)', "", content)
            try:
                if reg_ret := re.search(r"(?:活动时间|祈愿介绍|任务开放时间|冒险....包|折扣时间)\s*〓([^〓]+)(〓|$)", content):
                    if time_ret := re.search(r"(?:活动时间)?(?:〓|\s)*([0-9\\/\\: ~]{6,})", reg_ret[1]):
                        start_time, end_time = time_ret[1].split("~")
                        start_time = start_time.replace("/", "-").strip()
                        end_time = end_time.replace("/", "-").strip()
                        time_map[str(ann_id)] = ActTime(
                            title=title,
                            start=start_time,
                            end=end_time,
                        )
            except (IndexError, ValueError):
                continue
        return time_map

    async def req_cal_data(self) -> Tuple[List[List[ActDetail]], Dict[str, ActTime]]:
        """请求日历数据"""
        list_data = await self.client.get(self.ANNOUNCEMENT_LIST, params=self.ANNOUNCEMENT_PARAMS)
        list_data = list_data.json()

        new_list_data = [[], []]
        for idx, data in enumerate(list_data.get("data", {}).get("list", [])):
            for item in data.get("list", []):
                new_list_data[idx].append(ActDetail(**item))
        time_map = {}
        time_map.update(await self.parse_official_content_date())
        req = await self.client.get(self.MIAO_API)
        if req.status_code == 200:
            miao_data = req.json()
            time_map.update({key: ActTime(**value) for key, value in miao_data.get("data", {}).items()})
        remote_data = await Remote.get_remote_calendar()
        if remote_data:
            time_map.update({key: ActTime(**value) for key, value in remote_data.get("data", {}).items()})
        return new_list_data, time_map

    @staticmethod
    def date_to_weekday(date_: datetime) -> str:
        """日期转换为星期"""
        time = ["一", "二", "三", "四", "五", "六", "日"]
        return time[date_.weekday()]

    async def get_date_list(self) -> Tuple[List[Date], datetime, datetime, timedelta, float]:
        """获取日历数据"""
        data_list: List[Date] = []
        today = self.get_now_hour()
        temp = today - timedelta(days=7)
        month = 0
        date, week, is_today = [], [], []
        start_date, end_date = None, None
        for i in range(13):
            temp += timedelta(days=1)
            m, d, w = temp.month, temp.day, self.date_to_weekday(temp)
            if month == 0:
                start_date = temp
                month = m
            if month != m and len(date) > 0:
                data_list.append(Date(month=month, date=date, week=week, is_today=is_today))
                date, week, is_today = [], [], []
                month = m
            date.append(d)
            week.append(w)
            is_today.append(temp == today)
            if i == 12:
                data_list.append(Date(month=month, date=date, week=week, is_today=is_today))
                end_date = temp
        start_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        total_range: timedelta = end_time - start_time
        now_left: float = (self.get_now_hour() - start_time) / total_range * 100
        return (
            data_list,
            start_time,
            end_time,
            total_range,
            now_left,
        )

    @staticmethod
    def human_read(d: timedelta) -> str:
        """将日期转换为人类可读"""
        hour = d.seconds // 3600
        minute = d.seconds // 60 % 60
        if minute >= 59:
            hour += 1
        text = ""
        if d.days:
            text += f"{d.days}天"
        if hour:
            text += f"{hour}小时"
        return text

    @staticmethod
    def count_width(
        act: FinalAct,
        detail: Optional[ActTime],
        ds: ActDetail,
        start_time: datetime,
        end_time: datetime,
        total_range: timedelta,
    ) -> Tuple[datetime, datetime]:
        """计算宽度"""

        def get_date(d1: str, d2: str) -> datetime:
            if d1 and len(d1) > 6:
                return datetime.strptime(d1, "%Y-%m-%d %H:%M:%S")
            return datetime.strptime(d2, "%Y-%m-%d %H:%M:%S")

        s_date = get_date(detail and detail.start, ds.start_time)
        e_date = get_date(detail and detail.end, ds.end_time)
        s_time = max(s_date, start_time)
        e_time = min(e_date, end_time)

        s_range = s_time - start_time
        e_range = e_time - start_time

        act.left = s_range / total_range * 100
        act.width = e_range / total_range * 100 - act.left
        act.duration = (e_time - s_time).total_seconds()
        act.start = s_date.strftime("%m-%d %H:%M")
        act.end = e_date.strftime("%m-%d %H:%M")
        return s_date, e_date

    def parse_label(self, act: FinalAct, is_act: bool, s_date: datetime, e_date: datetime) -> None:
        """解析活动标签"""
        now = self.get_now_hour()
        label = ""
        if self.FULL_TIME_RE.findall(act.title) or e_date - s_date > timedelta(days=365):
            label = f"{s_date.strftime('%m-%d %H:%M')} 后永久有效" if s_date < now else "永久有效"
        elif s_date < now < e_date:
            label = f'{e_date.strftime("%m-%d %H:%M")} ({self.human_read(e_date - now)}后结束)'
            if act.width > (38 if is_act else 55):
                label = f"{s_date.strftime('%m-%d %H:%M')} ~ {label}"
        elif s_date > now:
            label = f'{s_date.strftime("%m-%d %H:%M")} ({self.human_read(s_date - now)}后开始)'
        elif is_act:
            label = f"{s_date.strftime('%m-%d %H:%M')} ~ {e_date.strftime('%m-%d %H:%M')}"
        act.label = label

    @staticmethod
    async def parse_type(act: FinalAct, assets: "AssetsService") -> None:
        """解析活动类型"""
        if "神铸赋形" in act.title:
            act.type = ActEnum.weapon
            act.title = re.sub(r"(单手剑|双手剑|长柄武器|弓|法器|·)", "", act.title)
            act.sort = 2
        elif "祈愿" in act.title:
            act.type = ActEnum.character
            if reg_ret := re.search(r"·(.*)\(", act.title):
                char_name = reg_ret[1]
                char = assets.avatar(roleToId(char_name))
                act.banner = (await assets.namecard(char.id).navbar()).as_uri()
                act.face = (await char.icon()).as_uri()
                act.sort = 1
        elif "纪行" in act.title:
            act.type = ActEnum.no_display
        elif act.title == "深渊":
            act.type = ActEnum.abyss

    async def get_list(
        self,
        ds: ActDetail,
        start_time: datetime,
        end_time: datetime,
        total_range: timedelta,
        time_map: Dict[str, ActTime],
        is_act: bool,
        assets: "AssetsService",
    ) -> Optional[FinalAct]:
        """获取活动列表"""
        act = FinalAct(
            id=ds.ann_id,
            type=ActEnum.activity if is_act else ActEnum.normal,
            title=ds.title,
            banner=ds.banner if is_act else "",
            sort=5 if is_act else 10,
            icon=ds.tag_icon,
        )
        detail: Optional[ActTime] = time_map.get(str(act.id))

        if act.id in self.IGNORE_IDS or self.IGNORE_RE.findall(act.title) or (detail and not detail.display):
            return None
        await self.parse_type(act, assets)
        s_date, e_date = self.count_width(act, detail, ds, start_time, end_time, total_range)
        self.parse_label(act, is_act, s_date, e_date)

        if s_date <= end_time and e_date >= start_time:
            act.mergeStatus = 1 if act.type in {ActEnum.activity, ActEnum.normal} else 0
            return act

    @staticmethod
    def get_abyss_cal(start_time: datetime, end_time: datetime) -> List[List[Union[datetime, str]]]:
        """获取深渊日历"""
        last = datetime.now().replace(day=1) - timedelta(days=2)
        last_month = last.month
        curr = datetime.now()
        curr_month = curr.month
        next_date = last + timedelta(days=40)
        next_month = next_date.month

        def start(date: datetime, up: bool = False):
            return date.replace(day=1 if up else 16, hour=4, minute=0, second=0, microsecond=0)

        def end(date: datetime, up: bool = False):
            return date.replace(day=1 if up else 16, hour=3, minute=59, second=59, microsecond=999999)

        check = [
            [start(last, False), end(last, True), f"{last_month}月下半"],
            [start(curr, True), end(curr, False), f"{curr_month}月上半"],
            [start(curr, False), end(next_date, True), f"{curr_month}月下半"],
            [start(next_date, True), end(next_date, False), f"{next_month}月上半"],
        ]
        ret = []
        for ds in check:
            s, e, _ = ds
            if (s <= start_time <= e) or (s <= end_time <= e):
                ret.append(ds)
        return ret

    async def get_birthday_char(
        self, date_list: List[Date], assets: "AssetsService"
    ) -> Tuple[int, Dict[str, Dict[str, List[BirthChar]]]]:
        """获取生日角色"""
        birthday_list = await self.async_gen_birthday_list()
        birthday_char_line = 0
        birthday_chars = {}
        for date in date_list:
            birthday_chars[str(date.month)] = {}
            for d in date.date:
                key = f"{date.month}_{d}"
                if char := birthday_list.get(key):
                    birthday_char_line = max(len(char), birthday_char_line)
                    birthday_chars[str(date.month)][str(d)] = []
                    for c in char:
                        character = await Character.get_by_name(c)
                        birthday_chars[str(date.month)][str(d)].append(
                            BirthChar(
                                name=c,
                                star=character.rarity,
                                icon=(await assets.avatar(roleToId(c)).icon()).as_uri(),
                            )
                        )
        return birthday_char_line, birthday_chars

    @staticmethod
    def get_merge_next(target: List[FinalAct], li: FinalAct) -> Optional[FinalAct]:
        """获取下一个可以合并的活动"""
        return next(
            (li2 for li2 in target if (li2.mergeStatus == 1) and (li.left + li.width <= li2.left)),
            None,
        )

    def merge_list(self, target: List[FinalAct]) -> Tuple[List[List[FinalAct]], int, int]:
        """将两个活动合并为一行"""
        char_count = 0
        char_old = 0
        ret: List[List[FinalAct]] = []
        for idx, li in enumerate(target):
            if li.type == ActEnum.character:
                char_count += 1
                if li.left == 0:
                    char_old += 1
                li.idx = char_count
            if li.mergeStatus == 1:
                if li2 := self.get_merge_next(target[idx + 1 :], li):
                    li.mergeStatus = 2
                    li2.mergeStatus = 2
                    ret.append([li, li2])
            if li.mergeStatus != 2:
                li.mergeStatus = 2
                ret.append([li])
        return ret, char_count, char_old

    async def get_photo_data(self, assets: "AssetsService") -> Dict:
        """获取数据"""
        now = self.get_now_hour()
        list_data, time_map = await self.req_cal_data()
        (
            date_list,
            start_time,
            end_time,
            total_range,
            now_left,
        ) = await self.get_date_list()
        birthday_char_line, birthday_chars = await self.get_birthday_char(date_list, assets)
        target: List[FinalAct] = []
        abyss: List[FinalAct] = []

        for ds in list_data[1]:
            if act := await self.get_list(ds, start_time, end_time, total_range, time_map, True, assets):
                target.append(act)
        for ds in list_data[0]:
            if act := await self.get_list(ds, start_time, end_time, total_range, time_map, False, assets):
                target.append(act)
        abyss_cal = self.get_abyss_cal(start_time, end_time)
        for t in abyss_cal:
            ds = ActDetail(
                title=f"「深境螺旋」· {t[2]}",
                start_time=t[0].strftime("%Y-%m-%d %H:%M:%S"),
                end_time=t[1].strftime("%Y-%m-%d %H:%M:%S"),
            )
            if act := await self.get_list(ds, start_time, end_time, total_range, {}, True, assets):
                abyss.append(act)
        target.sort(key=lambda x: (x.sort, x.start, x.duration))
        target, char_count, char_old = self.merge_list(target)
        return {
            "date_list": date_list,
            "now_left": now_left,
            "list": target,
            "abyss": abyss,
            "char_mode": f"char-{char_count}-{char_old}",
            "now_time": now.strftime("%Y-%m-%d %H 时"),
            "birthday_char_line": birthday_char_line,
            "birthday_chars": birthday_chars,
        }
