from dataclasses import dataclass
from typing import Callable, Dict, Any

MailFilter = Callable[[str, str, str], bool]


@dataclass
class MailBox:
    email: str
    extras: Dict[str, Any] | None = None


class BaseMailService:

    def generate_mail_box(self) -> MailBox:
        """生成新的临时邮箱。"""
        raise NotImplementedError

    def get_latest_verification_code(self, mail_box: MailBox, mail_filter: MailFilter | None = None) -> str:
        """通过 Token 获取最新验证码。"""
        raise NotImplementedError
