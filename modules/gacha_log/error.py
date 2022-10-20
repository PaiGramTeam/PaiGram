class GachaLogException(Exception):
    pass


class GachaLogFileError(GachaLogException):
    pass


class GachaLogNotFound(GachaLogException):
    pass


class GachaLogAccountNotFound(GachaLogException):
    pass


class GachaLogInvalidAuthkey(GachaLogException):
    pass


class PaimonMoeGachaLogFileError(GachaLogFileError):
    pass
