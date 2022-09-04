class CookiesCachePoolExhausted(Exception):
    def __init__(self):
        super().__init__("Cookies cache pool is exhausted")


class CookiesNotFoundError(Exception):
    def __init__(self, user_id):
        super().__init__(f"{user_id} cookies not found")
