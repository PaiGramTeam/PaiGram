from typing import List

from app.quiz.models import Question, Answer


def CreatQuestionFromSQLData(data: tuple) -> List[Question]:
    temp_list = []
    for temp_data in data:
        (question_id, question) = temp_data
        temp_list.append(Question(question_id, question))
    return temp_list

def CreatAnswerFromSQLData(data: tuple) -> List[Answer]:
    temp_list = []
    for temp_data in data:
        (answer_id, question_id, is_correct, answer) = temp_data
        temp_list.append(Answer(answer_id, question_id, is_correct, answer))
    return temp_list
