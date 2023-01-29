import re
from datetime import datetime

from telegram import Message, User
from telegram.ext import filters

from core.plugin import Plugin, handler
from metadata.genshin import AVATAR_DATA
from metadata.shortname import roleToId, roleToName
from utils.decorators.restricts import restricts
from utils.log import logger


def rm_starting_str(string, starting):
    """Remove the starting character from a string."""
    while string[0] == str(starting):
        string = string[1:]
    return string


class BirthdayPlugin(Plugin):
    """Birthday."""

    def __init__(self):
        """Load Data."""
        self.birthday_list = {}
        for value in AVATAR_DATA.values():
            key = "_".join([str(i) for i in value["birthday"]])
            data = self.birthday_list.get(key, [])
            data.append(value["name"])
            self.birthday_list.update({key: data})

    @restricts()
    @handler.command(command="birthday", block=False)
    async def command_start(self, user: User, message: Message) -> None:
        key = (
                rm_starting_str(datetime.now().strftime("%m"), "0")
                + "_"
                + rm_starting_str(datetime.now().strftime("%d"), "0")
        )
        args = self.get_args()

        if len(args) >= 1:
            msg = args[0]
            logger.info(f"用户 {user.full_name}[{user.id}] 查询角色生日命令请求 || 参数 {msg}")
            if re.match(r"\d{1,2}.\d{1,2}", msg):
                try:
                    month = rm_starting_str(re.findall(r"\d+", msg)[0], "0")
                    day = rm_starting_str(re.findall(r"\d+", msg)[1], "0")
                    key = f"{month}_{day}"
                    day_list = self.birthday_list.get(key, [])
                    date = f"{month}月{day}日"
                    if key == "6_1":
                        text = f"{date} 是 派蒙、{'、'.join(day_list)} 的生日哦~"
                    else:
                        text = f"{date} 是 {'、'.join(day_list)} 的生日哦~" if day_list else f"{date} 没有角色过生日哦~"
                except IndexError:
                    text = "请输入正确的日期格式，如1-1，或输入正确的角色名称。"
                reply_message = await message.reply_text(text)

            else:
                try:
                    if msg == "派蒙":
                        name = "派蒙"
                        birthday = [6, 1]
                    else:
                        name = roleToName(msg)
                        aid = str(roleToId(msg))
                        birthday = AVATAR_DATA[aid]["birthday"]
                    text = f"{name} 的生日是 {birthday[0]}月{birthday[1]}日 哦~"
                    reply_message = await message.reply_text(text)

                except KeyError:
                    reply_message = await message.reply_text("请输入正确的日期格式，如1-1，或输入正确的角色名称。")

        else:
            logger.info(f"用户 {user.full_name}[{user.id}] 查询今日角色生日列表")
            today_list = self.birthday_list.get(key, [])
            if key == "6_1":
                text = f"今天是 派蒙、{'、'.join(today_list)} 的生日哦~"
            else:
                text = f"今天是 {'、'.join(today_list)} 的生日哦~" if today_list else "今天没有角色过生日哦~"
            reply_message = await message.reply_text(text)

        if filters.ChatType.GROUPS.filter(reply_message):
            self.add_delete_message_job(message)
            self.add_delete_message_job(reply_message)
