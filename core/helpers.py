from typing import Optional, Union

import ujson as json
from telegram import Chat

from core.builtins.contexts import BotContext
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
