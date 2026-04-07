from __future__ import annotations

from pathlib import Path

from service.mail.duckmail_service import DuckMailService
from service.mail.freemail_service import FreeMailService
from service.mail.gmail_service import GmailService
from service.mail.luckmail_service import LuckMailService
from .base_mail_service import MailFilter, BaseMailService, MailBox
from .config_service import ConfigService, MailConfig
from .http_service import HttpService
from .mail.firefoxrelay_service import FirefoxRelayService


class MailServiceError(RuntimeError):
    """通用邮箱服务异常。"""


class MailService(BaseMailService):
    """通用邮箱服务，当前支持 luckmail / freemail / gmail。"""

    def __init__(self, config: MailConfig,
                 *,
                 luckmail_service: LuckMailService | None = None,
                 freemail_service: FreeMailService | None = None,
                 gmail_service: GmailService | None = None,
                 duckmail_service: DuckMailService | None = None,
                 firefoxrelay_service: FirefoxRelayService | None = None
                 ):
        provider = config.provider.strip().lower()
        if not provider:
            raise ValueError("provider 不能为空")
        if provider == "luckmail" and luckmail_service is None:
            raise ValueError("provider=luckmail 时必须传入 luckmail_service")
        if provider == "freemail" and freemail_service is None:
            raise ValueError("provider=freemail 时必须传入 freemail_service")
        if provider == "gmail" and gmail_service is None:
            raise ValueError("provider=gmail 时必须传入 gmail_service")
        if provider == "duckmail" and duckmail_service is None:
            raise ValueError("provider=duckmail 时必须传入 duckmail_service")
        if provider == "firefoxrelay" and not firefoxrelay_service:
            raise MailServiceError("provider=firefoxrelay 时缺少 firefoxrelay_service")

        if provider == "luckmail":
            self._mail_provider = luckmail_service
        elif provider == "freemail":
            self._mail_provider = freemail_service
        elif provider == "gmail":
            self._mail_provider = gmail_service
        elif provider == "duckmail":
            self._mail_provider = duckmail_service
        elif provider == "firefoxrelay":
            self._mail_provider = firefoxrelay_service
        else:
            raise MailServiceError(f"暂不支持的邮件服务 provider: {provider}")

        self._config = config
        self._provider = provider

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "MailService":
        """从配置文件创建通用邮箱服务。"""
        app_config = ConfigService.load(config_file)
        provider = app_config.mail.provider.strip().lower()
        http_service = HttpService(app_config.http)

        if provider == "luckmail":
            if app_config.luckmail is None:
                raise MailServiceError("provider=luckmail 时缺少 [services.luckmail] 配置")
            return cls(
                config=app_config.mail,
                luckmail_service=LuckMailService(app_config.luckmail, http_service),
            )

        if provider == "freemail":
            if app_config.freemail is None:
                raise MailServiceError("provider=freemail 时缺少 [services.freemail] 配置")
            return cls(
                config=app_config.mail,
                freemail_service=FreeMailService(app_config.freemail, http_service),
            )

        if provider == "gmail":
            return cls(
                config=app_config.mail,
                gmail_service=GmailService(app_config.gmail),
            )
        if provider == "duckmail":
            if app_config.duckmail is None:
                raise MailServiceError("provider=duckmail 时缺少 [services.duckmail] 配置")
            if app_config.gmail is None:
                raise MailServiceError("provider=duckmail 时缺少 [services.gmail] 配置")
            return cls(
                config=app_config.mail,
                duckmail_service=DuckMailService(app_config.duckmail, http_service, GmailService(app_config.gmail)),
            )
        if provider == "firefoxrelay":
            if app_config.firefoxrelay is None:
                raise MailServiceError("provider=firefoxrelay 时缺少 [services.firefoxrelay] 配置")
            if app_config.gmail is None:
                raise MailServiceError("provider=duckmail 时缺少 [services.gmail] 配置")
            return cls(
                config=app_config.mail,
                firefoxrelay_service=FirefoxRelayService(app_config.firefoxrelay, http_service, GmailService(app_config.gmail)),
            )

        raise MailServiceError(f"暂不支持的邮件服务 provider: {provider}")

    @property
    def provider(self) -> str:
        """返回当前使用的 provider。"""

        return self._provider

    def generate_mail_box(self) -> MailBox:
        """生成新的邮箱地址。"""
        return self._mail_provider.generate_mail_box()

    def get_latest_verification_code(self, email_box: MailBox, mail_filter: MailFilter | None = None) -> str:
        return self._mail_provider.get_latest_verification_code(email_box, mail_filter)
