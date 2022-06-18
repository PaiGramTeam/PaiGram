from base64 import b64encode
from random import choice

import httpx


def get_format_sub_item(artifact_attr: dict):
    return "".join(f'{i["name"]:\u3000<6} | {i["value"]}\n' for i in artifact_attr["sub_item"])


def get_comment(get_rate_num):
    data = {"1": ["破玩意谁能用啊，谁都用不了吧", "喂了吧，这东西做狗粮还能有点用", "抽卡有保底，圣遗物没有下限",
                  "未来可期呢（笑）", "你出门一定很安全", "你是不是得罪米哈游了？", "……宁就是班尼特本特？",
                  "丢人！你给我退出提瓦特(", "不能说很糟糕，只能说特别不好"],
            "2": ["淡如清泉镇的圣水，莫得提升", "你怎么不强化啊？", "嗯嗯嗯好好好可以可以可以挺好挺好（敷衍）",
                  "这就是日常，下一个", "洗洗还能吃（bushi）", "下次一定行……？", "派蒙平静地点了个赞",
                  "不知道该说什么，就当留个纪念吧"],
            "3": ["不能说有质变，只能说有提升", "过渡用的话没啥问题，大概", "再努努力吧", "嗯，差不多能用",
                  "这很合理", "达成成就“合格圣遗物”", "嗯，及格了，过渡用挺好的", "中规中矩，有待提升"],
            "4": ["以普遍理性而论，很好", "算是个很不戳的圣遗物了！", "很好，很有精神！", "再努努力，超越一下自己",
                  "感觉可以戴着它大杀四方了", "这就是大佬背包里的平均水平吧", "先锁上呗，这波不亏", "达成成就“高分圣遗物”",
                  "这波对输出有很大提升啊(认真)", "我也想拥有这种分数的圣遗物(切实)"],
            "5": ["多吃点好的，出门注意安全", "晒吧，欧不可耻，只是可恨", "没啥好说的，让我自闭一会", "达成成就“高分圣遗物”",
                  "怕不是以后开宝箱只能开出卷心菜", "吃了吗？没吃的话，吃我一拳", "我觉得这个游戏有问题", "这合理吗",
                  "这东西没啥用，给我吧（柠檬）", "？？？ ？？？？"]}
    try:
        data_ = int(float(get_rate_num))
    except ValueError:
        data_ = 0
    if data_ == 100:
        return choice(data["5"])
    return choice(data[str(data_ // 20 + 1)])


class ArtifactORCRate:
    OCR_URL = "https://api.genshin.pub/api/v1/app/ocr"
    RATE_URL = "https://api.genshin.pub/api/v1/relic/rate"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36",
        "Content-Type": "application/json; charset=utf-8",
    }

    def __init__(self):
        self.client = httpx.AsyncClient(headers=self.HEADERS)

    async def get_artifact_attr(self, photo_byte):
        b64_str = b64encode(photo_byte).decode()
        req = await self.client.post(self.OCR_URL, json={"image": b64_str}, timeout=8)
        return req

    async def rate_artifact(self, artifact_attr: dict):
        req = await self.client.post(self.RATE_URL, json=artifact_attr, timeout=8)
        return req
