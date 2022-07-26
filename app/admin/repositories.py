from typing import List

from utils.mysql import MySQL


class BotAdminRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def delete_by_user_id(self, user_id: int):
        query = """
        DELETE FROM `admin`
        WHERE user_id=%s;
        """
        query_args = (user_id,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def add_by_user_id(self, user_id: int):
        query = """
        INSERT INTO `admin`
        (user_id)
        VALUES
        (%s)
        """
        query_args = (user_id,)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def get_by_user_id(self) -> List[int]:
        query = """
        SELECT user_id
        FROM `admin`
        """
        query_args = ()
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return []
        return [i[0] for i in data]