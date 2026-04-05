from .config_service import (
    AppConfig,
    ConfigError,
    ConfigService,
    FreeMailConfig,
    GmailApiConfig,
    GmailConfig,
    HttpConfig,
    LuckMailConfig,
    MailConfig,
)


def __getattr__(name: str):
    if name in {"GmailService", "MessageRef"}:
        from .gmail_service import GmailService, MessageRef

        exports = {
            "GmailService": GmailService,
            "MessageRef": MessageRef,
        }
        return exports[name]

    if name in {"LuckMailService", "LuckMailApiError", "LuckMailHttpResult"}:
        from .luckmail_service import LuckMailApiError, LuckMailHttpResult, LuckMailService

        exports = {
            "LuckMailService": LuckMailService,
            "LuckMailApiError": LuckMailApiError,
            "LuckMailHttpResult": LuckMailHttpResult,
        }
        return exports[name]

    if name in {"FreeMailService", "FreeMailApiError", "FreeMailEmailSummary", "FreeMailEmailContent"}:
        from .freemail_service import (
            FreeMailApiError,
            FreeMailEmailContent,
            FreeMailEmailSummary,
            FreeMailService,
        )

        exports = {
            "FreeMailService": FreeMailService,
            "FreeMailApiError": FreeMailApiError,
            "FreeMailEmailSummary": FreeMailEmailSummary,
            "FreeMailEmailContent": FreeMailEmailContent,
        }
        return exports[name]

    if name in {"MailService", "MailServiceError", "GeneratedEmailAddress"}:
        from .mail_service import GeneratedEmailAddress, MailService, MailServiceError

        exports = {
            "MailService": MailService,
            "MailServiceError": MailServiceError,
            "GeneratedEmailAddress": GeneratedEmailAddress,
        }
        return exports[name]

    if name in {"HttpService", "HttpServiceError", "HttpResponse"}:
        from .http_service import HttpResponse, HttpService, HttpServiceError

        exports = {
            "HttpService": HttpService,
            "HttpServiceError": HttpServiceError,
            "HttpResponse": HttpResponse,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AppConfig",
    "ConfigError",
    "ConfigService",
    "FreeMailConfig",
    "GmailApiConfig",
    "GmailConfig",
    "HttpConfig",
    "LuckMailConfig",
    "MailConfig",
    "GmailService",
    "MessageRef",
    "HttpService",
    "HttpServiceError",
    "HttpResponse",
    "LuckMailService",
    "LuckMailApiError",
    "LuckMailHttpResult",
    "FreeMailService",
    "FreeMailApiError",
    "FreeMailEmailSummary",
    "FreeMailEmailContent",
    "MailService",
    "MailServiceError",
    "GeneratedEmailAddress",
]
