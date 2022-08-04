from typing import List

from app.quiz.models import Question, Answer
from utils.mysql import MySQL


class QuizRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_question_list(self) -> List[Question]:
        pass

    async def get_answer_form_question_id(self, question_id: int) -> List[Answer]:
        pass

    async def add_question(self, question: str):
        pass

    async def get_question(self, question: str) -> Question:
        pass

    async def add_answer(self, question_id: int, is_correct: int, answer: str):
        pass

    async def delete_question(self, question_id: int):
        pass

    async def delete_answer(self, answer_id: int):
        pass

    async def delete_admin(self, user_id: int):
        pass