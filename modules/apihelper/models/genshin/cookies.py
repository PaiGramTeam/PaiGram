from typing import Optional, TypeVar

from pydantic import BaseModel

IntStr = TypeVar("IntStr", int, str)

__all__ = ("CookiesModel",)


class CookiesModel(BaseModel):
    login_uid: Optional[IntStr] = None
    login_ticket: Optional[str] = None

    stoken: Optional[str] = None
    stuid: Optional[IntStr] = None

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
