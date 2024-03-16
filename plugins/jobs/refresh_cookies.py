import datetime
from typing import TYPE_CHECKING, Dict

from simnet import Region
from simnet.client.components.auth import AuthClient
from simnet.errors import (
    TimedOut as SimnetTimedOut,
    BadRequest as SimnetBadRequest,
    NetworkError as SimnetNetworkError,
    InvalidCookies,
)
from sqlalchemy.orm.exc import StaleDataError

from core.plugin import Plugin, job
from gram_core.basemodel import RegionEnum
from gram_core.services.cookies import CookiesService
from gram_core.services.cookies.models import CookiesStatusEnum
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes

REGION = {
    RegionEnum.HYPERION: Region.CHINESE,
    RegionEnum.HOYOLAB: Region.OVERSEAS,
}


class RefreshCookiesJob(Plugin):
    def __init__(self, cookies: CookiesService):
        self.cookies = cookies

    @job.run_daily(time=datetime.time(hour=0, minute=1, second=0), name="RefreshCookiesJob")
    async def daily_refresh_cookies(self, _: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行每日刷新 Cookies 任务")
        for database_region, client_region in REGION.items():
            for cookie_model in await self.cookies.get_all(region=database_region):
                cookies = cookie_model.data
                if cookies.get("stoken") is not None and cookie_model.status != CookiesStatusEnum.INVALID_COOKIES:
                    try:
                        async with AuthClient(cookies=cookies, region=client_region) as client:
                            new_cookies: Dict[str, str] = cookies.copy()
                            new_cookies["cookie_token"] = await client.get_cookie_token_by_stoken()
                            new_cookies["ltoken"] = await client.get_ltoken_by_stoken()
                            cookie_model.data = new_cookies
                            cookie_model.status = CookiesStatusEnum.STATUS_SUCCESS
                    except ValueError:
                        cookie_model.status = CookiesStatusEnum.INVALID_COOKIES
                        logger.warning("用户 user_id[%s] Cookies 不完整", cookie_model.user_id)
                    except InvalidCookies:
                        cookie_model.status = CookiesStatusEnum.INVALID_COOKIES
                        logger.info("用户 user_id[%s] Cookies 已经过期", cookie_model.user_id)
                    except SimnetBadRequest as _exc:
                        logger.warning(
                            "用户 user_id[%s] 刷新 Cookies 时出现错误 [%s]%s",
                            cookie_model.user_id,
                            _exc.ret_code,
                            _exc.original or _exc.message,
                        )
                        continue
                    except SimnetTimedOut:
                        logger.warning("用户 user_id[%s] 刷新 Cookies 时连接超时", cookie_model.user_id)
                        continue
                    except SimnetNetworkError:
                        logger.warning("用户 user_id[%s] 刷新 Cookies 时网络错误", cookie_model.user_id)
                        continue
                    except Exception as _exc:
                        logger.error("用户 user_id[%s] 刷新 Cookies 失败", cookie_model.user_id, exc_info=_exc)
                        continue
                    try:
                        await self.cookies.update(cookie_model)
                    except StaleDataError as _exc:
                        if "UPDATE" in str(_exc):
                            logger.warning("用户 user_id[%s] 刷新 Cookies 失败，数据不存在", cookie_model.user_id)
                        else:
                            logger.error(
                                "用户 user_id[%s] 更新 Cookies 时出现错误", cookie_model.user_id, exc_info=_exc
                            )
                    except Exception as _exc:
                        logger.error("用户 user_id[%s] 更新 Cookies 状态失败", cookie_model.user_id, exc_info=_exc)
                    else:
                        logger.debug("用户 user_id[%s] 刷新 Cookies 成功")

        logger.success("执行每日刷新 Cookies 任务完成")
