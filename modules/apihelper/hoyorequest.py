from typing import Any, Dict, Union

from modules.apihelper.error import NetworkError, ResponseError, DataNotFindError
from modules.apihelper.httpxrequest import HTTPXRequest


class HOYORequest(HTTPXRequest):

    async def get(self, url: str, *args, de_json: bool = True, **kwargs) -> Union[Dict[str, Any], bytes]:
        try:
            response = await self._client.get(url=url, *args, **kwargs)
        except Exception as exc:
            raise NetworkError(f"Unknown error in HTTP implementation: {repr(exc)}") from exc
        if response.is_error:
            raise ResponseError(f"response error in status code: {response.status_code}")
        if not de_json:
            return response.content
        json_data = response.json()
        return_code = json_data.get("retcode", None)
        data = json_data.get("data", None)
        message = json_data.get("message", None)
        if return_code is None:
            if data is None:
                raise DataNotFindError
            return json_data
        if return_code != 0:
            if message is None:
                raise ResponseError(f"response error in return code: {return_code}")
            else:
                raise ResponseError(f"response error: {message}[{return_code}]")
        return json_data
