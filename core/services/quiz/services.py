import asyncio
from typing import List

from core.base_service import BaseService
from core.services.quiz.cache import QuizCache
from core.services.quiz.models import Answer, Question
from core.services.quiz.repositories import QuizRepository

__all__ = ("QuizService",)


class QuizService(BaseService):
    def __init__(self, repository: QuizRepository, cache: QuizCache):
        self._repository = repository
        self._cache = cache
        self.lock = asyncio.Lock()

    async def get_quiz_from_database(self) -> List[Question]:
        """从数据库获取问题列表
        :return: Question List
        """
        temp: list = []
        question_list = await self._repository.get_question_list()
        for question in question_list:
            question_id = question.id
            answers = await self._repository.get_answers_from_question_id(question_id)
            data = Question.de_database_data(question)
            data.answers = [Answer.de_database_data(a) for a in answers]
            temp.append(data)
        return temp

    async def save_quiz(self, data: Question):
        await self._repository.get_question_by_text(data.text)
        for answers in data.answers:
            await self._repository.add_answer(answers.to_database_data())

    async def refresh_quiz(self) -> int:
        """从数据库刷新问题到Redis缓存 线程安全
        :return: 已经缓存问题的数量
        """
        # 只允许一个线程访问该区域 让数据被安全有效的访问
        async with self.lock:
            question_list = await self.get_quiz_from_database()
            await self._cache.del_all_question()
            question_count = await self._cache.add_question(question_list)
            await self._cache.del_all_answer()
            for question in question_list:
                await self._cache.add_answer(question.answers)
            return question_count

    async def get_question_id_list(self) -> List[int]:
        return [int(question_id) for question_id in await self._cache.get_all_question_id_list()]

    async def get_answer(self, answer_id: int) -> Answer:
        return await self._cache.get_one_answer(answer_id)

    async def get_question(self, question_id: int) -> Question:
        return await self._cache.get_one_question(question_id)

    async def delete_question_by_id(self, question_id: int):
        return await self._repository.delete_question_by_id(question_id)

    async def delete_answer_by_id(self, answer_id: int):
        return await self._repository.delete_answer_by_id(answer_id)
