from typing import Optional

from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, InlineQueryHandler, Application

from logger import Log
from manager import PluginsManager, JobsManager
from plugins.auth import Auth
from plugins.base import NewChatMembersHandler
from plugins.errorhandler import error_handler
from plugins.inline import Inline
from plugins.start import start, ping, reply_keyboard_remove, unknown_command
from service import BaseService


def register_handlers(application: Application, service: BaseService):
    """
    注册相关处理程序
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

    Log.info("正在加载插件管理器")
    plugins_manager = PluginsManager()

    plugins_manager.refresh_list("./plugins/*")

    # 忽略内置模块
    plugins_manager.add_exclude(["start", "base", "auth", "inline", "errorhandler"])

    Log.info("加载插件管理器正在加载插件")
    plugins_manager.import_module()
    plugins_manager.add_handler(application, service)

    Log.info("正在加载内置插件")

    inline = Inline(service)
    auth = Auth(service)

    add_handler(start, command="start")
    add_handler(ping, command="ping")
    add_handler(auth.query, query=r"^auth_challenge\|")
    add_handler(auth.admin, query=r"^auth_admin\|")
    # 调试功能
    add_handler(reply_keyboard_remove, command="reply_keyboard_remove")

    new_chat_members_handler = NewChatMembersHandler(service, auth.new_mem)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                                           new_chat_members_handler.new_member, block=False))

    application.add_handler(InlineQueryHandler(inline.inline_query, block=False))
    application.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, unknown_command))
    application.add_error_handler(error_handler, block=False)

    Log.info("插件加载成功")


def register_job(application: Application, service: BaseService):
    Log.info("正在加载Job管理器")
    jobs_manager = JobsManager()

    jobs_manager.refresh_list("./jobs/*")

    # 忽略内置模块
    jobs_manager.add_exclude(["base"])

    Log.info("Job管理器正在加载插件")
    jobs_manager.import_module()
    jobs_manager.add_handler(application, service)

    Log.info("Job加载成功")
