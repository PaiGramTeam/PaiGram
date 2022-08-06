from typing import List

import ujson

from .cache import QuizCache
from .models import Question
from .repositories import QuizRepository


class QuizService:
    def __init__(self, repository: QuizRepository, cache: QuizCache):
        self._repository = repository
        self._cache = cache

    async def get_quiz(self) -> List[Question]:
        """从数据库获取问题列表
        :return:
        """
        question_list = await self._repository.get_question_list()
        for question in question_list:
            question_id = question.question_id
            answers = await self._repository.get_answer_form_question_id(question_id)
            question.answers = answers
        return question_list

    async def save_quiz(self, data: Question):
        await self._repository.get_question(data.text)
        question = await self._repository.get_question(data.text)
        for answers in data.answers:
            await self._repository.add_answer(question.question_id, answers.is_correct, answers.text)

    async def refresh_quiz(self) -> int:
        question_list = await self.get_quiz()
        await self._cache.del_all_question()
        question_count = await self._cache.add_question(question_list)
        await self._cache.del_all_answer()
        for question in question_list:
            await self._cache.add_answer(question.answers)
        return question_count

    async def get_question_id_list(self) -> List[int]:
        return [int(question_id) for question_id in await self._cache.get_all_question_id_list()]

    async def get_answer(self, answer_id: int):
        data = await self._cache.get_one_answer(answer_id)
        return ujson.loads(data)

    async def get_question(self, question_id: int) -> Question:
        return await self._cache.get_one_question(question_id)
