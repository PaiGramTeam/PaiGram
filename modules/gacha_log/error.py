class GachaLogException(Exception):
    pass


class GachaLogFileError(GachaLogException):
    pass


class GachaLogNotFound(GachaLogException):
    pass


class GachaLogAccountNotFound(GachaLogException):
    pass


class GachaLogAuthkeyException(GachaLogException):
    pass


class GachaLogAuthkeyTimeout(GachaLogAuthkeyException):
    pass


class GachaLogInvalidAuthkey(GachaLogAuthkeyException):
    pass


class GachaLogMixedProvider(GachaLogException):
    pass


class PaimonMoeGachaLogFileError(GachaLogFileError):
    def __init__(self, file_version: int, support_version: int):
        super().__init__("Paimon.Moe version not supported")
        self.support_version = support_version
        self.file_version = file_version


class GachaLogWebError(GachaLogException):
    pass


class GachaLogWebNotConfigError(GachaLogWebError):
    pass


class GachaLogWebUploadError(GachaLogWebError):
    pass
