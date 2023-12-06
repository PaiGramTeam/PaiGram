class GachaException(Exception):
    pass


class GachaInvalidTimes(GachaException):
    pass


class GachaIllegalArgument(GachaException):
    pass


class BannerNotFound(GachaException):
    pass
