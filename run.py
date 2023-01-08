import asyncio

from utils.const import PROJECT_ROOT

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    uvloop = None


def main():
    from core.bot import bot
    from core.builtins.reloader import Reloader
    from core.config import config

    if config.auto_reload:
        reload_config = config.reload

        Reloader(
            bot.launch,
            reload_delay=reload_config.delay,
            reload_dirs=list(set(reload_config.dirs + [PROJECT_ROOT])),
            reload_includes=reload_config.include,
            reload_excludes=reload_config.exclude,
        ).run()
    else:
        bot.launch()


if __name__ == "__main__":
    main()
