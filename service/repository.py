from typing import List

from model.base import ServiceEnum
from service.base import CreateUserInfoDBDataFromSQLData, UserInfoData, CreatCookieDictFromSQLData, \
    CreatQuestionFromSQLData, QuestionData, AnswerData, CreatAnswerFromSQLData
from utils.mysql import MySQL


class AsyncRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def update_cookie(self, user_id: int, cookie: str, service: ServiceEnum):
        if service == ServiceEnum.HYPERION:
            query = """
                                UPDATE `mihoyo_cookie`
                                SET cookie=%s
                                WHERE user_id=%s;
                    """
        elif service == ServiceEnum.HOYOLAB:
            query = """
                                UPDATE `hoyoverse_cookie`
                                SET cookie=%s
                                WHERE user_id=%s;
                    """
        else:
            query = ""
        query_args = (cookie, user_id)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def set_cookie(self, user_id: int, cookie: str, service: ServiceEnum):
        if service == ServiceEnum.HYPERION:
            query = """
                                INSERT INTO  `mihoyo_cookie`
                                (user_id,cookie)
                                VALUES
                                (%s,%s)
                                ON DUPLICATE KEY UPDATE
                                cookie=VALUES(cookie);
                    """
        elif service == ServiceEnum.HOYOLAB:
            query = """
                                INSERT INTO `hoyoverse_cookie`
                                (user_id,cookie)
                                VALUES
                                (%s,%s)
                                ON DUPLICATE KEY UPDATE
                                cookie=VALUES(cookie);
                    """
        else:
            raise ValueError()
        query_args = (user_id, cookie)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def set_user_info(self, user_id: int, mihoyo_game_uid: int, hoyoverse_game_uid: int, service: int):
        query = """
                        INSERT INTO `user`
                        (user_id,mihoyo_game_uid,hoyoverse_game_uid,service)
                        VALUES
                        (%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE
                        mihoyo_game_uid=VALUES(mihoyo_game_uid),
                        hoyoverse_game_uid=VALUES(hoyoverse_game_uid),
                        service=VALUES(service);
                """
        query_args = (user_id, mihoyo_game_uid, hoyoverse_game_uid, service)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def read_mihoyo_cookie(self, user_id) -> dict:
        query = """
                    SELECT cookie
                    FROM `mihoyo_cookie`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return {}
        return CreatCookieDictFromSQLData(data[0])

    async def read_hoyoverse_cookie(self, user_id) -> dict:
        query = """
                    SELECT cookie
                    FROM `hoyoverse_cookie`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return {}
        return CreatCookieDictFromSQLData(data[0])

    async def read_user_info(self, user_id) -> UserInfoData:
        query = """
                    SELECT user_id,mihoyo_game_uid,hoyoverse_game_uid,service
                    FROM `user`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return UserInfoData()
        return CreateUserInfoDBDataFromSQLData(data[0])

    async def read_question_list(self) -> List[QuestionData]:
        query = """
                    SELECT id,question
                    FROM `question`
                """
        query_args = ()
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)

    async def read_answer_form_question_id(self, question_id: int) -> List[AnswerData]:
        query = """
                    SELECT id,question_id,is_correct,answer
                    FROM `answer`
                    WHERE question_id=%s;
                """
        query_args = (question_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatAnswerFromSQLData(data)

    async def save_question(self, question: str):
        query = """
                    INSERT INTO `question`
                    (question)
                    VALUES
                    (%s)
                """
        query_args = (question,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def read_question(self, question: str) -> QuestionData:
        query = """
                    SELECT id,question
                    FROM `question`
                    WHERE question=%s;
                """
        query_args = (question,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)[0]

    async def save_answer(self, question_id: int, is_correct: int, answer: str):
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

    async def add_admin(self, user_id: int):
        query = """
                            INSERT INTO `admin`
                            (user_id)
                            VALUES
                            (%s)
                """
        query_args = (user_id,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def get_admin(self) -> List[int]:
        query = """
                        SELECT user_id
                        FROM `admin`
                """
        query_args = ()
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return []
        return [i[0] for i in data]
