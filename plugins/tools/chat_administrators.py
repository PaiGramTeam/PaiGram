from typing import Union, Tuple, TYPE_CHECKING, List, Any

from telegram import ChatMember

try:
    import ujson as jsonlib
except ImportError:
    import json as jsonlib


if TYPE_CHECKING:
    from redis import Redis

    from telegram.ext import ContextTypes


class ChatAdministrators:
    QNAME = "plugin:group_captcha:chat_administrators"
    TTL = 1 * 60 * 60

    @staticmethod
    async def get_chat_administrators(
        cache: "Redis",
        context: "ContextTypes.DEFAULT_TYPE",
        chat_id: Union[str, int],
    ) -> Union[Tuple[ChatMember, ...], Any]:
        qname = f"{ChatAdministrators.QNAME}:{chat_id}"
        result: "List[bytes]" = await cache.lrange(qname, 0, -1)
        if len(result) > 0:
            return ChatMember.de_list([jsonlib.loads(str(_data, encoding="utf-8")) for _data in result], context.bot)
        chat_administrators = await context.bot.get_chat_administrators(chat_id)
        async with cache.pipeline(transaction=True) as pipe:
            for chat_administrator in chat_administrators:
                await pipe.lpush(qname, chat_administrator.to_json())
            await pipe.expire(qname, ChatAdministrators.TTL)
            await pipe.execute()
        return chat_administrators

    @staticmethod
    def is_admin(chat_administrators: Tuple[ChatMember], user_id: int) -> bool:
        return any(admin.user.id == user_id for admin in chat_administrators)
