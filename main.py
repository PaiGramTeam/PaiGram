from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler, InlineQueryHandler, CallbackContext

from plugins.admin import Admin
from plugins.auth import Auth
from plugins.cookies import Cookies
from plugins.errorhandler import error_handler
from plugins.gacha import Gacha
from plugins.get_user import GetUser
from plugins.inline import Inline
from plugins.job_queue import JobQueue
from plugins.quiz import Quiz
from plugins.sign import Sign
from plugins.start import start, help_command, new_chat_members, emergency_food, ping
from plugins.weapon import Weapon
from service import StartService
from service.repository import AsyncRepository
from config import config
from service.cache import RedisCache


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
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping))
    # application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_members))
    auth = Auth(service)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, auth.new_mem))
    application.add_handler(CallbackQueryHandler(auth.query, pattern=r"^auth_challenge\|"))
    application.add_handler(CallbackQueryHandler(auth.admin, pattern=r"^auth_admin\|"))

    # application.add_handler(MessageHandler((filters.Regex(r'.派蒙是应急食品') & filters.ChatType.PRIVATE), emergency_food))

    cookies = Cookies(service)
    cookies_handler = ConversationHandler(
        entry_points=[CommandHandler('set_cookies', cookies.command_start),
                      MessageHandler(filters.Regex(r"^绑定账号(.*)"), cookies.command_start)],
        states={
            cookies.CHECK_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookies.check_server)],
            cookies.CHECK_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookies.check_cookies)],
            cookies.COMMAND_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cookies.command_result)],
        },
        fallbacks=[CommandHandler('cancel', cookies.cancel)],
    )
    get_user = GetUser(service)
    get_user_handler = ConversationHandler(
        entry_points=[CommandHandler('get_user', get_user.command_start),
                      MessageHandler(filters.Regex(r"^玩家查询(.*)"), get_user.command_start)],
        states={
            get_user.COMMAND_RESULT: [CallbackQueryHandler(get_user.command_result)]
        },
        fallbacks=[CommandHandler('cancel', get_user.cancel)],
    )
    sign = Sign(service)
    sign_handler = ConversationHandler(
        entry_points=[CommandHandler('sign', sign.command_start),
                      MessageHandler(filters.Regex(r"^每日签到(.*)"), sign.command_start)],
        states={
            sign.COMMAND_RESULT: [CallbackQueryHandler(sign.command_result)]
        },
        fallbacks=[CommandHandler('cancel', sign.cancel)],
    )
    application.add_handler(sign_handler)
    quiz = Quiz(service)
    quiz_handler = ConversationHandler(
        entry_points=[CommandHandler('quiz', quiz.command_start)],
        states={
            quiz.CHECK_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.check_command)],
            quiz.CHECK_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.check_question)],
            quiz.GET_NEW_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.get_new_question)],
            quiz.GET_NEW_CORRECT_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.get_new_correct_answer)],
            quiz.GET_NEW_WRONG_ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.get_new_wrong_answer),
                                        CommandHandler("finish", quiz.finish_edit)],
            quiz.SAVE_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, quiz.save_question)],
        },
        fallbacks=[CommandHandler('cancel', quiz.cancel)]
    )
    gacha = Gacha(service)
    application.add_handler(CommandHandler("gacha", gacha.command_start))
    admin = Admin(service)
    application.add_handler(CommandHandler("add_admin", admin.add_admin))
    application.add_handler(CommandHandler("del_admin", admin.del_admin))
    weapon = Weapon(service)
    application.add_handler(CommandHandler("weapon", weapon.command_start))
    application.add_handler(MessageHandler(filters.Regex(r"^武器查询(.*)"), weapon.command_start))
    application.add_handler(quiz_handler)
    application.add_handler(cookies_handler)
    application.add_handler(get_user_handler)
    inline = Inline(service)
    application.add_handler(InlineQueryHandler(inline.inline_query))
    job_queue = JobQueue(service)
    application.job_queue.run_once(job_queue.start_job, when=3, name="start_job")
    # application.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, unknown_command))
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
