from typing import List

import aiomysql

from model.base import ServiceEnum
from service.base import CreateUserInfoDBDataFromSQLData, UserInfoData, CreatCookieDictFromSQLData, \
    CreatQuestionFromSQLData, QuestionData, AnswerData, CreatAnswerFromSQLData


class AsyncRepository:
    def __init__(self, mysql_host: str = "127.0.0.1", mysql_port: int = 3306, mysql_user: str = "root",
                 mysql_password: str = "", mysql_database: str = "", loop=None):
        self._mysql_database = mysql_database
        self._mysql_password = mysql_password
        self._mysql_user = mysql_user
        self._mysql_port = mysql_port
        self._mysql_host = mysql_host
        self._loop = loop
        self._sql_pool = None

    async def close(self):
        if self._sql_pool is None:
            return
        pool = self._sql_pool
        pool.close()
        self._sql_pool = None
        await pool.wait_closed()

    async def _get_pool(self):
        if self._sql_pool is None:
            self._sql_pool = await aiomysql.create_pool(
                host=self._mysql_host, port=self._mysql_port,
                user=self._mysql_user, password=self._mysql_password,
                db=self._mysql_database, loop=self._loop)
        return self._sql_pool

    async def _executemany(self, query, query_args):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            sql_cur = await conn.cursor()
            await sql_cur.executemany(query, query_args)
            rowcount = sql_cur.rowcount
            await sql_cur.close()
            await conn.commit()
        return rowcount

    async def _execute_and_fetchall(self, query, query_args):
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            sql_cur = await conn.cursor()
            await sql_cur.execute(query, query_args)
            result = await sql_cur.fetchall()
            await sql_cur.close()
            await conn.commit()
        return result

    async def update_cookie(self, user_id: int, cookie: str, service: ServiceEnum):
        if service == ServiceEnum.MIHOYO:
            query = f"""
                                UPDATE `mihoyo_cookie`
                                SET cookie=%s
                                WHERE user_id=%s;
                    """
        elif service == ServiceEnum.HOYOLAB:
            query = f"""
                                UPDATE `hoyoverse_cookie`
                                SET cookie=%s
                                WHERE user_id=%s;
                    """
        else:
            query = ""
        query_args = (cookie, user_id)
        await self._execute_and_fetchall(query, query_args)

    async def set_cookie(self, user_id: int, cookie: str, service: ServiceEnum):
        if service == ServiceEnum.MIHOYO:
            query = f"""
                                INSERT INTO  `mihoyo_cookie`
                                (user_id,cookie)
                                VALUES
                                (%s,%s)
                                ON DUPLICATE KEY UPDATE
                                cookie=VALUES(cookie);
                    """
        elif service == ServiceEnum.HOYOLAB:
            query = f"""
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
        await self._execute_and_fetchall(query, query_args)

    async def set_user_info(self, user_id: int, mihoyo_game_uid: int, hoyoverse_game_uid: int, service: int):
        query = f"""
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
        await self._execute_and_fetchall(query, query_args)

    async def read_mihoyo_cookie(self, user_id) -> dict:
        query = f"""
                    SELECT cookie
                    FROM `mihoyo_cookie`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self._execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return {}
        return CreatCookieDictFromSQLData(data[0])

    async def read_hoyoverse_cookie(self, user_id) -> dict:
        query = f"""
                    SELECT cookie
                    FROM `hoyoverse_cookie`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self._execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return {}
        return CreatCookieDictFromSQLData(data[0])

    async def read_user_info(self, user_id) -> UserInfoData:
        query = f"""
                    SELECT user_id,mihoyo_game_uid,hoyoverse_game_uid,service
                    FROM `user`
                    WHERE user_id=%s;
                """
        query_args = (user_id,)
        data = await self._execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return UserInfoData()
        return CreateUserInfoDBDataFromSQLData(data[0])

    async def read_question_list(self) -> List[QuestionData]:
        query = f"""
                    SELECT id,question
                    FROM `question`
                """
        query_args = ()
        data = await self._execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)

    async def read_answer_form_question_id(self, question_id: int) -> List[AnswerData]:
        query = f"""
                    SELECT id,question_id,is_correct,answer
                    FROM `answer`
                    WHERE question_id=%s;
                """
        query_args = (question_id,)
        data = await self._execute_and_fetchall(query, query_args)
        return CreatAnswerFromSQLData(data)

    async def save_question(self, question: str):
        query = f"""
                    INSERT INTO `question`
                    (question)
                    VALUES
                    (%s)
                """
        query_args = (question,)
        await self._execute_and_fetchall(query, query_args)

    async def read_question(self, question: str) -> QuestionData:
        query = f"""
                    SELECT id,question
                    FROM `question`
                    WHERE question=%s;
                """
        query_args = (question,)
        data = await self._execute_and_fetchall(query, query_args)
        return CreatQuestionFromSQLData(data)[0]

    async def save_answer(self, question_id: int, is_correct: int, answer: str):
        query = f"""
                    INSERT INTO `answer`
                    (question_id,is_correct,answer)
                    VALUES
                    (%s,%s,%s)
                """
        query_args = (question_id, is_correct, answer)
        await self._execute_and_fetchall(query, query_args)

    async def delete_question(self, question_id: int):
        query = f"""
                    DELETE FROM `question`
                    WHERE id=%s;
                """
        query_args = (question_id,)
        await self._execute_and_fetchall(query, query_args)

    async def delete_answer(self, answer_id: int):
        query = f"""
                    DELETE FROM `answer`
                    WHERE id=%s;
                """
        query_args = (answer_id,)
        await self._execute_and_fetchall(query, query_args)

    async def delete_admin(self, user_id: int):
        query = f"""
                            DELETE FROM `admin`
                            WHERE user_id=%s;
                        """
        query_args = (user_id,)
        await self._execute_and_fetchall(query, query_args)

    async def add_admin(self, user_id: int):
        query = f"""
                            INSERT INTO `admin`
                            (user_id)
                            VALUES
                            (%s)
                """
        query_args = (user_id,)
        await self._execute_and_fetchall(query, query_args)

    async def get_admin(self) -> List[int]:
        query = f"""
                        SELECT user_id
                        FROM `admin`
                """
        query_args = ()
        data = await self._execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return []
        return list(data[0])
