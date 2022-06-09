import asyncio
from warnings import filterwarnings

from telegram.ext import Application
from telegram.warnings import PTBUserWarning

from config import config
from handler import register_handlers
from logger import Log
from service import StartService
from service.cache import RedisCache
from service.repository import AsyncRepository

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

    register_handlers(application, service)

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
