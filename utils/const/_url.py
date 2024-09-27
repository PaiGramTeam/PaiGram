from httpx import URL

__all__ = ("HONEY_HOST", "ENKA_HOST", "AMBR_HOST", "AMBR_API_HOST", "CELESTIA_HOST")

HONEY_HOST = URL("https://gensh.honeyhunterworld.com/")
ENKA_HOST = URL("https://enka.network/")
AMBR_HOST = URL("https://gi.yatta.moe/")
AMBR_API_HOST = AMBR_HOST.join("api/")
CELESTIA_HOST = URL("https://www.projectcelestia.com/")
