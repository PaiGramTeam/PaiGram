import json
from typing import List, cast, Union

from telegram import Chat
from telegram.ext import CallbackContext

from core.base.redisdb import RedisDB
from core.bot import bot

redis_db = bot.services.get(RedisDB)
redis_db = cast(RedisDB, redis_db)


async def get_chat(chat_id: Union[str, int], ttl: int = 86400) -> Chat:
    if not redis_db:
        return await bot.app.bot.get_chat(chat_id)
    qname = f"bot:chat:{chat_id}"
    data = await redis_db.client.get(qname)
    if data:
        json_data = json.loads(data)
        return Chat.de_json(json_data, bot.app.bot)
    chat_info = await bot.app.bot.get_chat(chat_id)
    await redis_db.client.set(qname, chat_info.to_json())
    await redis_db.client.expire(qname, ttl)
    return chat_info


def get_all_args(context: CallbackContext) -> List[str]:
    args = context.args
    match = context.match
    if args is None:
        if match is not None:
            groups = match.groups()
            return list(groups)
    else:
        if len(args) >= 1:
            return args
    return []
