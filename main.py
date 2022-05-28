from typing import Optional
from warnings import filterwarnings

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler, InlineQueryHandler
from telegram.warnings import PTBUserWarning

from plugins.admin import Admin
from plugins.auth import Auth
from plugins.base import NewChatMembersHandler
from plugins.cookies import Cookies
from plugins.errorhandler import error_handler
from plugins.gacha import Gacha
from plugins.get_user import GetUser
from plugins.inline import Inline
from plugins.job_queue import JobQueue
from plugins.post import Post
from plugins.quiz import Quiz
from plugins.sign import Sign
from plugins.start import start, help_command, ping, reply_keyboard_remove, unknown_command
from plugins.strategy import Strategy
from plugins.weapon import Weapon
from service import StartService
from service.repository import AsyncRepository
from config import config
from service.cache import RedisCache

# https://github.com/python-telegram-bot/python-telegram-bot/wiki/Frequently-Asked-Questions#what-do-the-per_-settings-in-conversationhandler-do
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


def main() -> None:
    repository = AsyncRepository(mysql_host=config.MYSQL["host"],
                                 mysql_user=config.MYSQL["user"],
                                 mysql_password=config.MYSQL["password"],
                                 mysql_port=config.MYSQL["port"],
                                 mysql_database=config.MYSQL["database"]
                                 )
    cache = RedisCache(db=6)
    service = StartService(repository, cache)
    application = Application.builder().token(config.TELEGRAM["token"]).build()

    def add_handler(handler, command: Optional[str] = None, regex: Optional[str] = None, query: Optional[str] = None,
                    block: bool = False) -> None:
        if command:
            application.add_handler(CommandHandler(command, handler, block=block))
        if regex:
            application.add_handler(MessageHandler(filters.Regex(regex), handler, block=block))
        if query:
            application.add_handler(CallbackQueryHandler(handler, pattern=query, block=block))

    add_handler(start, command="start")
    add_handler(help_command, command="help")
    add_handler(ping, command="ping")
    # application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_members))
    auth = Auth(service)
    new_chat_members_handler = NewChatMembersHandler(service, auth.new_mem)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS,
                                           new_chat_members_handler.new_member, block=False))
    add_handler(auth.query, query=r"^auth_challenge\|")
    add_handler(auth.admin, query=r"^auth_admin\|")

    # application.add_handler(MessageHandler((filters.Regex(r'.派蒙是应急食品') & filters.ChatType.PRIVATE), emergency_food))

    cookies = Cookies(service)
    cookies_handler = ConversationHandler(
        entry_points=[CommandHandler('adduser', cookies.command_start, filters.ChatType.PRIVATE, block=True),
                      MessageHandler(filters.Regex(r"^绑定账号(.*)") & filters.ChatType.PRIVATE,
                                     cookies.command_start, block=True)],
        states={
            cookies.CHECK_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                  cookies.check_server, block=True)],
            cookies.CHECK_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                   cookies.check_cookies, block=True)],
            cookies.COMMAND_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                    cookies.command_result, block=True)],
        },
        fallbacks=[CommandHandler('cancel', cookies.cancel, block=True)],
    )
    get_user = GetUser(service)
    get_user_handler = ConversationHandler(
        entry_points=[CommandHandler('getuser', get_user.command_start, block=True),
                      MessageHandler(filters.Regex(r"^玩家查询(.*)"), get_user.command_start, block=True)],
        states={
            get_user.COMMAND_RESULT: [CallbackQueryHandler(get_user.command_result, block=True)]
        },
        fallbacks=[CommandHandler('cancel', get_user.cancel, block=True)]
    )
    sign = Sign(service)
    sign_handler = ConversationHandler(
        entry_points=[CommandHandler('sign', sign.command_start, block=True),
                      MessageHandler(filters.Regex(r"^每日签到(.*)"), sign.command_start, block=True)],
        states={
            sign.COMMAND_RESULT: [CallbackQueryHandler(sign.command_result, block=True)]
        },
        fallbacks=[CommandHandler('cancel', sign.cancel, block=True)]
    )
    quiz = Quiz(service)
    quiz_handler = ConversationHandler(
        entry_points=[CommandHandler('quiz', quiz.command_start, block=True)],
        states={
            quiz.CHECK_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                quiz.check_command, block=True)],
            quiz.CHECK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                 quiz.check_question, block=True)],
            quiz.GET_NEW_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                   quiz.get_new_question, block=True)],
            quiz.GET_NEW_CORRECT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                         quiz.get_new_correct_answer, block=True)],
            quiz.GET_NEW_WRONG_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                       quiz.get_new_wrong_answer, block=True),
                                        CommandHandler("finish", quiz.finish_edit)],
            quiz.SAVE_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND,
                                                quiz.save_question, block=True)],
        },
        fallbacks=[CommandHandler('cancel', quiz.cancel, block=True)]
    )
    _post = Post(service)
    post_handler = ConversationHandler(
        entry_points=[CommandHandler('post', _post.command_start, block=True)],
        states={
            _post.CHECK_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.check_post, block=True)],
            _post.SEND_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.send_post, block=True)],
        },
        fallbacks=[CommandHandler('cancel', _post.cancel, block=True)]
    )
    gacha = Gacha(service)
    add_handler(gacha.command_start, command="gacha", regex=r"^抽卡(.*)")
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
    application.add_handler(get_user_handler)
    application.add_handler(post_handler)
    inline = Inline(service)
    application.add_handler(InlineQueryHandler(inline.inline_query, block=False))
    job_queue = JobQueue(service)
    application.job_queue.run_once(job_queue.start_job, when=3, name="start_job")
    application.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, unknown_command))
    application.add_error_handler(error_handler, block=False)
    application.run_polling()


if __name__ == '__main__':
    main()
