from typing import List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.base_service import BaseService
from core.dependence.database import Database
from core.services.quiz.models import AnswerDB, QuestionDB

__all__ = ("QuizRepository",)


class QuizRepository(BaseService.Component):
    def __init__(self, database: Database):
        self.engine = database.engine

    async def get_question_list(self) -> List[QuestionDB]:
        async with AsyncSession(self.engine) as session:
            query = select(QuestionDB)
            results = await session.exec(query)
            return results.all()

    async def get_answers_from_question_id(self, question_id: int) -> List[AnswerDB]:
        async with AsyncSession(self.engine) as session:
            query = select(AnswerDB).where(AnswerDB.question_id == question_id)
            results = await session.exec(query)
            return results.all()

    async def add_question(self, question: QuestionDB):
        async with AsyncSession(self.engine) as session:
            session.add(question)
            await session.commit()

    async def get_question_by_text(self, text: str) -> QuestionDB:
        async with AsyncSession(self.engine) as session:
            query = select(QuestionDB).where(QuestionDB.text == text)
            results = await session.exec(query)
            return results.first()

    async def add_answer(self, answer: AnswerDB):
        async with AsyncSession(self.engine) as session:
            session.add(answer)
            await session.commit()

    async def delete_question_by_id(self, question_id: int):
        async with AsyncSession(self.engine) as session:
            statement = select(QuestionDB).where(QuestionDB.id == question_id)
            results = await session.exec(statement)
            question = results.one()
            await session.delete(question)

    async def delete_answer_by_id(self, answer_id: int):
        async with AsyncSession(self.engine) as session:
            statement = select(AnswerDB).where(AnswerDB.id == answer_id)
            results = await session.exec(statement)
            answer = results.one()
            await session.delete(answer)
