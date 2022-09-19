class APIHelperError(Exception):
    pass


class NetworkError(APIHelperError):
    pass


class ResponseError(APIHelperError):
    pass


class DataNotFindError(APIHelperError):
    pass


class ReturnCodeError(APIHelperError):
    pass
