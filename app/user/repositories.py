from app.user.models import User
from model.base import ServiceEnum
from utils.error import NotFoundError
from utils.mysql import MySQL


class UserRepository:
    def __init__(self, mysql: MySQL):
        self.mysql = mysql

    async def get_by_user_id(self, user_id: int) -> User:
        query = """
        SELECT user_id,mihoyo_game_uid,hoyoverse_game_uid,service
        FROM `user`
        WHERE user_id=%s;"""
        query_args = (user_id,)
        data = await self.mysql.execute_and_fetchall(query, query_args)
        if len(data) == 0:
            raise UserNotFoundError(user_id)
        (user_id, yuanshen_game_uid, genshin_game_uid, default_service) = data
        return User(user_id, yuanshen_game_uid, genshin_game_uid, ServiceEnum(default_service))


class UserNotFoundError(NotFoundError):
    entity_name: str = "User"
    entity_value_name: str = "id"
