import asyncio
from typing import Optional
from warnings import filterwarnings

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, \
    CallbackQueryHandler, InlineQueryHandler
from telegram.warnings import PTBUserWarning

from logger import Log
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
from service import StartService
from service.repository import AsyncRepository
from config import config
from service.cache import RedisCache

# 无视相关警告
# 该警告说明在官方GITHUB的WIKI中Frequently Asked Questions里的What do the per_* settings in ConversationHandler do?
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


def main() -> None:
    Log.info("正在启动项目")

    # 初始化数据库
    Log.info("初始化数据库")
    repository = AsyncRepository(mysql_host=config.MYSQL["host"],
                                 mysql_user=config.MYSQL["user"],
                                 mysql_password=config.MYSQL["password"],
                                 mysql_port=config.MYSQL["port"],
                                 mysql_database=config.MYSQL["database"]
                                 )

    # 初始化Redis缓存
    Log.info("初始化Redis缓存")
    cache = RedisCache(db=6)

    # 传入服务并启动
    Log.info("传入服务并启动")
    service = StartService(repository, cache)

    # 构建BOT
    application = Application.builder().token(config.TELEGRAM["token"]).build()
    Log.info("构建BOT")

    # 添加相关命令处理过程
    def add_handler(handler, command: Optional[str] = None, regex: Optional[str] = None, query: Optional[str] = None,
                    block: bool = False) -> None:
        if command:
            application.add_handler(CommandHandler(command, handler, block=block))
        if regex:
            application.add_handler(MessageHandler(filters.Regex(regex), handler, block=block))
        if query:
            application.add_handler(CallbackQueryHandler(handler, pattern=query, block=block))

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
    uid = Uid(service)
    uid_handler = ConversationHandler(
        entry_points=[CommandHandler('uid', uid.command_start, block=True),
                      MessageHandler(filters.Regex(r"^玩家查询(.*)"), uid.command_start, block=True)],
        states={
            uid.COMMAND_RESULT: [CallbackQueryHandler(uid.command_result, block=True)]
        },
        fallbacks=[CommandHandler('cancel', uid.cancel, block=True)]
    )
    daily_note = DailyNote(service)
    daily_note_handler = ConversationHandler(
        entry_points=[CommandHandler('dailynote', daily_note.command_start, block=True),
                      MessageHandler(filters.Regex(r"^当前状态(.*)"), daily_note.command_start, block=True)],
        states={
            daily_note.COMMAND_RESULT: [CallbackQueryHandler(daily_note.command_result, block=True)]
        },
        fallbacks=[CommandHandler('cancel', daily_note.cancel, block=True)]
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
            _post.CHECK_COMMAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.check_command, block=True)],
            _post.GTE_DELETE_PHOTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_delete_photo, block=True)],
            _post.GET_POST_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_post_channel, block=True)],
            _post.GET_TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_tags, block=True)],
            _post.GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, _post.get_edit_text, block=True)]
        },
        fallbacks=[CommandHandler('cancel', _post.cancel, block=True)]
    )
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

    # 启动BOT
    try:
        Log.info("BOT已经启动 开始处理命令")
        # BOT 在退出后默认关闭LOOP 这时候得让LOOP不要关闭
        application.run_polling(close_loop=False)
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as exc:
        Log.info("BOT执行过程中出现错误")
        raise exc
    finally:
        Log.info("项目收到退出命令 BOT停止处理并退出")
        loop = asyncio.get_event_loop()
        try:
            # 需要关闭数据库连接
            Log.info("正在关闭数据库连接")
            loop.run_until_complete(repository.wait_closed())
            # 关闭Redis连接
            Log.info("正在关闭Redis连接")
            loop.run_until_complete(cache.close())
            # 关闭playwright
            Log.info("正在关闭Playwright")
            loop.run_until_complete(service.template.close())
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            Log.error("关闭必要连接时出现错误 \n", exc)
        Log.info("正在关闭loop")
        # 关闭LOOP
        loop.close()
        Log.info("项目已经已结束")


if __name__ == '__main__':
    main()
