from typing import List

from app.quiz.models import Question, Answer


def CreatQuestionFromSQLData(data: tuple) -> List[Question]:
    temp_list = []
    for temp_data in data:
        (question_id, text) = temp_data
        temp_list.append(Question(question_id, text))
    return temp_list

def CreatAnswerFromSQLData(data: tuple) -> List[Answer]:
    temp_list = []
    for temp_data in data:
        (answer_id, question_id, is_correct, text) = temp_data
        temp_list.append(Answer(answer_id, question_id, is_correct, text))
    return temp_list
