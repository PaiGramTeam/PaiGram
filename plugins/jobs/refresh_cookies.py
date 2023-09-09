import datetime
from typing import TYPE_CHECKING, Dict

from simnet import Region
from simnet.client.components.auth import AuthClient
from simnet.errors import TimedOut as SimnetTimedOut, BadRequest as SimnetBadRequest, NetworkError as SimnetNetworkError

from core.plugin import Plugin, job
from gram_core.basemodel import RegionEnum
from gram_core.services.cookies import CookiesService
from utils.log import logger

if TYPE_CHECKING:
    from telegram.ext import ContextTypes


class RefreshCookiesJob(Plugin):
    def __init__(self, cookies: CookiesService):
        self.cookies = cookies

    @job.run_daily(time=datetime.time(hour=0, minute=1, second=0), name="RefreshCookiesJob")
    async def daily_refresh_cookies(self, _: "ContextTypes.DEFAULT_TYPE"):
        logger.info("正在执行每日刷新 Cookies 任务")
        for db_region, client_region in {
            RegionEnum.HYPERION: Region.CHINESE,
            RegionEnum.HOYOLAB: Region.OVERSEAS,
        }.items():
            for cookie_model in await self.cookies.get_all_by_region(db_region):
                cookies = cookie_model.data
                if cookies.get("stoken"):
                    try:
                        async with AuthClient(cookies=cookies, region=client_region) as client:
                            new_cookies: Dict[str, str] = cookies.copy()
                            new_cookies["cookie_token"] = await client.get_cookie_token_by_stoken()
                            new_cookies["ltoken"] = await client.get_ltoken_by_stoken()
                            cookie_model.data = new_cookies
                            await self.cookies.update(cookie_model)
                    except ValueError:
                        continue
                    except SimnetBadRequest:
                        logger.warning("用户 user_id[%s] 刷新 Cookies 时出现错误", cookie_model.user_id)
                    except SimnetTimedOut:
                        logger.warning("用户 user_id[%s] 刷新 Cookies 时超时", cookie_model.user_id)
                    except SimnetNetworkError:
                        logger.warning("用户 user_id[%s] 刷新 Cookies 时网络错误", cookie_model.user_id)
                    except Exception as _exc:
                        logger.error("用户 user_id[%s] 刷新 Cookies 失败", cookie_model.user_id, exc_info=_exc)
        logger.success("执行每日刷新 Cookies 任务完成")
