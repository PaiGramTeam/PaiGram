class CookiesCachePoolExhausted(Exception):
    def __init__(self):
        super().__init__("Cookies cache pool is exhausted")