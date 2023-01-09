import asyncio

from core.application import Application
from core.builtins.dispatcher import set_default_kwargs
from utils.const import PROJECT_ROOT
from core.builtins.reloader import Reloader
from core.config import config

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    uvloop = None


def run():
    app = Application()
    set_default_kwargs(app)
    app.launch()


def main():

    if config.auto_reload:

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
