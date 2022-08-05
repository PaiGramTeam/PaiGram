from typing import List, Optional

from model.baseobject import BaseObject
from model.types import JSONDict


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

    def to_dict(self) -> JSONDict:
        data = super().to_dict()
        if self.answers:
            data["sub_item"] = [e.to_dict() for e in self.answers]
        return data

    @classmethod
    def de_json(cls, data: Optional[JSONDict]) -> Optional["Question"]:
        data = cls._parse_data(data)
        if not data:
            return None
        data["sub_item"] = Answer.de_list(data.get("sub_item"))
        return cls(**data)

    __slots__ = ("question_id", "text", "answers")
