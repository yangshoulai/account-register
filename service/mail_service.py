from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .config_service import ConfigService, MailConfig
from .freemail_service import FreeMailService
from .luckmail_service import LuckMailService

MailFilter = Callable[[str, str, str], bool]
_OTP_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


@dataclass(frozen=True)
class GeneratedEmailAddress:
    """通用邮箱服务生成的邮箱地址信息。"""

    provider: str
    email: str
    token: str | None
    raw: dict[str, Any]


class MailServiceError(RuntimeError):
    """通用邮箱服务异常。"""


class MailService:
    """通用邮箱服务（当前支持 luckmail / freemail）。"""

    def __init__(
            self,
            config: MailConfig,
            luckmail_service: LuckMailService | None = None,
            freemail_service: FreeMailService | None = None,
    ):
        provider = config.provider.strip().lower()
        if not provider:
            raise ValueError("provider 不能为空")

        if provider == "luckmail" and luckmail_service is None:
            raise ValueError("provider=luckmail 时必须传入 luckmail_service")
        if provider == "freemail" and freemail_service is None:
            raise ValueError("provider=freemail 时必须传入 freemail_service")

        self._config = config
        self._provider = provider
        self._luckmail_service = luckmail_service
        self._freemail_service = freemail_service

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "MailService":
        """从配置文件创建通用邮箱服务。"""

        app_config = ConfigService.load(config_file)
        provider = app_config.mail.provider.strip().lower()

        if provider == "luckmail":
            if app_config.luckmail is None:
                raise MailServiceError("provider=luckmail 时缺少 [services.luckmail] 配置")
            return cls(
                config=app_config.mail,
                luckmail_service=LuckMailService.from_config_file(config_file),
            )

        if provider == "freemail":
            if app_config.freemail is None:
                raise MailServiceError("provider=freemail 时缺少 [services.freemail] 配置")
            return cls(
                config=app_config.mail,
                freemail_service=FreeMailService.from_config_file(config_file),
            )

        raise MailServiceError(f"暂不支持的邮件服务 provider: {provider}")

    @property
    def config(self) -> MailConfig:
        """返回当前服务配置。"""

        return self._config

    @property
    def provider(self) -> str:
        """返回当前使用的 provider。"""

        return self._provider

    def generate_email_address(self) -> GeneratedEmailAddress:
        """
        生成新的邮箱地址。

        当前 provider=luckmail 时，会调用 LuckMail 的 purchase_email 接口并返回第一条邮箱记录。
        """

        if self._provider == "luckmail":
            result = self._require_luckmail().purchase_email()
            return GeneratedEmailAddress(
                provider=self._provider,
                email=result.get("email_address", ""),
                token=result.get("token", ""),
                raw=result,
            )

        if self._provider == "freemail":
            email = self._require_freemail().generate_mail_box()
            return GeneratedEmailAddress(
                provider=self._provider,
                email=email,
                token=None,
                raw={"email": email},
            )

        raise MailServiceError(f"暂不支持的邮件服务 provider: {self._provider}")

    def get_latest_verification_code(self, email_address: GeneratedEmailAddress, mail_filter: MailFilter) -> str:
        """
        获取目标邮箱的最新验证码。

        mail_filter 回调入参顺序严格为：
        1) from（邮件发送者）
        2) subject（邮件主题）
        3) receive_at（yyyy-mm-dd HH:mm:ss）
        """
        if not callable(mail_filter):
            raise ValueError("mail_filter 必须是可调用对象")

        if self._provider == "freemail":
            return self._require_freemail().get_latest_verification_code(email_address.email, mail_filter)
        elif self._provider == "luckmail":
            return self._require_luckmail().get_latest_verification_code(email_address.token, mail_filter)
        raise MailServiceError(f"暂不支持的邮件服务 provider: {self._provider}")

    def _require_luckmail(self) -> LuckMailService:
        if self._luckmail_service is None:
            raise MailServiceError("LuckMail 服务未初始化")
        return self._luckmail_service

    def _require_freemail(self) -> FreeMailService:
        if self._freemail_service is None:
            raise MailServiceError("FreeMail 服务未初始化")
        return self._freemail_service
