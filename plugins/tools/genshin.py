import asyncio
import random
import re
from datetime import datetime, timedelta, time
from typing import Optional, Tuple, Union, TYPE_CHECKING

import genshin
from genshin.errors import GenshinException
from genshin.models import BaseCharacter
from genshin.models import CalculatorCharacterDetails
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, Field, String, Column, Integer, BigInteger, select, DateTime, func, delete, Index
from telegram.ext import ContextTypes

from core.basemodel import RegionEnum
from core.config import config
from core.dependence.database import Database
from core.dependence.redisdb import RedisDB
from core.error import ServiceNotFoundError
from core.plugin import Plugin
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.players.services import PlayersService
from core.services.users.services import UserService
from core.sqlmodel.session import AsyncSession
from utils.const import REGION_MAP
from utils.log import logger

if TYPE_CHECKING:
    from sqlalchemy import Table
    from genshin import Client as GenshinClient

__all__ = ("GenshinHelper", "PlayerNotFoundError", "CookiesNotFoundError")


class PlayerNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"User not found, user_id: {user_id}")


class CookiesNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"{user_id} cookies not found")


class CharacterDetailsSQLModel(SQLModel, table=True):
    __tablename__ = "character_details"
    __table_args__ = (
        Index("index_player_character", "player_id", "character_id", unique=True),
        dict(mysql_charset="utf8mb4", mysql_collate="utf8mb4_general_ci"),
    )
    id: Optional[int] = Field(default=None, sa_column=Column(Integer, primary_key=True, autoincrement=True))
    player_id: int = Field(sa_column=Column(BigInteger()))
    character_id: int = Field(sa_column=Column(BigInteger()))
    data: Optional[str] = Field(sa_column=Column(String(length=4096)))
    time_updated: Optional[datetime] = Field(sa_column=Column(DateTime, onupdate=func.now()))  # pylint: disable=E1102


class CharacterDetails(Plugin):
    def __init__(
        self,
        database: Database,
        redis: RedisDB,
    ) -> None:
        self.database = database
        self.redis = redis.client
        self.ttl = 60 * 60 * 6

    async def initialize(self) -> None:
        def fetch_and_update_objects(connection):
            if not self.database.engine.dialect.has_table(connection, table_name="character_details"):
                logger.info("正在创建角色详细信息表")
                table: "Table" = SQLModel.metadata.tables["character_details"]
                table.create(connection)
                logger.success("创建角色详细信息表成功")

        async with self.database.engine.begin() as conn:
            await conn.run_sync(fetch_and_update_objects)
        asyncio.create_task(self.save_character_details_task(max_ttl=None))
        self.application.job_queue.run_daily(self.del_old_data_job, time(hour=3, minute=0))
        self.application.job_queue.run_repeating(self.save_character_details_job, timedelta(hours=1))

    async def save_character_details_job(self, _: ContextTypes.DEFAULT_TYPE):
        await self.save_character_details()

    async def del_old_data_job(self, _: ContextTypes.DEFAULT_TYPE):
        await self.del_old_data(timedelta(days=7))

    async def del_old_data(self, expiration_time: timedelta):
        expire_time = datetime.now() - expiration_time
        statement = delete(CharacterDetailsSQLModel).where(CharacterDetailsSQLModel.time_updated <= expire_time)
        async with AsyncSession(self.database.engine) as session:
            await session.execute(statement)

    async def save_character_details_task(self, max_ttl: Optional[int] = 60 * 60):
        logger.info("正在从Redis中保存角色详细信息")
        try:
            await self.save_character_details(max_ttl)
        except SQLAlchemyError as exc:
            logger.error("写入到数据库失败 code[%s]", exc.code)
            logger.debug("写入到数据库失败", exc_info=exc)
        except Exception as exc:
            logger.error("save_character_details 执行失败", exc_info=exc)
        else:
            logger.success("从Redis中保存角色详细信息成功")

    async def save_character_details(self, max_ttl: Optional[int] = 60 * 60):
        keys = await self.redis.keys("plugins:character_details:*")
        for key in keys:
            key = str(key, encoding="utf-8")
            ttl = await self.redis.ttl(key)
            if max_ttl is None or (0 <= ttl <= max_ttl):
                try:
                    player_id, character_id = re.findall(r"\d+", key)
                except ValueError:
                    logger.warning("非法Key %s", key)
                    continue
                data = await self.redis.get(key)
                if data is None:
                    logger.warning("Redis key[%s] 数据未找到", key)  # 如果未找到可能因为处理过程中已经过期，导致该数据未回写到 MySQL
                    continue
                str_data = str(data, encoding="utf-8")
                async with AsyncSession(self.database.engine) as session:
                    statement = (
                        select(CharacterDetailsSQLModel)
                        .where(CharacterDetailsSQLModel.player_id == player_id)
                        .where(CharacterDetailsSQLModel.character_id == character_id)
                    )
                    results = await session.exec(statement)
                    sql_data = results.first()
                if sql_data is None:
                    sql_data = CharacterDetailsSQLModel(
                        player_id=player_id, character_id=character_id, data=str_data, time_updated=datetime.now()
                    )
                    async with AsyncSession(self.database.engine) as session:
                        session.add(sql_data)
                        await session.commit()
                else:
                    if sql_data.time_updated <= datetime.now() - timedelta(hours=2):
                        sql_data.data = str_data
                        sql_data.time_updated = datetime.now()
                        async with AsyncSession(self.database.engine) as session:
                            session.add(sql_data)
                            await session.commit()

    @staticmethod
    def get_qname(uid: int, character: int):
        return f"plugins:character_details:{uid}:{character}"

    async def get_character_details_for_redis(
        self,
        uid: int,
        character_id: int,
    ) -> Optional["CalculatorCharacterDetails"]:
        name = self.get_qname(uid, character_id)
        data = await self.redis.get(name)
        if data is None:
            return None
        json_data = str(data, encoding="utf-8")
        return CalculatorCharacterDetails.parse_raw(json_data)

    async def set_character_details_for_redis(self, uid: int, character_id: int, detail: "CalculatorCharacterDetails"):
        randint = random.randint(1, 30)  # nosec
        await self.redis.set(
            self.get_qname(uid, character_id), detail.json(), ex=self.ttl + randint * 60  # 使用随机数防止缓存雪崩
        )

    async def get_character_details_for_mysql(
        self,
        uid: int,
        character_id: int,
    ) -> Optional["CalculatorCharacterDetails"]:
        async with AsyncSession(self.database.engine) as session:
            statement = (
                select(CharacterDetailsSQLModel)
                .where(CharacterDetailsSQLModel.player_id == uid)
                .where(CharacterDetailsSQLModel.character_id == character_id)
            )
            results = await session.exec(statement)
            data = results.first()
            if data is not None:
                try:
                    return CalculatorCharacterDetails.parse_raw(data.data)
                except ValidationError as exc:
                    logger.error("解析数据出现异常 ValidationError", exc_info=exc)
                    await session.delete(data)
                    await session.commit()
                except ValueError as exc:
                    logger.error("解析数据出现异常 ValueError", exc_info=exc)
                    await session.delete(data)
                    await session.commit()
        return None

    async def get_character_details(
        self, client: "GenshinClient", character: "Union[int,BaseCharacter]"
    ) -> Optional["CalculatorCharacterDetails"]:
        """缓存 character_details 并定时对其进行数据存储 当遇到 Too Many Requests 可以获取以前的数据
        :param client: genshin.py
        :param character:
        :return:
        """
        uid = client.uid
        if uid is not None:
            if isinstance(character, BaseCharacter):
                character_id = character.id
            else:
                character_id = character
            detail = await self.get_character_details_for_redis(uid, character_id)
            if detail is not None:
                return detail
            try:
                detail = await client.get_character_details(character)
            except GenshinException as exc:
                if "Too Many Requests" in exc.msg:
                    return await self.get_character_details_for_mysql(uid, character_id)
                raise exc
            await self.set_character_details_for_redis(uid, character_id, detail)
            return detail
        try:
            return await client.get_character_details(character)
        except GenshinException as exc:
            if "Too Many Requests" in exc.msg:
                logger.warning("Too Many Requests")
            else:
                raise exc
        return None


class GenshinHelper(Plugin):
    def __init__(
        self,
        cookies: CookiesService,
        public_cookies: PublicCookiesService,
        user: UserService,
        redis: RedisDB,
        player: PlayersService,
    ) -> None:
        self.cookies_service = cookies
        self.public_cookies_service = public_cookies
        self.user_service = user
        self.redis_db = redis
        self.players_service = player

        if self.redis_db and config.genshin_ttl:
            self.genshin_cache = genshin.RedisCache(self.redis_db.client, ttl=config.genshin_ttl)
        else:
            self.genshin_cache = None

        if None in (temp := [self.user_service, self.cookies_service, self.players_service]):
            raise ServiceNotFoundError(*filter(lambda x: x is None, temp))

    @staticmethod
    def region_server(uid: Union[int, str]) -> RegionEnum:
        if isinstance(uid, (int, str)):
            region = REGION_MAP.get(str(uid)[0])
        else:
            raise TypeError("UID variable type error")
        if region:
            return region
        raise ValueError(f"UID {uid} isn't associated with any region.")

    async def get_genshin_client(
        self, user_id: int, region: Optional[RegionEnum] = None, need_cookie: bool = True
    ) -> Optional[genshin.Client]:
        """通过 user_id 和 region 获取私有的 `genshin.Client`"""
        player = await self.players_service.get_player(user_id, region)
        if player is None:
            raise PlayerNotFoundError(user_id)
        cookies = None
        if need_cookie:
            if player.account_id is None:
                raise CookiesNotFoundError(user_id)
            cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
            if cookie_model is None:
                raise CookiesNotFoundError(user_id)
            cookies = cookie_model.data

        uid = player.player_id
        region = player.region
        if region == RegionEnum.HYPERION:  # 国服
            game_region = genshin.types.Region.CHINESE
        elif region == RegionEnum.HOYOLAB:  # 国际服
            game_region = genshin.types.Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        client = genshin.Client(
            cookies,
            lang="zh-cn",
            game=genshin.types.Game.GENSHIN,
            region=game_region,
            uid=uid,
            hoyolab_id=player.account_id,
        )

        if self.genshin_cache is not None:
            client.cache = self.genshin_cache

        return client

    async def get_public_genshin_client(self, user_id: int) -> Tuple[genshin.Client, int]:
        """通过 user_id 获取公共的 `genshin.Client`"""
        player = await self.players_service.get_player(user_id)

        region = player.region
        cookies = await self.public_cookies_service.get_cookies(user_id, region)

        uid = player.player_id
        if region is RegionEnum.HYPERION:
            game_region = genshin.types.Region.CHINESE
        elif region is RegionEnum.HOYOLAB:
            game_region = genshin.types.Region.OVERSEAS
        else:
            raise TypeError("Region is not `RegionEnum.NULL`")

        client = genshin.Client(
            cookies.data, region=game_region, uid=uid, game=genshin.types.Game.GENSHIN, lang="zh-cn"
        )

        if self.genshin_cache is not None:
            client.cache = self.genshin_cache

        return client, uid
