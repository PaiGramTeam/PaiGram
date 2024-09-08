from typing import TYPE_CHECKING

from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from core.plugin import Plugin, handler
from core.config import config
from utils.log import logger

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class SetCommandPlugin(Plugin):
    @handler.command("set_command", block=False, admin=True)
    @handler.command("set_commands", block=False, admin=True)
    async def set_command(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE"):
        user = update.effective_user
        message = update.effective_message
        logger.info("用户 %s[%s] 发出 set_command 命令", user.full_name, user.id)
        user_command = [
            BotCommand("cancel", "取消操作（解决一切玄学问题）"),
            BotCommand("help_raw", "查看文本帮助"),
            # gacha_log 相关
            BotCommand("wish_log", "查看抽卡记录"),
            BotCommand("wish_log_import", "导入抽卡记录"),
            BotCommand("wish_log_export", "导出抽卡记录"),
            BotCommand("wish_log_delete", "删除抽卡记录"),
            BotCommand("wish_log_online_view", "抽卡记录在线浏览"),
            BotCommand("pay_log", "查看充值记录"),
            BotCommand("pay_log_import", "导入充值记录"),
            BotCommand("pay_log_export", "导出充值记录"),
            BotCommand("pay_log_delete", "删除充值记录"),
            # Cookie 查询类
            BotCommand("sign", "米游社原神每日签到"),
            BotCommand("dailynote_tasks", "自动便笺提醒"),
            # 其他
            BotCommand("hilichurls", "丘丘语字典"),
            BotCommand("birthday", "查询角色生日"),
            BotCommand("setuid", "添加/重设UID"),
            BotCommand("setcookie", "添加/重设Cookie"),
            BotCommand("setdevice", "添加/重设设备"),
            BotCommand("player", "管理用户绑定玩家"),
            BotCommand("verify", "手动验证"),
            BotCommand("redeem", "（国际服）兑换 Key"),
            BotCommand("privacy", "隐私政策"),
        ]
        group_command = [
            # 通用
            BotCommand("help", "帮助"),
            BotCommand("quiz", f"{config.notice.bot_name}的十万个为什么"),
            BotCommand("wish", " 非洲人模拟器（抽卡模拟器）"),
            BotCommand("set_wish", "抽卡模拟器定轨"),
            BotCommand("calendar", "活动日历"),
            # Wiki 类
            BotCommand("weapon", "查询武器"),
            BotCommand("strategy", "查询角色攻略"),
            BotCommand("material", "角色培养素材查询"),
            # UID 查询类
            BotCommand("stats", "玩家统计查询"),
            BotCommand("player_card", "查询角色卡片"),
            BotCommand("avatar_board", "角色排名"),
            BotCommand("gcsim", "组队伤害计算"),
            # Cookie 查询类
            BotCommand("dailynote", "查询实时便笺"),
            BotCommand("ledger", "查询当月旅行札记"),
            BotCommand("ledger_history", "查询旅行札记历史记录"),
            BotCommand("abyss", "查询深渊战绩"),
            BotCommand("abyss_team", "查询深渊推荐配队"),
            BotCommand("abyss_history", "查询深渊历史战绩"),
            BotCommand("role_combat", "查询幻想真境剧诗战绩"),
            BotCommand("role_combat_history", "查询幻想真境剧诗历史战绩"),
            BotCommand("avatars", "查询角色练度"),
            BotCommand("reg_time", "账号注册时间"),
            BotCommand("daily_material", "今日素材表"),
            BotCommand("cookies_import", "从其他 BOT 导入账号信息"),
            BotCommand("cookies_export", "导出账号信息给其他 BOT"),
        ]
        admin_command = [
            BotCommand("add_admin", "添加管理员"),
            BotCommand("del_admin", "删除管理员"),
            BotCommand("refresh_metadata", "刷新元数据"),
            BotCommand("refresh_wiki", "刷新Wiki缓存"),
            BotCommand("refresh_map", "刷新地图数据"),
            BotCommand("save_entry", "保存条目数据"),
            BotCommand("remove_all_entry", "删除全部条目数据"),
            BotCommand("sign_all", "全部账号重新签到"),
            BotCommand("refresh_all_history", "全部账号刷新历史记录"),
            BotCommand("send_log", "发送日志"),
            BotCommand("update", "更新"),
            BotCommand("set_command", "重设命令"),
            BotCommand("status", "当前Bot运行状态"),
            BotCommand("leave_chat", "退出群组"),
            BotCommand("get_chat", "获取会话信息"),
            BotCommand("add_block", "添加黑名单"),
            BotCommand("del_block", "移除黑名单"),
        ]
        await context.bot.set_my_commands(
            commands=group_command
        )  # 留空，default 为 botCommandScopeDefault, 所有聊天可见
        await context.bot.set_my_commands(commands=user_command + group_command, scope=BotCommandScopeAllPrivateChats())
        if config.error.notification_chat_id:
            await context.bot.set_my_commands(
                commands=admin_command + group_command + user_command,
                scope=BotCommandScopeChat(config.error.notification_chat_id),
            )
        await message.reply_text("设置命令成功")
