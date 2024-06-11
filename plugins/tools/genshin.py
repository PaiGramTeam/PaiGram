import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from typing import Optional
from typing import TYPE_CHECKING, Union

from pydantic import ValidationError
from simnet import GenshinClient, Region
from simnet.errors import BadRequest as SimnetBadRequest, InvalidCookies, NetworkError, CookieException, NeedChallenge
from simnet.models.genshin.calculator import CalculatorCharacterDetails
from simnet.models.genshin.chronicle.characters import Character
from simnet.utils.player import recognize_game_biz
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import BigInteger, Column, DateTime, Field, Index, Integer, SQLModel, String, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from telegram.ext import ContextTypes

from core.basemodel import RegionEnum
from core.dependence.database import Database
from core.dependence.redisdb import RedisDB
from core.error import ServiceNotFoundError
from core.plugin import Plugin
from core.services.cookies.services import CookiesService, PublicCookiesService
from core.services.devices import DevicesService
from core.services.players.services import PlayersService
from core.services.users.services import UserService
from gram_core.services.cookies.models import CookiesStatusEnum
from utils.log import logger

if TYPE_CHECKING:
    from sqlalchemy import Table

__all__ = ("GenshinHelper", "PlayerNotFoundError", "CookiesNotFoundError", "CharacterDetails")


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
        self.expire = 60 * 60

    async def initialize(self) -> None:
        def fetch_and_update_objects(connection):
            if not self.database.engine.dialect.has_table(connection, table_name="character_details"):
                logger.info("正在创建角色详细信息表")
                table: "Table" = SQLModel.metadata.tables["character_details"]
                table.create(connection)
                logger.success("创建角色详细信息表成功")

        async with self.database.engine.begin() as conn:
            await conn.run_sync(fetch_and_update_objects)
        self.application.job_queue.run_daily(self.del_old_data_job, time(hour=12, minute=0))

    async def del_old_data_job(self, _: ContextTypes.DEFAULT_TYPE):
        await self.del_old_data(timedelta(days=7))

    async def del_old_data(self, expiration_time: timedelta):
        expire_time = datetime.now() - expiration_time
        statement = delete(CharacterDetailsSQLModel).where(CharacterDetailsSQLModel.time_updated <= expire_time)
        async with AsyncSession(self.database.engine) as session:
            await session.execute(statement)

    @staticmethod
    def get_qname(uid: int, character: int):
        return f"plugin:character_details:{uid}:{character}"

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

    async def set_character_details(self, player_id: int, character_id: int, data: str):
        randint = random.randint(1, 30)  # nosec
        await self.redis.set(
            self.get_qname(player_id, character_id), data, ex=self.expire + randint * 60
        )  # 使用随机数防止缓存雪崩
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
                player_id=player_id, character_id=character_id, data=data, time_updated=datetime.now()
            )
            async with AsyncSession(self.database.engine) as session:
                session.add(sql_data)
                await session.commit()
        else:
            sql_data.data = data
            sql_data.time_updated = datetime.now()
            async with AsyncSession(self.database.engine) as session:
                session.add(sql_data)
                await session.commit()

    async def set_character_details_task(self, player_id: int, character_id: int, data: str):
        try:
            await self.set_character_details(player_id, character_id, data)
        except SQLAlchemyError as exc:
            logger.error("写入到数据库失败 code[%s]", exc.code)
            logger.debug("写入到数据库失败", exc_info=exc)
        except Exception as exc:
            logger.error("set_character_details 执行失败", exc_info=exc)

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
        self, client: "GenshinClient", character: "Union[int,Character]"
    ) -> Optional["CalculatorCharacterDetails"]:
        """缓存 character_details 并定时对其进行数据存储 当遇到 Too Many Requests 可以获取以前的数据"""
        uid = client.player_id
        if isinstance(character, Character):
            character_id = character.id
        else:
            character_id = character
        if uid is not None:
            detail = await self.get_character_details_for_redis(uid, character_id)
            if detail is not None:
                return detail
            try:
                detail = await client.get_character_details(character_id)
            except SimnetBadRequest as exc:
                if "Too Many Requests" in exc.message:
                    return await self.get_character_details_for_mysql(uid, character_id)
                raise exc
            asyncio.create_task(self.set_character_details(uid, character_id, detail.json(by_alias=True)))
            return detail
        try:
            return await client.get_character_details(character_id)
        except SimnetBadRequest as exc:
            if "Too Many Requests" in exc.message:
                logger.warning("Too Many Requests")
            else:
                raise exc
        return None


class PlayerNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"User not found, user_id: {user_id}")


class CookiesNotFoundError(Exception):
    def __init__(self, user_id: int, region: Optional[RegionEnum] = None):
        self.user_id = user_id
        self.region = region
        super().__init__(f"{user_id} cookies not found")


class GenshinHelper(Plugin):
    def __init__(
        self,
        cookies: CookiesService,
        public_cookies: PublicCookiesService,
        user: UserService,
        player: PlayersService,
        devices: DevicesService,
    ) -> None:
        self.cookies_service = cookies
        self.public_cookies_service = public_cookies
        self.user_service = user
        self.players_service = player
        self.devices_service = devices
        if None in (temp := [self.user_service, self.cookies_service, self.players_service]):
            raise ServiceNotFoundError(*filter(lambda x: x is None, temp))

    @asynccontextmanager
    async def genshin(
        self, user_id: int, region: Optional[RegionEnum] = None, player_id: int = None, offset: int = 0
    ) -> GenshinClient:  # skipcq: PY-R1000 #
        player = await self.players_service.get_player(user_id, region, player_id, offset)
        if player is None:
            raise PlayerNotFoundError(user_id)

        if player.account_id is None:
            raise CookiesNotFoundError(user_id, player.region)
        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model is None:
            raise CookiesNotFoundError(user_id, player.region)
        cookies = cookie_model.data

        if player.region == RegionEnum.HYPERION:  # 国服
            region = Region.CHINESE
        elif player.region == RegionEnum.HOYOLAB:  # 国际服
            region = Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        device_id: Optional[str] = None
        device_fp: Optional[str] = None
        devices = await self.devices_service.get(player.account_id)
        if devices:
            device_id = devices.device_id
            device_fp = devices.device_fp

        async with GenshinClient(
            cookies,
            region=region,
            account_id=player.account_id,
            player_id=player.player_id,
            lang="zh-cn",
            device_id=device_id,
            device_fp=device_fp,
        ) as client:
            try:
                yield client
            except InvalidCookies as exc:
                if exc.retcode == 10103:
                    raise exc
                refresh = False
                cookie_model.status = CookiesStatusEnum.INVALID_COOKIES
                stoken = client.cookies.get("stoken")
                if stoken is not None:
                    try:
                        new_cookies = cookie_model.data.copy()
                        new_cookies["cookie_token"] = await client.get_cookie_token_by_stoken()
                        logger.success("用户 %s 刷新 cookie_token 成功", user_id)
                        new_cookies["ltoken"] = await client.get_ltoken_by_stoken()
                        logger.success("用户 %s 刷新 ltoken 成功", user_id)
                        cookie_model.data = new_cookies
                        cookie_model.status = CookiesStatusEnum.STATUS_SUCCESS
                    except ValueError as _exc:
                        logger.info("用户 user_id[%s] Cookies 不完整 [%s]", cookie_model.user_id, str(_exc))
                    except InvalidCookies:
                        logger.info("用户 user_id[%s] Cookies 已经过期", cookie_model.user_id)
                    except SimnetBadRequest as _exc:
                        logger.warning(
                            "用户 %s 刷新 token 失败 [%s]%s", user_id, _exc.ret_code, _exc.original or _exc.message
                        )
                        cookie_model.status = CookiesStatusEnum.STATUS_SUCCESS
                    except NetworkError:
                        logger.warning("用户 %s 刷新 Cookies 失败 网络错误", user_id)
                        cookie_model.status = CookiesStatusEnum.STATUS_SUCCESS
                    except Exception as _exc:
                        logger.error("用户 %s 刷新 Cookies 失败", user_id, exc_info=_exc)
                    else:
                        refresh = True
                try:
                    await self.cookies_service.update(cookie_model)
                except StaleDataError as _exc:
                    if "UPDATE" in str(_exc):
                        logger.warning("用户 user_id[%s] 刷新 Cookies 失败，数据不存在", cookie_model.user_id)
                    else:
                        logger.error("用户 user_id[%s] 更新 Cookies 时出现错误", cookie_model.user_id, exc_info=_exc)
                except Exception as _exc:
                    logger.error("用户 user_id[%s] 更新 Cookies 失败", cookie_model.user_id, exc_info=_exc)
                if refresh:
                    raise CookieException(message="The cookie has been refreshed.") from exc
                raise exc
            except NeedChallenge as exc:
                if devices is not None:
                    devices.is_valid = False
                    await self.devices_service.update(devices)
                raise exc

    async def get_genshin_client(
        self, user_id: int, region: Optional[RegionEnum] = None, player_id: int = None, offset: int = 0
    ) -> GenshinClient:
        player = await self.players_service.get_player(user_id, region, player_id, offset)
        if player is None:
            raise PlayerNotFoundError(user_id)

        if player.account_id is None:
            raise CookiesNotFoundError(user_id, player.region)
        cookie_model = await self.cookies_service.get(player.user_id, player.account_id, player.region)
        if cookie_model is None:
            raise CookiesNotFoundError(user_id, player.region)
        cookies = cookie_model.data

        if player.region == RegionEnum.HYPERION:
            region = Region.CHINESE
        elif player.region == RegionEnum.HOYOLAB:
            region = Region.OVERSEAS
        else:
            raise TypeError("Region is not None")

        device_id: Optional[str] = None
        device_fp: Optional[str] = None
        devices = await self.devices_service.get(player.account_id)
        if devices:
            device_id = devices.device_id
            device_fp = devices.device_fp

        return GenshinClient(
            cookies,
            region=region,
            account_id=player.account_id,
            player_id=player.player_id,
            lang="zh-cn",
            device_id=device_id,
            device_fp=device_fp,
        )

    @asynccontextmanager
    async def public_genshin(
        self, user_id: int, region: Optional[RegionEnum] = None, uid: Optional[int] = None
    ) -> GenshinClient:
        if not (region or uid):
            player = await self.players_service.get_player(user_id, region)
            if player:
                region = player.region
                uid = player.player_id

        cookies = await self.public_cookies_service.get_cookies(user_id, region)

        if region == RegionEnum.HYPERION:
            region = Region.CHINESE
        elif region == RegionEnum.HOYOLAB:
            region = Region.OVERSEAS
        else:
            raise TypeError("Region is not `RegionEnum.NULL`")

        device_id: Optional[str] = None
        device_fp: Optional[str] = None
        devices = await self.devices_service.get(cookies.account_id)
        if devices:
            device_id = devices.device_id
            device_fp = devices.device_fp

        async with GenshinClient(
            cookies.data,
            region=region,
            player_id=uid,
            lang="zh-cn",
            device_id=device_id,
            device_fp=device_fp,
        ) as client:
            try:
                yield client
            except NeedChallenge as exc:
                await self.public_cookies_service.undo(user_id)
                await self.public_cookies_service.set_device_valid(client.account_id, False)
                raise exc

    @asynccontextmanager
    async def genshin_or_public(
        self,
        user_id: int,
        region: Optional[RegionEnum] = None,
        uid: Optional[int] = None,
        offset: int = 0,
    ) -> GenshinClient:
        try:
            async with self.genshin(user_id, region, uid, offset) as client:
                client.public = False
                if uid and recognize_game_biz(uid, client.game) != recognize_game_biz(client.player_id, client.game):
                    # 如果 uid 和 player_id 服务器不一致，说明是跨服的，需要使用公共的 cookies
                    raise CookiesNotFoundError(user_id)
                yield client
        except (CookiesNotFoundError, PlayerNotFoundError):
            if uid:
                region = RegionEnum.HYPERION if uid < 600000000 else RegionEnum.HOYOLAB
            async with self.public_genshin(user_id, region, uid) as client:
                try:
                    client.public = True
                    yield client
                except NeedChallenge as exc:
                    raise CookiesNotFoundError(user_id) from exc
