from typing import List

from core.base_service import BaseService
from core.dependence.redisdb import RedisDB
from core.services.quiz.models import Answer, Question

__all__ = ("QuizCache",)


class QuizCache(BaseService.Component):
    def __init__(self, redis: RedisDB):
        self.client = redis.client
        self.question_qname = "quiz:question"
        self.answer_qname = "quiz:answer"

    async def get_all_question(self) -> List[Question]:
        temp_list = []
        qname = self.question_qname + "id_list"
        data_list = [self.question_qname + f":{question_id}" for question_id in await self.client.lrange(qname, 0, -1)]
        data = await self.client.mget(data_list)
        for i in data:
            temp_list.append(Question.parse_raw(i))
        return temp_list

    async def get_all_question_id_list(self) -> List[str]:
        qname = self.question_qname + ":id_list"
        return await self.client.lrange(qname, 0, -1)

    async def get_one_question(self, question_id: int) -> Question:
        qname = f"{self.question_qname}:{question_id}"
        data = await self.client.get(qname)
        json_data = str(data, encoding="utf-8")
        return Question.parse_raw(json_data)

    async def get_one_answer(self, answer_id: int) -> Answer:
        qname = f"{self.answer_qname}:{answer_id}"
        data = await self.client.get(qname)
        json_data = str(data, encoding="utf-8")
        return Answer.parse_raw(json_data)

    async def add_question(self, question_list: List[Question] = None) -> int:
        if not question_list:
            return 0
        for question in question_list:
            await self.client.set(f"{self.question_qname}:{question.question_id}", question.json())
        question_id_list = [question.question_id for question in question_list]
        await self.client.lpush(f"{self.question_qname}:id_list", *question_id_list)
        return await self.client.llen(f"{self.question_qname}:id_list")

    async def del_all_question(self):
        keys = await self.client.keys(f"{self.question_qname}*")
        if keys is not None:
            for key in keys:
                await self.client.delete(key)

    async def del_all_answer(self):
        keys = await self.client.keys(f"{self.answer_qname}*")
        if keys is not None:
            for key in keys:
                await self.client.delete(key)

    async def add_answer(self, answer_list: List[Answer] = None) -> int:
        if not answer_list:
            return 0
        for answer in answer_list:
            await self.client.set(f"{self.answer_qname}:{answer.answer_id}", answer.json())
        answer_id_list = [answer.answer_id for answer in answer_list]
        await self.client.lpush(f"{self.answer_qname}:id_list", *answer_id_list)
        return await self.client.llen(f"{self.answer_qname}:id_list")
