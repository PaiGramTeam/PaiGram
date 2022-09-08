class CookieServiceError(Exception):
    pass


class CookiesCachePoolExhausted(CookieServiceError):
    def __init__(self):
        super().__init__("Cookies cache pool is exhausted")


class CookiesNotFoundError(CookieServiceError):
    def __init__(self, user_id):
        super().__init__(f"{user_id} cookies not found")


class TooManyRequestPublicCookies(CookieServiceError):
    def __init__(self, user_id):
        super().__init__(f"{user_id} too many request public cookies")
