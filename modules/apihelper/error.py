from typing import Any, Mapping, Optional


class APIHelperException(Exception):
    pass


class NetworkException(APIHelperException):
    pass


class APIHelperTimedOut(APIHelperException):
    pass


class ResponseException(APIHelperException):
    code: int = 0
    message: str = ""

    def __init__(self, response: Optional[Mapping[str, Any]] = None, message: Optional[str] = None) -> None:
        if response is None:
            self.message = message
            _message = message
        else:
            self.code = response.get("retcode", self.code)
            self.message = response.get("message", "")
            _message = f"[{self.code}] {self.message}"

        super().__init__(_message)


class DataNotFoundError(ResponseException):
    def __init__(self):
        message = "response data not find"
        super().__init__(message=message)


class ReturnCodeError(ResponseException):
    def __init__(self):
        message = "response return code error"
        super().__init__(message=message)
