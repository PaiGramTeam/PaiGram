from typing import List

from app.quiz.base import CreatQuestionFromSQLData, CreatAnswerFromSQLData
from app.quiz.models import Question, Answer
from utils.mysql import MySQL


class QuizRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_question_list(self) -> List[Question]:
        query = """
        SELECT id,question
        FROM `question`
        """
        query_args = ()
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)

    async def get_answer_form_question_id(self, question_id: int) -> List[Answer]:
        query = """
        SELECT id,question_id,is_correct,answer
        FROM `answer`
        WHERE question_id=%s;
        """
        query_args = (question_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatAnswerFromSQLData(data)

    async def add_question(self, question: str):
        query = """
        INSERT INTO `question`
        (question)
        VALUES
        (%s)
        """
        query_args = (question,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def get_question(self, question: str) -> Question:
        query = """
        SELECT id,question
        FROM `question`
        WHERE question=%s;
        """
        query_args = (question,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)[0]

    async def add_answer(self, question_id: int, is_correct: int, answer: str):
        query = """
        INSERT INTO `answer`
        (question_id,is_correct,answer)
        VALUES
        (%s,%s,%s)
        """
        query_args = (question_id, is_correct, answer)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def delete_question(self, question_id: int):
        query = """
        DELETE FROM `question`
        WHERE id=%s;
        """
        query_args = (question_id,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def delete_answer(self, answer_id: int):
        query = """
        DELETE FROM `answer`
        WHERE id=%s;
        """
        query_args = (answer_id,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def delete_admin(self, user_id: int):
        query = """
        DELETE FROM `admin`
        WHERE user_id=%s;
        """
        query_args = (user_id,)
        await self.mysql.execute_and_fetchall(query, query_args)