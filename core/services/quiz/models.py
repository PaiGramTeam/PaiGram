from typing import List, Optional

from pydantic import BaseModel
from sqlmodel import Column, Field, ForeignKey, Integer, SQLModel

__all__ = ("Answer", "AnswerDB", "Question", "QuestionDB")


class AnswerDB(SQLModel, table=True):
    __tablename__ = "answer"
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")

    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    question_id: Optional[int] = Field(
        sa_column=Column(Integer, ForeignKey("question.id", ondelete="RESTRICT", onupdate="RESTRICT"))
    )
    is_correct: Optional[bool] = Field()
    text: Optional[str] = Field()


class QuestionDB(SQLModel, table=True):
    __tablename__ = "question"
    __table_args__ = dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci")

    id: Optional[int] = Field(
        default=None, primary_key=True, sa_column=Column(Integer, primary_key=True, autoincrement=True)
    )
    text: Optional[str] = Field()


class Answer(BaseModel):
    answer_id: int = 0
    question_id: int = 0
    is_correct: bool = True
    text: str = ""

    def to_database_data(self) -> AnswerDB:
        return AnswerDB(id=self.answer_id, question_id=self.question_id, text=self.text, is_correct=self.is_correct)

    @classmethod
    def de_database_data(cls, data: AnswerDB) -> Optional["Answer"]:
        return cls(answer_id=data.id, question_id=data.question_id, text=data.text, is_correct=data.is_correct)


class Question(BaseModel):
    question_id: int = 0
    text: str = ""
    answers: List[Answer] = []

    def to_database_data(self) -> QuestionDB:
        return QuestionDB(text=self.text, id=self.question_id)

    @classmethod
    def de_database_data(cls, data: QuestionDB) -> Optional["Question"]:
        return cls(question_id=data.id, text=data.text)
