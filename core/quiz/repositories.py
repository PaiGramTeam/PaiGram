from typing import List

from sqlmodel import select

from core.base.mysql import MySQL

from .models import AnswerDB, QuestionDB


class QuizRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_question_list(self) -> List[QuestionDB]:
        async with self.mysql.Session() as session:
            query = select(QuestionDB)
            results = await session.exec(query)
            questions = results.all()
            return questions

    async def get_answers_from_question_id(self, question_id: int) -> List[AnswerDB]:
        async with self.mysql.Session() as session:
            query = select(AnswerDB).where(AnswerDB.question_id == question_id)
            results = await session.exec(query)
            answers = results.all()
            return answers

    async def add_question(self, question: QuestionDB):
        async with self.mysql.Session() as session:
            session.add(question)
            await session.commit()

    async def get_question_by_text(self, text: str) -> QuestionDB:
        async with self.mysql.Session() as session:
            query = select(QuestionDB).where(QuestionDB.text == text)
            results = await session.exec(query)
            question = results.first()
            return question[0]

    async def add_answer(self, answer: AnswerDB):
        async with self.mysql.Session() as session:
            session.add(answer)
            await session.commit()

    async def delete_question_by_id(self, question_id: int):
        async with self.mysql.Session() as session:
            statement = select(QuestionDB).where(QuestionDB.id == question_id)
            results = await session.exec(statement)
            question = results.one()
            await session.delete(question)

    async def delete_answer_by_id(self, answer_id: int):
        async with self.mysql.Session() as session:
            statement = select(AnswerDB).where(AnswerDB.id == answer_id)
            results = await session.exec(statement)
            answer = results.one()
            await session.delete(answer)
