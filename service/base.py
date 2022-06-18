from typing import List

import ujson

from model.base import ServiceEnum


class UserInfoDataEx:
    def __init__(self, user_id: int = 0, mihoyo_game_uid: int = 0, hoyoverse_game_uid: int = 0,
                 service: ServiceEnum = ServiceEnum.NULL, hoyoverse_cookie=None,
                 mihoyo_cookie=None):
        if hoyoverse_cookie is None:
            hoyoverse_cookie = {}
        if mihoyo_cookie is None:
            mihoyo_cookie = {}
        self.user_id = user_id
        self.mihoyo_game_uid = mihoyo_game_uid
        self.hoyoverse_game_uid = hoyoverse_game_uid
        self.service = service
        self.hoyoverse_cookie = hoyoverse_cookie
        self.mihoyo_cookie = mihoyo_cookie


class UserInfoData:
    def __init__(self, user_id: int = 0, mihoyo_game_uid: int = 0, hoyoverse_game_uid: int = 0,
                 service: ServiceEnum = ServiceEnum.NULL, hoyoverse_cookie=None,
                 mihoyo_cookie=None):
        if hoyoverse_cookie is None:
            hoyoverse_cookie = {}
        if mihoyo_cookie is None:
            mihoyo_cookie = {}
        self.user_id = user_id
        self.mihoyo_game_uid = mihoyo_game_uid
        self.hoyoverse_game_uid = hoyoverse_game_uid
        self.service = service
        self.hoyoverse_cookie = hoyoverse_cookie
        self.mihoyo_cookie = mihoyo_cookie


class AnswerData:
    def __init__(self, answer_id: int = 0, question_id: int = 0, is_correct: bool = True, answer: str = ""):
        self.answer_id = answer_id
        self.question_id = question_id
        self.answer = answer
        self.is_correct = is_correct


class QuestionData:
    def __init__(self, question_id: int = 0, question: str = "", answer: List[AnswerData] = None):
        self.question_id = question_id
        self.question = question
        self.answer = [] if answer is None else answer

    def json_dumps(self):
        data = {
            "question_id": self.question_id,
            "question": self.question,
            "answer": [{
                "answer_id": answer.answer_id,
                "question_id": answer.question_id,
                "answer": answer.answer,
                "is_correct": answer.is_correct,
            } for answer in self.answer]
        }
        return ujson.dumps(data)

    def json_loads(self, data: str):
        json_data = ujson.loads(data)
        self.question_id = json_data["question_id"]
        self.question = json_data["question"]
        answers = json_data["answer"]
        for answer in answers:
            self.answer.append(
                AnswerData(
                    answer["answer_id"],
                    answer["question_id"],
                    answer["is_correct"],
                    answer["answer"]
                )
            )
        return self


def CreateUserInfoDBDataFromSQLData(data: tuple) -> UserInfoData:
    (user_id, mihoyo_game_uid, hoyoverse_game_uid, service) = data
    return UserInfoData(user_id=user_id, mihoyo_game_uid=mihoyo_game_uid, hoyoverse_game_uid=hoyoverse_game_uid,
                        service=ServiceEnum(service))


def CreatCookieDictFromSQLData(data: tuple) -> dict:
    (cookie,) = data
    return ujson.loads(cookie)


def CreatQuestionFromSQLData(data: tuple) -> List[QuestionData]:
    temp_list = []
    for temp_data in data:
        (question_id, question) = temp_data
        temp_list.append(QuestionData(question_id, question))
    return temp_list


def CreatAnswerFromSQLData(data: tuple) -> List[AnswerData]:
    temp_list = []
    for temp_data in data:
        (answer_id, question_id, is_correct, answer) = temp_data
        temp_list.append(AnswerData(answer_id, question_id, is_correct, answer))
    return temp_list
