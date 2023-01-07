class PayLogException(Exception):
    pass


class PayLogFileError(PayLogException):
    pass


class PayLogNotFound(PayLogFileError):
    pass


class PayLogAccountNotFound(PayLogException):
    pass


class PayLogAuthkeyException(PayLogException):
    pass


class PayLogAuthkeyTimeout(PayLogAuthkeyException):
    pass


class PayLogInvalidAuthkey(PayLogAuthkeyException):
    pass
