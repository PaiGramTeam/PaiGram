from typing import Optional

from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler, InlineQueryHandler

from plugins.admin import Admin
from plugins.auth import Auth
from plugins.base import NewChatMembersHandler
from plugins.cookies import Cookies
from plugins.errorhandler import error_handler
from plugins.gacha import Gacha
from plugins.help import Help
from plugins.uid import Uid
from plugins.daily_note import DailyNote
from plugins.inline import Inline
from plugins.job_queue import JobQueue
from plugins.post import Post
from plugins.quiz import Quiz
from plugins.sign import Sign
from plugins.start import start, ping, reply_keyboard_remove, unknown_command
from plugins.strategy import Strategy
from plugins.weapon import Weapon
from service import BaseService


def register_handlers(application, service: BaseService = None):
    # 添加相关命令处理过程
    def add_handler(handler, command: Optional[str] = None, regex: Optional[str] = None, query: Optional[str] = None,
                    block: bool = False) -> None:
        if command:
            application.add_handler(CommandHandler(command, handler, block=block))
        if regex:
            application.add_handler(MessageHandler(filters.Regex(regex), handler, block=block))
        if query:
            application.add_handler(CallbackQueryHandler(handler, pattern=query, block=block))
    
    if service is None:
        return

    # 基础命令
    add_handler(start, command="start")
    _help = Help(service)
    add_handler(_help.command_start, command="help")
    add_handler(ping, command="ping")

    # 有关群验证和监听
    auth = Auth(service)
    new_chat_members_handler = NewChatMembersHandler(service, auth.new_mem)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                                           new_chat_members_handler.new_member, block=False))
    add_handler(auth.query, query=r"^auth_challenge\|")
    add_handler(auth.admin, query=r"^auth_admin\|")

    # cookie绑定
    cookies_handler = Cookies.create_conversation_handler(service)
    uid_handler = Uid.create_conversation_handler(service)
    daily_note_handler = DailyNote.create_conversation_handler(service)
    sign_handler = Sign.create_conversation_handler(service)
    quiz_handler = Quiz.create_conversation_handler(service)
    post_handler = Post.create_conversation_handler(service)
    gacha = Gacha(service)
    add_handler(gacha.command_start, command="gacha", regex=r"^抽卡模拟器(.*)")
    admin = Admin(service)
    add_handler(admin.add_admin, command="add_admin")
    add_handler(admin.del_admin, command="del_admin")
    weapon = Weapon(service)
    add_handler(weapon.command_start, command="weapon", regex=r"^武器查询(.*)")
    strategy = Strategy(service)
    add_handler(strategy.command_start, command="strategy", regex=r"^角色攻略查询(.*)")
    # 调试功能
    add_handler(reply_keyboard_remove, command="reply_keyboard_remove")
    add_handler(admin.leave_chat, command="leave_chat")
    application.add_handler(sign_handler)
    application.add_handler(quiz_handler)
    application.add_handler(cookies_handler)
    application.add_handler(uid_handler)
    application.add_handler(daily_note_handler)
    application.add_handler(post_handler)
    inline = Inline(service)
    application.add_handler(InlineQueryHandler(inline.inline_query, block=False))
    job_queue = JobQueue(service)
    application.job_queue.run_once(job_queue.start_job, when=3, name="start_job")
    application.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, unknown_command))
    application.add_error_handler(error_handler, block=False)

