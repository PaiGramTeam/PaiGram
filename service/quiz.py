from typing import List

import ujson

from service.repository import AsyncRepository
from service.cache import RedisCache
from service.base import QuestionData


class QuizService:
    def __init__(self, repository: AsyncRepository, cache: RedisCache):
        self.repository = repository
        self.cache = cache

    async def get_quiz_for_db(self) -> List[QuestionData]:
        question_list = await self.repository.read_question_list()
        for question in question_list:
            question_id = question.question_id
            answer = await self.repository.read_answer_form_question_id(question_id)
            question.answer = answer
        return question_list

    async def save_quiz(self, data: QuestionData):
        await self.repository.save_question(data.question)
        question = await self.repository.read_question(data.question)
        for answer in data.answer:
            await self.repository.save_answer(question.question_id, answer.is_correct, answer.answer)

    async def refresh_quiz(self) -> int:
        question_list = await self.get_quiz_for_db()
        await self.cache.del_all_question()
        question_count = await self.cache.set_question(question_list)
        await self.cache.del_all_answer()
        for question in question_list:
            await self.cache.set_answer(question.answer)
        return question_count

    async def get_question_id_list(self) -> List[int]:
        return [int(question_id) for question_id in await self.cache.get_all_question_id_list()]

    async def get_question(self, question_id: int):
        data = await self.cache.get_one_question(question_id)
        return ujson.loads(data)

    async def get_answer(self, answer_id: int):
        data = await self.cache.get_one_answer(answer_id)
        return ujson.loads(data)