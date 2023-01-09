from typing import List, Optional, Union

import ujson as json
from telegram import Chat
from telegram.ext import CallbackContext

from core.builtins.contexts import TGContext
from core.dependence.redisdb import RedisDB


async def get_chat(chat_id: Union[str, int], redis: Optional[RedisDB] = None, ttl: int = 86400) -> Chat:
    if not redis:
        return await bot.tg_app.bot.get_chat(chat_id)
    qname = f"bot:chat:{chat_id}"
    data = await redis.client.get(qname)
    if data:
        json_data = json.loads(data)
        return Chat.de_json(json_data, bot.tg_app.bot)
    chat_info = await bot.tg_app.bot.get_chat(chat_id)
    await redis.client.set(qname, chat_info.to_json())
    await redis.client.expire(qname, ttl)
    return chat_info


def get_args(context: Optional[CallbackContext] = None) -> List[str]:
    if context is None:
        context = TGContext.get()

    args = context.args
    match = context.match
    if args is None:
        if match is not None:
            groups = match.groups()
            command = groups[0]
            if command:
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
