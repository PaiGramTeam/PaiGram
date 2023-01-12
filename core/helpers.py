from typing import List, Optional, Union

import ujson as json
from telegram import Chat
from telegram.ext import CallbackContext

from core.builtins.contexts import BotContext, TGContext
from core.dependence.redisdb import RedisDB


async def get_chat(chat_id: Union[str, int], redis_db: Optional[RedisDB] = None, ttl: int = 86400) -> Chat:
    bot = BotContext.get()
    redis_db: RedisDB = redis_db or bot.services_map.get(RedisDB, None)

    if not redis_db:
        return await bot.tg_app.bot.get_chat(chat_id)

    qname = f"bot:chat:{chat_id}"

    data = await redis_db.client.get(qname)
    if data:
        json_data = json.loads(data)
        return Chat.de_json(json_data, bot.tg_app.bot)

    chat_info = await bot.tg_app.bot.get_chat(chat_id)
    await redis_db.client.set(qname, chat_info.to_json())
    await redis_db.client.expire(qname, ttl)
    return chat_info


def get_args(context: Optional[CallbackContext] = None) -> List[str]:
    if context is None:
        context = TGContext.get()

    args = context.args
    match = context.match

    if args is None:
        if match is not None and (command := match.groups()[0]):
            temp = []
            command_parts = command.split(" ")
            for command_part in command_parts:
                if command_part:
                    temp.append(command_part)
            return temp
        return []
    else:
        if len(args) >= 1:
            return args
    return []
