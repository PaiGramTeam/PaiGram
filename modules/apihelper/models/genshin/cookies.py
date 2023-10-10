from typing import Optional, TypeVar

from pydantic import BaseModel

IntStr = TypeVar("IntStr", int, str)

__all__ = ("CookiesModel",)


class CookiesModel(BaseModel):
    login_uid: Optional[IntStr] = None
    login_ticket: Optional[str] = None

    stoken: Optional[str] = None
    stuid: Optional[IntStr] = None
    mid: Optional[str] = None

    account_id: Optional[IntStr] = None
    cookie_token: Optional[str] = None

    ltoken: Optional[str] = None
    ltuid: Optional[IntStr] = None

    account_mid_v2: Optional[str] = None
    cookie_token_v2: Optional[str] = None
    account_id_v2: Optional[IntStr] = None

    ltoken_v2: Optional[str] = None
    ltmid_v2: Optional[str] = None
    ltuid_v2: Optional[IntStr] = None

    @property
    def is_v1(self) -> bool:
        if self.account_id or self.cookie_token or self.ltoken or self.ltuid:
            return True
        return False

    @property
    def is_v2(self) -> bool:
        if self.account_mid_v2 or self.cookie_token_v2 or self.ltoken_v2 or self.ltmid_v2:
            return True
        return False

    def remove_v2(self):
        self.account_mid_v2 = None
        self.cookie_token_v2 = None
        self.ltoken_v2 = None
        self.ltmid_v2 = None

    def to_dict(self):
        return self.dict(exclude_defaults=True)

    def to_json(self):
        return self.json(exclude_defaults=True)

    @property
    def user_id(self) -> Optional[int]:
        if self.ltuid:
            return self.ltuid
        if self.account_id:
            return self.account_id
        if self.login_uid:
            return self.login_uid
        if self.stuid:
            return self.stuid
        if self.account_id_v2:
            return self.account_id_v2
        if self.ltuid_v2:
            return self.ltuid_v2
        return None

    def set_v2_uid(self, user_id: int):
        if self.ltuid_v2 is None and self.ltoken_v2:
            self.ltuid_v2 = user_id
        if self.account_id_v2 is None and self.account_mid_v2:
            self.account_id_v2 = user_id

    def set_uid(self, user_id: int):
        if self.account_id is None and self.cookie_token:
            self.account_id = user_id
        if self.ltuid is None and self.ltoken:
            self.ltuid = user_id

    def check(self) -> bool:
        """检查Cookies是否完整
        :return: 成功返回 True 失败返回 False
        """
        # 以下任何缺一都导致问题
        if (self.account_mid_v2 is None) ^ (self.cookie_token_v2 is None):
            return False
        if (self.ltoken_v2 is None) ^ (self.ltmid_v2 is None):
            return False
        if (self.ltoken is None) ^ (self.ltuid is None):
            return False
        if (self.account_id is None) ^ (self.account_id is None):
            return False
        return True
