from simnet.models.genshin.wish import GenshinBeyondBannerType

GACHA_TYPE_LIST = {
    GenshinBeyondBannerType.PERMANENT: "常驻颂愿",
    GenshinBeyondBannerType.EVENT: "活动颂愿",
}
GACHA_TYPE_LIST_REVERSE = {v: k for k, v in GACHA_TYPE_LIST.items()}
