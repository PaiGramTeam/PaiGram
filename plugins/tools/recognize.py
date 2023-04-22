from json import JSONDecodeError
from typing import Optional

from httpx import AsyncClient, TimeoutException

from core.config import config
from utils.log import logger


class RecognizeSystem:
    REFERER = (
        "https://webstatic.mihoyo.com/bbs/event/signin-ys/index.html?"
        "bbs_auth_required=true&act_id=e202009291139501&utm_source=bbs&utm_medium=mys&utm_campaign=icon"
    )

    @staticmethod
    async def recognize(gt: str, challenge: str, referer: str = None, uid: int = None) -> Optional[str]:
        if not referer:
            referer = RecognizeSystem.REFERER
        if not gt or not challenge or not uid:
            return None
        pass_challenge_params = {
            "gt": gt,
            "challenge": challenge,
            "referer": referer,
        }
        if config.pass_challenge_app_key:
            pass_challenge_params["appkey"] = config.pass_challenge_app_key
        headers = {
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/107.0.0.0 Safari/537.36",
        }
        try:
            async with AsyncClient(headers=headers) as client:
                resp = await client.post(
                    config.pass_challenge_api,
                    params=pass_challenge_params,
                    timeout=60,
                )
            logger.debug("recognize 请求返回：%s", resp.text)
            data = resp.json()
            status = data.get("status")
            if status != 0:
                logger.error("recognize 解析错误：[%s]%s", data.get("code"), data.get("msg"))
            if data.get("code", 0) != 0:
                raise RuntimeError
            logger.info("recognize 解析成功")
            return data["data"]["validate"]
        except JSONDecodeError:
            logger.warning("recognize 请求 JSON 解析失败")
        except TimeoutException as exc:
            logger.warning("recognize 请求超时")
            raise exc
        except KeyError:
            logger.warning("recognize 请求数据错误")
        except RuntimeError:
            logger.warning("recognize 请求失败")
        return None
