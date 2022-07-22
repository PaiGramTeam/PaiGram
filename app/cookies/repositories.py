import ujson

from app.exception import NotFoundError
from model.base import ServiceEnum
from utils.mysql import MySQL


class CookiesRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def update_cookie(self, user_id: int, cookies: str, default_service: ServiceEnum):
        if default_service == ServiceEnum.HYPERION:
            query = """
            UPDATE `mihoyo_cookie`
            SET cookie=%s
            WHERE user_id=%s;
            """
        elif default_service == ServiceEnum.HOYOLAB:
            query = """
            UPDATE `hoyoverse_cookie`
            SET cookie=%s
            WHERE user_id=%s;
            """
        else:
            raise DefaultServiceNotFoundError(default_service.name)
        query_args = (cookies, user_id)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def set_cookie(self, user_id: int, cookies: str, default_service: ServiceEnum):
        if default_service == ServiceEnum.HYPERION:
            query = """
            INSERT INTO  `mihoyo_cookie`
            (user_id,cookie)
            VALUES
            (%s,%s)
            ON DUPLICATE KEY UPDATE
            cookie=VALUES(cookie);
            """
        elif default_service == ServiceEnum.HOYOLAB:
            query = """
            INSERT INTO `hoyoverse_cookie`
            (user_id,cookie)
            VALUES
            (%s,%s)
            ON DUPLICATE KEY UPDATE
            cookie=VALUES(cookie);
            """
        else:
            raise DefaultServiceNotFoundError(default_service.name)
        query_args = (user_id, cookies)
        await self.mysql.execute_and_fetchall(query, query_args)

    async def read_cookies(self, user_id, default_service: ServiceEnum) -> dict:
        if default_service == ServiceEnum.HYPERION:
            query = """
            SELECT cookie
            FROM `mihoyo_cookie`
            WHERE user_id=%s;
            """
        elif default_service == ServiceEnum.HOYOLAB:
            query = """
            SELECT cookie
            FROM `hoyoverse_cookie`
            WHERE user_id=%s;;
            """
        else:
            raise DefaultServiceNotFoundError(default_service.name)
        query_args = (user_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            return {}
        (cookies,) = data
        return ujson.loads(cookies)


class DefaultServiceNotFoundError(NotFoundError):
    entity_name: str = "ServiceEnum"
    entity_value_name: str = "default_service"
