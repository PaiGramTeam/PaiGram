from typing import List, Optional

from sqlmodel import SQLModel, Field, Column, Integer, ForeignKey

from utils.baseobject import BaseObject
from utils.typedefs import JSONDict


class AnswerDB(SQLModel, table=True):
    __tablename__ = 'answer'
    __table_args__ = dict(mysql_charset='utf8mb4', mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    question_id: Optional[int] = Field(
        sa_column=Column(
            Integer,
            ForeignKey("question.id", ondelete="RESTRICT", onupdate="RESTRICT")
        )
    )
    is_correct: Optional[bool] = Field()
    text: Optional[str] = Field()


class QuestionDB(SQLModel, table=True):
    __tablename__ = 'question'
    __table_args__ = dict(mysql_charset='utf8mb4', mysql_collate="utf8mb4_general_ci")

    id: int = Field(primary_key=True)
    text: Optional[str] = Field()


class Answer(BaseObject):
    def __init__(self, answer_id: int = 0, question_id: int = 0, is_correct: bool = True, text: str = ""):
        """Answer类

        :param answer_id: 答案ID
        :param question_id: 与之对应的问题ID
        :param is_correct: 该答案是否正确
        :param text: 答案文本
        """
        self.answer_id = answer_id
        self.question_id = question_id
        self.text = text
        self.is_correct = is_correct

    __slots__ = ("answer_id", "question_id", "text", "is_correct")

    def to_database_data(self) -> AnswerDB:
        data = AnswerDB()
        data.id = self.answer_id
        data.question_id = self.question_id
        data.text = self.text
        data.is_correct = self.is_correct
        return data

    @classmethod
    def de_database_data(cls, data: Optional[AnswerDB]) -> Optional["Answer"]:
        if data is None:
            return cls()
        return cls(answer_id=data.id, question_id=data.question_id, text=data.text, is_correct=data.is_correct)


class Question(BaseObject):
    def __init__(self, question_id: int = 0, text: str = "", answers: List[Answer] = None):
        """Question类

        :param question_id: 问题ID
        :param text: 问题文本
        :param answers: 答案列表
        """
        self.question_id = question_id
        self.text = text
        self.answers = [] if answers is None else answers

    def to_database_data(self) -> QuestionDB:
        data = QuestionDB()
        data.text = self.text
        data.id = self.question_id
        return data

    @classmethod
    def de_database_data(cls, data: Optional[QuestionDB]) -> Optional["Question"]:
        if data is None:
            return cls()
        return cls(question_id=data.id, text=data.text)

    def to_dict(self) -> JSONDict:
        data = super().to_dict()
        if self.answers:
            data["answers"] = [e.to_dict() for e in self.answers]
        return data

    @classmethod
    def de_json(cls, data: Optional[JSONDict]) -> Optional["Question"]:
        data = cls._parse_data(data)
        if not data:
            return None
        data["answers"] = Answer.de_list(data.get("answers"))
        return cls(**data)

    __slots__ = ("question_id", "text", "answers")
