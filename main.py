import asyncio
from warnings import filterwarnings

import pytz
from telegram.ext import Application, Defaults
from telegram.warnings import PTBUserWarning

from config import config
from logger import Log
from utils.aiobrowser import AioBrowser
from utils.apps.manager import AppsManager
from utils.job.register import register_job
from utils.mysql import MySQL
from utils.plugins.register import register_plugin_handlers
from utils.redisdb import RedisDB

# 无视相关警告
# 该警告说明在官方GITHUB的WIKI中Frequently Asked Questions里的What do the per_* settings in ConversationHandler do?
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


def main() -> None:
    Log.info("正在启动项目")

    # 初始化数据库
    Log.info("初始化数据库")
    mysql = MySQL(host=config.MYSQL["host"], user=config.MYSQL["user"], password=config.MYSQL["password"],
                  port=config.MYSQL["port"], database=config.MYSQL["database"])

    # 初始化Redis缓存
    Log.info("初始化Redis缓存")
    redis = RedisDB(host=config.REDIS["host"], port=config.REDIS["port"], db=config.REDIS["database"])

    # 初始化Playwright
    Log.info("初始化Playwright")
    browser = AioBrowser()

    # 传入服务并启动
    Log.info("正在启动服务")
    apps = AppsManager(mysql, redis, browser)
    apps.refresh_list("./apps/*")
    apps.import_module()
    apps.add_service()

    # 构建BOT
    Log.info("构建BOT")

    defaults = Defaults(tzinfo=pytz.timezone("Asia/Shanghai"))

    application = Application\
        .builder()\
        .token(config.TELEGRAM["token"])\
        .defaults(defaults)\
        .build()

    register_plugin_handlers(application)

    register_job(application)

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
            loop.run_until_complete(mysql.wait_closed())
            # 关闭Redis连接
            Log.info("正在关闭Redis连接")
            loop.run_until_complete(redis.close())
            # 关闭playwright
            Log.info("正在关闭Playwright")
            loop.run_until_complete(browser.close())
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
