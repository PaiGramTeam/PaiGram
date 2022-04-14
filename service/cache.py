from typing import List

import ujson
from redis import asyncio as aioredis

from service.base import QuestionData, AnswerData


class RedisCache:

    def __init__(self, host="127.0.0.1", port=6379, db=0):
        self.rdb = aioredis.Redis(host=host, port=port, db=db)
        self.ttl = 600
        self.key_prefix = "paimon_bot"

    async def get_chat_admin(self, char_id: int):
        qname = f"group:admin_list:{char_id}"
        return [int(str_id) for str_id in await self.rdb.lrange(qname, 0, -1)]

    async def set_chat_admin(self, char_id: int, admin_list: List[int]):
        qname = f"group:admin_list:{char_id}"
        await self.rdb.ltrim(qname, 1, 0)
        await self.rdb.lpush(qname, *admin_list)
        await self.rdb.expire(qname, 60)
        count = await self.rdb.llen(qname)
        return count

    async def get_all_question(self) -> List[str]:
        qname = "quiz:question"
        data_list = [qname + f":{question_id}" for question_id in await self.rdb.lrange(qname + "id_list", 0, -1)]
        return await self.rdb.mget(data_list)

    async def get_all_question_id_list(self) -> List[str]:
        qname = "quiz:question:id_list"
        return await self.rdb.lrange(qname, 0, -1)

    async def get_one_question(self, question_id: int) -> str:
        qname = f"quiz:question:{question_id}"
        return await self.rdb.get(qname)

    async def get_one_answer(self, answer_id: int) -> str:
        qname = f"quiz:answer:{answer_id}"
        return await self.rdb.get(qname)

    async def set_question(self, question_list: List[QuestionData] = None):
        qname = "quiz:question"

        def json_dumps(_question: QuestionData) -> str:
            data = {
                "question_id": _question.question_id,
                "question": _question.question,
                "answer_id": [answer.answer_id for answer in _question.answer]
            }
            return ujson.dumps(data)

        for question in question_list:
            await self.rdb.set(qname + f":{question.question_id}", json_dumps(question))

        question_id_list = [question.question_id for question in question_list]
        await self.rdb.lpush(qname + f":id_list", *question_id_list)
        return await self.rdb.llen(qname + ":id_list")

    async def del_all_question(self, answer_list: List[AnswerData] = None):
        qname = "quiz:question"
        keys = await self.rdb.keys(qname + "*")
        if keys is not None:
            for key in keys:
                await self.rdb.delete(key)

    async def del_all_answer(self, answer_list: List[AnswerData] = None):
        qname = "quiz:answer"
        keys = await self.rdb.keys(qname + "*")
        if keys is not None:
            for key in keys:
                await self.rdb.delete(key)

    async def set_answer(self, answer_list: List[AnswerData] = None):
        qname = "quiz:answer"

        def json_dumps(_answer: AnswerData):
            return ujson.dumps(obj=_answer.__dict__)

        for answer in answer_list:
            await self.rdb.set(qname + f":{answer.answer_id}", json_dumps(answer))

        answer_id_list = [answer.answer_id for answer in answer_list]
        await self.rdb.lpush(qname + ":id_list", *answer_id_list)
        return await self.rdb.llen(qname + ":id_list")

    async def get_str_list(self, qname: str):
        return [str(str_data, encoding="utf-8") for str_data in await self.rdb.lrange(qname, 0, -1)]

    async def set_str_list(self, qname: str, str_list: List[str], ttl: int = 60):
        await self.rdb.ltrim(qname, 1, 0)
        await self.rdb.lpush(qname, *str_list)
        if ttl != -1:
            await self.rdb.expire(qname, ttl)
        count = await self.rdb.llen(qname)
        return count

    async def get_int_list(self, qname: str):
        return [int(str_data) for str_data in await self.rdb.lrange(qname, 0, -1)]

    async def set_int_list(self, qname: str, str_list: List[int], ttl: int = 60):
        await self.rdb.ltrim(qname, 1, 0)
        await self.rdb.lpush(qname, *str_list)
        if ttl != -1:
            await self.rdb.expire(qname, ttl)
        count = await self.rdb.llen(qname)
        return count
