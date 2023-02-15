import re

from datetime import datetime, timedelta
from httpx import AsyncClient

from core.base.assets import AssetsService
from metadata.shortname import roleToId


class Calendar:
    ANNOUNCEMENT_LIST = (
        "https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnList"
        "?game=hk4e&game_biz=hk4e_cn&lang=zh-cn&bundle_id=hk4e_cn&platform=pc&"
        "region=cn_gf01&level=55&uid=100000000"
    )
    ANNOUNCEMENT_DETAIL = (
        "https://hk4e-api.mihoyo.com/common/hk4e_cn/announcement/api/getAnnContent"
        "?game=hk4e&game_biz=hk4e_cn&lang=zh-cn&bundle_id=hk4e_cn&platform=pc&"
        "region=cn_gf01&level=55&uid=100000000"
    )
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

    async def reqCalData(self):
        list_data = await self.client.get(self.ANNOUNCEMENT_LIST)
        list_data = list_data.json()

        req = await self.client.get(self.MIAO_API)
        miao_data = req.json()
        time_map = dict(miao_data["data"].items())
        return list_data, time_map

    async def getDateList(self):
        def weekday(date_: datetime):
            time = ["一", "二", "三", "四", "五", "六", "日"]
            return time[date_.weekday()]

        data_list = []
        month = 0
        date = []
        week = []
        is_today = []
        today = datetime.now()
        temp = today - timedelta(days=7)
        start_date = temp
        end_date = today
        for i in range(13):
            temp += timedelta(days=1)
            m = temp.month
            d = temp.day
            w = weekday(temp)
            if month == 0:
                start_date = temp
                month = m
            if month != m and len(date) > 0:
                data_list.append(
                    {
                        "month": month,
                        "date": date,
                        "week": week,
                        "is_today": is_today,
                    }
                )
                date = []
                week = []
                month = m
            date.append(d)
            week.append(w)
            is_today.append(temp.date() == today.date())
            if i == 12:
                data_list.append(
                    {
                        "month": month,
                        "date": date,
                        "week": week,
                        "is_today": is_today,
                    }
                )
                end_date = temp
        start_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        total_range = end_time - start_time
        now_left = (datetime.now() - start_time) / total_range * 100
        return (
            data_list,
            start_time,
            end_time,
            total_range,
            now_left,
        )

    async def get_list(
        self,
        ds,
        target,
        start_time,
        end_time,
        total_range,
        now,
        time_map,
        is_act: bool,
        assets: AssetsService,
    ):
        an_type = "activity" if is_act else "normal"
        an_id = ds.get("ann_id", 0)
        an_title = ds["title"]
        an_banner = ds.get("banner", "") if is_act else ""
        extra = {
            "sort": 5 if is_act else 10,
        }
        detail = time_map.get(str(an_id), {})

        if an_id in self.IGNORE_IDS or self.IGNORE_RE.findall(an_title) or detail.get("display", False):
            return

        if "神铸赋形" in an_title:
            an_type = "weapon"
            an_title = re.sub(r"(单手剑|双手剑|长柄武器|弓|法器|·)", "", an_title)
            extra["sort"] = 2
        elif "祈愿" in an_title:
            an_type = "character"
            reg_ret = re.search(r"·(.*)\(", an_title)
            if reg_ret:
                char_name = reg_ret[1]
                char = assets.avatar(roleToId(char_name))
                # extra["banner2"] = (await assets.namecard(char.id).navbar()).as_uri()
                extra["face"] = (await char.icon()).as_uri()
                extra["character"] = char_name
                extra["sort"] = 1
        elif "纪行" in an_title:
            an_type = "pass"
        elif an_title == "深渊":
            an_type = "abyss"

        def get_data(d1, d2):
            if d1 and len(d1) > 6:
                return datetime.strptime(d1, "%Y-%m-%d %H:%M:%S")
            return datetime.strptime(d2, "%Y-%m-%d %H:%M:%S")

        def human_read(d: timedelta):
            hour = d.seconds // 3600
            minute = d.seconds // 60 % 60
            text = ""
            if d.days:
                text += f"{d.days}天"
            if hour:
                text += f"{hour}小时"
            if minute:
                text += f"{minute}分钟"
            return text

        sDate = get_data(detail.get("start"), ds["start_time"])
        eDate = get_data(detail.get("end"), ds["end_time"])
        sTime = max(sDate, start_time)
        eTime = min(eDate, end_time)

        sRange = sTime - start_time
        eRange = eTime - start_time

        left = sRange / total_range * 100
        width = eRange / total_range * 100 - left

        label = ""
        if self.FULL_TIME_RE.findall(an_title) or eDate - sDate > timedelta(days=365):
            label = f"{sDate.strftime('%m-%d %H:%M')} 后永久有效" if sDate < now else "永久有效"
        elif sDate < now < eDate:
            label = f'{eDate.strftime("%m-%d %H:%M")} ({human_read(eDate - now)}后结束)'
            if width > (38 if is_act else 55):
                label = f"{sDate.strftime('%m-%d %H:%M')} ~ {label}"
        elif sDate > now:
            label = f'{sDate.strftime("%m-%d %H:%M")} ({human_read(sDate - now)}后开始)'
        elif is_act:
            label = f"{sDate.strftime('%m-%d %H:%M')} ~ {eDate.strftime('%m-%d %H:%M')}"

        if sDate <= end_time and eDate >= start_time:
            target.append(
                {
                    "id": an_id,
                    "type": an_type,
                    "title": an_title,
                    "banner": an_banner,
                    "mergeStatus": 1 if an_type in {"activity", "normal"} else 0,
                    "icon": ds.get("tag_icon", ""),
                    "left": left,
                    "width": width,
                    "label": label,
                    "duration": eTime - sTime,
                    "start": sDate.strftime("%m-%d %H:%M"),
                    "end": eDate.strftime("%m-%d %H:%M"),
                    **extra,
                }
            )

    @staticmethod
    def getAbyssCal(start_time, end_time):
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

    async def get(self, assets: AssetsService):
        now = datetime.now()
        list_data, time_map = await self.reqCalData()
        (
            date_list,
            start_time,
            end_time,
            total_range,
            now_left,
        ) = await self.getDateList()
        target = []
        abyss = []

        for ds in list_data["data"]["list"][1]["list"]:
            await self.get_list(ds, target, start_time, end_time, total_range, now, time_map, True, assets)
        for ds in list_data["data"]["list"][0]["list"]:
            await self.get_list(ds, target, start_time, end_time, total_range, now, time_map, False, assets)
        abyss_cal = self.getAbyssCal(start_time, end_time)
        for t in abyss_cal:
            ds = {
                "title": f"「深境螺旋」· {t[2]}",
                "start_time": t[0].strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": t[1].strftime("%Y-%m-%d %H:%M:%S"),
            }
            await self.get_list(ds, abyss, start_time, end_time, total_range, now, {}, True, assets)
        target.sort(key=lambda x: (x["sort"], x["start"], x["duration"]))

        char_count = 0
        char_old = 0
        ret = []
        for li in target:
            if li["type"] == "character":
                char_count += 1
                if li["left"] == 0:
                    char_old += 1
                li["idx"] = char_count
            if li["mergeStatus"] == 1:
                for li2 in target:
                    if (li2["mergeStatus"] == 1) and (li["left"] + li["width"] <= li2["left"]):
                        li["mergeStatus"] = 2
                        li2["mergeStatus"] = 2
                        ret.append([li, li2])
                        break
            if li["mergeStatus"] != 2:
                li["mergeStatus"] = 2
                ret.append([li])
        return {
            "date_list": date_list,
            "start_time": start_time,
            "end_time": end_time,
            "total_range": total_range,
            "now_left": now_left,
            "list": ret,
            "abyss": abyss,
            "char_mode": f"char-{char_count}-{char_old}",
            "now_time": now.strftime("%Y-%m-%d %H:%M"),
            "now_date": now.strftime("%Y-%m-%d"),
            "char_num": 0,
        }
