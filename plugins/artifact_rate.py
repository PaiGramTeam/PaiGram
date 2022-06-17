import re
import requests

from base64 import b64encode
from secrets import choice
from os import remove

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, filters
from logger import Log
from service.artifact_rate import get_artifact_attr, rate_artifact
from plugins.base import BasePlugins
from plugins.errorhandler import conversation_error_handler


def get_format_sub_item(artifact_attr):
    msg = ""
    for i in artifact_attr["sub_item"]:
        msg += f'{i["name"]:\u3000<6} | {i["value"]}\n'
    return msg


def get_yiyan(get_yiyan_num):
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
        data_ = int(float(get_yiyan_num))
    except ValueError:
        data_ = 0
    if data_ == 100:
        return choice(data["5"])
    return choice(data[str(data_ // 20 + 1)])


class DailyNote(BasePlugins):
    """
    圣遗物评分
    """

    async def command_start(self, update: Update, context: CallbackContext) -> None:
        message = update.message
        user = update.effective_user
        args = message.text.split(" ")
        search_command = re.search(r"^圣遗物评分(.*)", message.text)
        keyboard = [
            [
                InlineKeyboardButton(text="圣遗物评分", switch_inline_query_current_chat="圣遗物评分")
            ]
        ]
        if not message.photo:
            return await message.reply("图呢？\n*请命令将与截图一起发送", quote=True)
        msg = await message.reply("正在下载图片。。。", quote=True)
        path = await message.download()
        with open(path, "rb") as f:
            image_b64 = b64encode(f.read()).decode()
        remove(path)
        try:
            artifact_attr = await get_artifact_attr(image_b64)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            return await msg.edit("连接超时")
        if 'err' in artifact_attr.keys():
            err_msg = artifact_attr["full"]["message"]
            return await msg.edit(f"发生了点小错误：\n{err_msg}")
        if 'star' not in artifact_attr:
            reply_message = await message.reply_text("无法识别圣遗物星级，请回复数字（1-5）：",
                                                    reply_markup=InlineKeyboardMarkup(keyboard))
            try:
                artifact_attr['star'] = int(reply_message.text)
            except ValueError:
                artifact_attr['star'] = 4
            if filters.ChatType.GROUPS.filter(reply_message):
                    self._add_delete_message_job(context, message.chat_id, message.message_id)
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        if 'level' not in artifact_attr:
            reply_message = await message.reply_text("无法识别圣遗物等级，请回复数字（1-20）：",
                                                    reply_markup=InlineKeyboardMarkup(keyboard))
            try:
                artifact_attr['level'] = int(reply_message.text)
            except ValueError:
                artifact_attr['level'] = 1
            if filters.ChatType.GROUPS.filter(reply_message):
                    self._add_delete_message_job(context, message.chat_id, message.message_id)
                    self._add_delete_message_job(context, reply_message.chat_id, reply_message.message_id)
            return
        await msg.edit("识图成功！\n正在评分中...")
        rate_result = await rate_artifact(artifact_attr)
        if 'err' in rate_result.keys():
            err_msg = rate_result["full"]["message"]
            return await msg.edit(f"发生了点小错误：\n{err_msg}")
        format_result = f'圣遗物评分结果：\n' \
                        f'主属性：{artifact_attr["main_item"]["name"]}\n' \
                        f'{get_format_sub_item(artifact_attr)}' \
                        f'`------------------------------`\n' \
                        f'总分：{rate_result["total_percent"]}\n' \
                        f'主词条：{rate_result["main_percent"]}\n' \
                        f'副词条：{rate_result["sub_percent"]}\n' \
                        f'`------------------------------`\n' \
                        f'{get_yiyan(rate_result["total_percent"])}\n' \
                        f'评分、识图均来自 genshin.pub'
        await msg.edit(format_result)
