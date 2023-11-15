import asyncio

from utils.const import PROJECT_ROOT

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    uvloop = None


def run():
    __import__("utils.patch")
    from core.application import Application
    from dotenv import load_dotenv

    load_dotenv()
    Application.build().launch()


def main():
    from gram_core.builtins.reloader import Reloader
    from core.config import config

    if config.auto_reload:  # 是否启动重载器
        reload_config = config.reload

        Reloader(
            run,
            reload_delay=reload_config.delay,
            reload_dirs=list(set(reload_config.dirs + [PROJECT_ROOT])),
            reload_includes=reload_config.include,
            reload_excludes=reload_config.exclude,
        ).run()
    else:
        run()


if __name__ == "__main__":
    main()
