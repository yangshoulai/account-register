from service.base_mail_service import BaseMailService
from service.config_service import AppConfig, HttpConfig
from service.http_service import HttpService
from service.mail.duckmail_service import DuckMailService
from service.mail.firefoxrelay_service import FirefoxRelayService
from service.mail.freemail_service import FreeMailService
from service.mail.gmail_service import GmailService
from service.mail.luckmail_service import LuckMailService


def create_mail_service(app_config: AppConfig, provider: str, http_service: HttpService | None = None) -> BaseMailService:
    """创建邮箱服务。"""
    http_service = http_service if http_service else _create_default_http_service(app_config.http)

    if provider == "luckmail":
        if app_config.luckmail is None:
            raise RuntimeError("provider=luckmail 时缺少 [services.luckmail] 配置")
        return LuckMailService(app_config.luckmail, http_service)

    if provider == "freemail":
        if app_config.freemail is None:
            raise RuntimeError("provider=freemail 时缺少 [services.freemail] 配置")
        return FreeMailService(app_config.freemail, http_service)

    if provider == "gmail":
        if app_config.gmail is None:
            raise RuntimeError("provider=gmail 时缺少 [services.gmail] 配置")
        return GmailService(app_config.gmail)

    if provider == "duckmail":
        if app_config.duckmail is None:
            raise RuntimeError("provider=duckmail 时缺少 [services.duckmail] 配置")
        if app_config.gmail is None:
            raise RuntimeError("provider=duckmail 时缺少 [services.gmail] 配置")
        return DuckMailService(app_config.duckmail, http_service, GmailService(app_config.gmail))

    if provider == "firefoxrelay":
        if app_config.firefoxrelay is None:
            raise RuntimeError("provider=firefoxrelay 时缺少 [services.firefoxrelay] 配置")
        if app_config.gmail is None:
            raise RuntimeError("provider=duckmail 时缺少 [services.gmail] 配置")
        return FirefoxRelayService(app_config.firefoxrelay, http_service, GmailService(app_config.gmail))

    raise RuntimeError(f"暂不支持的邮件服务 provider: {provider}")


def _create_default_http_service(http_config: HttpConfig | None = None) -> HttpService:
    http_config = http_config if http_config else HttpConfig()
    return HttpService(config=http_config)
