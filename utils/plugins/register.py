from importlib import import_module
from typing import Optional

from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, Application, InlineQueryHandler

from logger import Log
from plugins.base import NewChatMembersHandler
from plugins.system.errorhandler import error_handler
from plugins.system.inline import Inline
from plugins.system.start import start, ping, reply_keyboard_remove, unknown_command
from utils.plugins.manager import PluginsManager


def register_plugin_handlers(application: Application):
    """
    注册插件相关处理程序
    :param application:
    :param service:
    :return:
    """

    # 添加相关命令处理过程
    def add_handler(handler, command: Optional[str] = None, regex: Optional[str] = None, query: Optional[str] = None,
                    block: bool = False) -> None:
        if command:
            application.add_handler(CommandHandler(command, handler, block=block))
        if regex:
            application.add_handler(MessageHandler(filters.Regex(regex), handler, block=block))
        if query:
            application.add_handler(CallbackQueryHandler(handler, pattern=query, block=block))

    # 初始化
    Log.info("正在加载动态插件管理器")
    plugins_manager = PluginsManager()
    plugins_manager.add_exclude(["start", "auth", "inline", "errorhandler"])  # 忽略内置模块

    Log.info("正在加载插件")
    plugins_manager.refresh_list("plugins/genshin/*")
    plugins_manager.refresh_list("plugins/system/*")

    Log.info("加载插件管理器正在加载插件")
    plugins_manager.import_module()
    plugins_manager.add_handler(application)

    Log.info("正在加载静态系统插件")
    inline = Inline()
    new_chat_members_handler = NewChatMembersHandler()

    if config.auth["status"]:
        auth = Auth()
        for chat_id in config.auth["groups"]:
            new_chat_members_handler.add_callback(auth.new_mem, chat_id)
        add_handler(auth.query, query=r"^auth_challenge\|")
        add_handler(auth.admin, query=r"^auth_admin\|")

    add_handler(start, command="start")
    add_handler(ping, command="ping")
    # 调试功能
    add_handler(reply_keyboard_remove, command="reply_keyboard_remove")

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                                           new_chat_members_handler.new_member, block=False))
    application.add_handler(InlineQueryHandler(inline.inline_query, block=False))
    application.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, unknown_command))
    application.add_error_handler(error_handler, block=False)

    import_module("plugins.system.admin")

    Log.info("插件加载成功")
