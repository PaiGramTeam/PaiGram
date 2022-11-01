import asyncio

try:
    import uvloop
except ImportError:
    uvloop = None

if uvloop is not None:
    # noinspection PyUnresolvedReferences
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def main():
    from core.bot import bot

    bot.launch()


if __name__ == "__main__":
    main()
