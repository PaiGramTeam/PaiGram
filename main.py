import asyncio
from warnings import filterwarnings

import pytz
from telegram.ext import Application, Defaults, AIORateLimiter
from telegram.warnings import PTBUserWarning

from config import config
from utils.log import logger
from utils.aiobrowser import AioBrowser
from utils.job.register import register_job
from utils.mysql import MySQL
from utils.plugins.register import register_plugin_handlers
from utils.redisdb import RedisDB
from utils.service.manager import ServicesManager

# 无视相关警告
# 该警告说明在官方GITHUB的WIKI中Frequently Asked Questions里的What do the per_* settings in ConversationHandler do?
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)
filterwarnings(action="ignore", message=r".*Prior to v20.0 the `days` parameter", category=PTBUserWarning)


def main() -> None:
    logger.info("正在启动项目")

    # 初始化数据库
    logger.info("初始化数据库")
    mysql = MySQL(host=config.mysql["host"], user=config.mysql["user"], password=config.mysql["password"],
                  port=config.mysql["port"], database=config.mysql["database"])

    # 初始化Redis缓存
    logger.info("初始化Redis缓存")
    redis = RedisDB(host=config.redis["host"], port=config.redis["port"], db=config.redis["database"])

    # 初始化Playwright
    logger.info("初始化Playwright")
    browser = AioBrowser()

    # 传入服务并启动
    logger.info("正在启动服务")
    services = ServicesManager(mysql, redis, browser)
    services.refresh_list("core/*")
    services.import_module()
    services.add_service()

    # 构建BOT
    logger.info("构建BOT")

    defaults = Defaults(tzinfo=pytz.timezone("Asia/Shanghai"))
    rate_limiter = AIORateLimiter()

    application = Application \
        .builder() \
        .token(config.bot_token) \
        .defaults(defaults) \
        .rate_limiter(rate_limiter) \
        .build()

    register_plugin_handlers(application)

    register_job(application)

    # 启动BOT
    try:
        logger.info("BOT已经启动 开始处理命令")
        # BOT 在退出后默认关闭LOOP 这时候得让LOOP不要关闭
        application.run_polling(close_loop=False)
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as exc:
        logger.info("BOT执行过程中出现错误")
        raise exc
    finally:
        logger.info("项目收到退出命令 BOT停止处理并退出")
        loop = asyncio.get_event_loop()
        try:
            # 需要关闭数据库连接
            logger.info("正在关闭数据库连接")
            loop.run_until_complete(mysql.wait_closed())
            # 关闭Redis连接
            logger.info("正在关闭Redis连接")
            loop.run_until_complete(redis.close())
            # 关闭playwright
            logger.info("正在关闭Playwright")
            loop.run_until_complete(browser.close())
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as exc:
            logger.error("关闭必要连接时出现错误 \n", exc)
        logger.info("正在关闭loop")
        # 关闭LOOP
        loop.close()
        logger.info("项目已经已结束")


if __name__ == '__main__':
    main()
