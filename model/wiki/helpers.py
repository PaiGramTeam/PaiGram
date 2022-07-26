import re

ID_RGX = re.compile(r"/db/[^.]+_(?P<id>\d+)")


def get_headers():
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;"
                  "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.63 Safari/537.36",
        "referer": "https://genshin.honeyhunterworld.com/db/char/hutao/?lang=CHS",
    }
    return headers


def get_id_form_url(url: str):
    matches = ID_RGX.search(url)
    if matches is None:
        return -1
    entries = matches.groupdict()
    if entries is None:
        return -1
    try:
        return int(entries.get('id'))
    except (IndexError, ValueError, TypeError):
        return -1
