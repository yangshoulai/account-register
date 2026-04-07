from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.modify",)
DEFAULT_HTTP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
DEFAULT_HTTP_IMPERSONATE = "chrome136"

DEFAULT_OPENAI_REGISTER_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


class ConfigError(ValueError):
    """配置文件读取或校验失败。"""


def _normalize_email(email: str, field_name: str) -> str:
    """标准化邮箱字符串。"""

    normalized = email.strip().lower()
    if not normalized or "@" not in normalized:
        raise ConfigError(f"字段 `{field_name}` 必须是合法的邮箱地址")
    return normalized


def _normalize_base_url(value: str, field_name: str) -> str:
    """标准化 Base URL，去除结尾斜杠。"""

    text = value.strip()
    if not text:
        raise ConfigError(f"字段 `{field_name}` 必须是非空字符串")
    if not (text.startswith("http://") or text.startswith("https://")):
        raise ConfigError(f"字段 `{field_name}` 必须以 http:// 或 https:// 开头")
    return text.rstrip("/")


def _normalize_path_prefix(value: str, field_name: str) -> str:
    """标准化 API 前缀，保证以 / 开头。"""

    text = value.strip()
    if not text:
        raise ConfigError(f"字段 `{field_name}` 必须是非空字符串")
    if not text.startswith("/"):
        text = f"/{text}"
    return text.rstrip("/")


@dataclass(frozen=True)
class GmailApiConfig:
    """Gmail API 配置（单 client_secret，多 token）。"""

    credentials_file: Path
    token_dir: Path
    scopes: tuple[str, ...] = DEFAULT_GMAIL_SCOPES

    def resolve_token_file(self, email: str) -> Path:
        """按规则生成 token 文件路径：<邮箱>.json。"""

        normalized_email = _normalize_email(email, "services.gmail.email")
        return self.token_dir / f"{normalized_email}.json"


@dataclass(frozen=True)
class GmailConfig:
    """Gmail 服务业务配置。"""
    api: GmailApiConfig
    email: str
    email_length: int = 8
    default_max_results: int = 20
    proxy: str | None = None

    def resolve_token_file(self) -> Path:
        """获取当前邮箱对应的 token 文件路径。"""

        return self.api.resolve_token_file(self.email)

    def resolve_credentials_file(self) -> Path:
        """获取 OAuth 凭证文件路径（全局唯一）。"""

        return self.api.credentials_file


@dataclass(frozen=True)
class LuckMailConfig:
    """LuckMail API 配置。"""

    base_url: str
    api_key: str
    project_code: str
    email_type: str | None = None
    variant_mode: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class FreeMailConfig:
    """FreeMail API 配置。"""

    base_url: str
    admin_token: str
    email_length: int = 8
    domain_index: int = 0
    max_probe_emails: int = 10


@dataclass(frozen=True)
class DuckMailConfig:
    """DuckMail API 配置。"""
    base_url: str
    authorization_token: str
    forward_gmail: str


@dataclass(frozen=True)
class FirefoxRelayConfig:
    session_id: str
    csrf_token: str
    forward_gmail: str
    base_url: str = "https://relay.firefox.com"


@dataclass(frozen=True)
class HttpConfig:
    """通用 HTTP 客户端配置。"""

    timeout_seconds: int = 60
    verify_ssl: bool = True
    user_agent: str = DEFAULT_HTTP_USER_AGENT
    proxy: str | None = None
    http_proxy: str | None = None
    https_proxy: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None
    impersonate: str | None = DEFAULT_HTTP_IMPERSONATE
    ja3: str | None = None
    akamai: str | None = None
    extra_fp: dict[str, Any] = field(default_factory=dict)
    default_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenAIRegisterConfig:
    """OpenAI 注册服务配置。"""
    mail_provider: str
    oauth_client_id: str = DEFAULT_OPENAI_REGISTER_CLIENT_ID
    default_timeout_seconds: int = 60
    callback_server_port: int = 1455
    chrome_binary_path: str | None = None
    headless: bool = False
    default_account_password: str | None = None

    auth_file_dir: Path = field(default_factory=lambda: (Path.cwd() / "accounts").resolve())


@dataclass(frozen=True)
class CpaConfig:
    """CPA 服务配置。"""
    base_url: str
    management_password: str


@dataclass(frozen=True)
class AppConfig:
    """应用结构化配置对象。"""

    gmail: GmailConfig | None = None
    luckmail: LuckMailConfig | None = None
    freemail: FreeMailConfig | None = None
    duckmail: DuckMailConfig | None = None
    firefoxrelay: FirefoxRelayConfig | None = None

    http: HttpConfig = field(default_factory=HttpConfig)
    openai_register: OpenAIRegisterConfig = field(default_factory=OpenAIRegisterConfig)
    cpa: CpaConfig | None = None


class ConfigService:
    """负责从 config.toml 加载应用配置。"""

    @classmethod
    def load(cls, config_file: str | Path = "config.toml") -> AppConfig:
        """加载并返回应用配置对象。"""

        path = Path(config_file).expanduser()
        if not path.is_absolute():
            path = path.resolve()

        if not path.exists():
            raise ConfigError(f"配置文件不存在: {path}")

        with path.open("rb") as file:
            data = tomllib.load(file)

        return cls._parse(data=data, base_dir=path.parent)

    @classmethod
    def _parse(cls, data: dict[str, Any], base_dir: Path) -> AppConfig:
        services_table = cls._require_table(data, "services")

        gmail_config = None
        luckmail_config = None
        freemail_config = None
        duckmail_config = None
        firefoxrelay_config = None

        http_config = cls._parse_http_config(services_table)
        cpa_config = cls._parse_cpa_config(services_table)

        registers_table = cls._require_table(data, "registers")
        openai_register_config = cls._parse_openai_register_config(registers_table, base_dir=base_dir)

        if openai_register_config.mail_provider == "freemail":
            freemail_config = cls._parse_freemail_config(services_table)
        elif openai_register_config.mail_provider == "luckmail":
            luckmail_config = cls._parse_luckmail_config(services_table)
        elif openai_register_config.mail_provider == "duckmail":
            duckmail_config = cls._parse_duckmail_config(services_table)
            gmail_config = cls._parse_gmail_config(services_table, base_dir=base_dir)
        elif openai_register_config.mail_provider == "gmail":
            gmail_config = cls._parse_gmail_config(services_table, base_dir=base_dir)
        elif openai_register_config.mail_provider == "firefoxrelay":
            firefoxrelay_config = cls._parse_firefoxrelay_config(services_table)
            gmail_config = cls._parse_gmail_config(services_table, base_dir=base_dir)

        return AppConfig(
            gmail=gmail_config,
            luckmail=luckmail_config,
            freemail=freemail_config,
            duckmail=duckmail_config,
            firefoxrelay=firefoxrelay_config,
            http=http_config,
            openai_register=openai_register_config,
            cpa=cpa_config,
        )

    @classmethod
    def _parse_gmail_config_from_gmail_table(cls, services_table: dict[str, Any], base_dir: Path, config_prefix: str = "services"):
        gmail_table = cls._require_table(services_table, "gmail", full_name=f"{config_prefix}.gmail")
        gmail_api_table = cls._require_table(gmail_table, "api", full_name=f"{config_prefix}.gmail.api")
        raw_email = gmail_table.get("email")
        gmail_email = cls._parse_email(raw_email, field_name=f"{config_prefix}.gmail.email")
        email_length = cls._parse_positive_int(gmail_table.get("email_length"), f"{config_prefix}.gmail.email_length", default=8)
        gmail_api_config = GmailApiConfig(
            credentials_file=cls._parse_required_path(
                gmail_api_table.get("credentials_file"),
                field_name=f"{config_prefix}.gmail.api.credentials_file",
                base_dir=base_dir,
            ),
            token_dir=cls._parse_token_dir(gmail_api_table, base_dir),
            scopes=cls._parse_scopes(gmail_api_table.get("scopes")),
        )

        return GmailConfig(
            email=gmail_email,
            api=gmail_api_config,
            email_length=email_length,
            default_max_results=cls._parse_positive_int(
                gmail_table.get("default_max_results"),
                field_name=f"{config_prefix}.gmail.default_max_results",
                default=20,
            ),
            proxy=cls._parse_optional_nullable_str(
                gmail_table.get("proxy"),
                field_name=f"{config_prefix}.gmail.proxy",
                default=None,
            ),
        )

    @classmethod
    def _parse_gmail_config(cls, services_table: dict[str, Any], base_dir: Path) -> GmailConfig:
        return cls._parse_gmail_config_from_gmail_table(services_table, base_dir, "services")

    @classmethod
    def _parse_luckmail_config(cls, services_table: dict[str, Any]) -> LuckMailConfig | None:
        luckmail_table = services_table.get("luckmail")
        if luckmail_table is None:
            return None
        if not isinstance(luckmail_table, dict):
            raise ConfigError("[services.luckmail] 必须是表结构")

        base_url = _normalize_base_url(
            cls._parse_optional_str(
                luckmail_table.get("base_url"),
                field_name="services.luckmail.base_url",
                default="https://mails.luckyous.com",
            ),
            "services.luckmail.base_url",
        )

        api_key = cls._parse_required_str(
            luckmail_table.get("api_key"),
            field_name="services.luckmail.api_key",
        )

        project_code = cls._parse_required_str(
            luckmail_table.get("project_code"),
            field_name="services.luckmail.project_code"
        )

        email_type = cls._parse_required_str(
            luckmail_table.get("email_type"),
            field_name="services.luckmail.email_type"
        )

        variant_mode = cls._parse_nullable_str(
            luckmail_table.get("variant_mode"),
            field_name="services.luckmail.variant_mode"
        )

        domain = cls._parse_nullable_str(
            luckmail_table.get("domain"),
            field_name="services.luckmail.domain"
        )

        return LuckMailConfig(
            base_url=base_url,
            api_key=api_key,
            project_code=project_code,
            email_type=email_type,
            variant_mode=variant_mode,
            domain=domain,
        )

    @classmethod
    def _parse_freemail_config(cls, services_table: dict[str, Any]) -> FreeMailConfig | None:
        """解析 FreeMail 服务配置。"""

        freemail_table = services_table.get("freemail")
        if freemail_table is None:
            return None
        if not isinstance(freemail_table, dict):
            raise ConfigError("[services.freemail] 必须是表结构")

        base_url = _normalize_base_url(
            cls._parse_required_str(
                freemail_table.get("base_url"),
                field_name="services.freemail.base_url",
            ),
            "services.freemail.base_url",
        )
        admin_token = cls._parse_required_str(
            freemail_table.get("admin_token"),
            field_name="services.freemail.admin_token",
        )
        domain_index = cls._parse_non_negative_int(
            freemail_table.get("domain_index"),
            field_name="services.freemail.domain_index",
            default=0,
        )
        max_probe_emails = cls._parse_positive_int(
            freemail_table.get("max_probe_emails"),
            field_name="services.freemail.max_probe_emails",
            default=10,
        )
        email_length = cls._parse_positive_int(
            freemail_table.get("email_length"),
            field_name="services.freemail.email_length",
            default=8,
        )
        if max_probe_emails > 50:
            raise ConfigError("字段 `services.freemail.max_probe_emails` 不能大于 50")

        return FreeMailConfig(
            base_url=base_url,
            admin_token=admin_token,
            domain_index=domain_index,
            max_probe_emails=max_probe_emails,
            email_length=email_length,
        )

    @classmethod
    def _parse_duckmail_config(cls, services_table) -> DuckMailConfig | None:
        duckmail_table = cls._require_table(services_table, "duckmail", "services.duckmail")
        base_url = _normalize_base_url(
            cls._parse_required_str(
                duckmail_table.get("base_url"),
                field_name="services.duckmail.base_url",
            ),
            "services.duckmail.base_url",
        )

        authorization_token = cls._parse_required_str(
            duckmail_table.get("authorization_token"),
            field_name="services.duckmail.authorization_token",
        )
        forward_gmail = cls._parse_required_str(
            duckmail_table.get("forward_gmail"),
            field_name="services.duckmail.forward_gmail",
        )
        return DuckMailConfig(base_url=base_url, authorization_token=authorization_token, forward_gmail=forward_gmail)

    @classmethod
    def _parse_firefoxrelay_config(cls, services_table: dict[str, Any]) -> FirefoxRelayConfig | None:
        firefoxrelay_table = cls._require_table(services_table, "firefoxrelay", "services.firefoxrelay")

        base_url = _normalize_base_url(
            cls._parse_required_str(
                firefoxrelay_table.get("base_url"),
                field_name="services.firefoxrelay.base_url",
            ),
            "services.firefoxrelay.base_url",
        )

        session_id = cls._parse_required_str(
            firefoxrelay_table.get("session_id"),
            field_name="services.firefoxrelay.session_id",
        )

        csrf_token = cls._parse_required_str(
            firefoxrelay_table.get("csrf_token"),
            field_name="services.firefoxrelay.csrf_token",
        )

        forward_gmail = cls._parse_required_str(
            firefoxrelay_table.get("forward_gmail"),
            field_name="services.firefoxrelay.forward_gmail",
        )
        return FirefoxRelayConfig(base_url=base_url, session_id=session_id, csrf_token=csrf_token, forward_gmail=forward_gmail)

    @classmethod
    def _parse_http_config(cls, services_table: dict[str, Any]) -> HttpConfig:
        """解析通用 HTTP 配置。"""

        http_table = services_table.get("http")
        if http_table is None:
            return HttpConfig()
        if not isinstance(http_table, dict):
            raise ConfigError("[services.http] 必须是表结构")

        timeout_seconds = cls._parse_positive_int(
            http_table.get("timeout_seconds"),
            field_name="services.http.timeout_seconds",
            default=60,
        )
        verify_ssl = cls._parse_optional_bool(
            http_table.get("verify_ssl"),
            field_name="services.http.verify_ssl",
            default=True,
        )
        user_agent = cls._parse_optional_str(
            http_table.get("user_agent"),
            field_name="services.http.user_agent",
            default=DEFAULT_HTTP_USER_AGENT,
        )
        proxy = cls._parse_optional_nullable_str(
            http_table.get("proxy"),
            field_name="services.http.proxy",
            default=None,
        )
        http_proxy = cls._parse_optional_nullable_str(
            http_table.get("http_proxy"),
            field_name="services.http.http_proxy",
            default=None,
        )
        https_proxy = cls._parse_optional_nullable_str(
            http_table.get("https_proxy"),
            field_name="services.http.https_proxy",
            default=None,
        )
        proxy_username = cls._parse_optional_nullable_str(
            http_table.get("proxy_username"),
            field_name="services.http.proxy_username",
            default=None,
        )
        proxy_password = cls._parse_optional_nullable_str(
            http_table.get("proxy_password"),
            field_name="services.http.proxy_password",
            default=None,
        )
        impersonate = cls._parse_optional_nullable_str(
            http_table.get("impersonate"),
            field_name="services.http.impersonate",
            default=DEFAULT_HTTP_IMPERSONATE,
        )
        ja3 = cls._parse_optional_nullable_str(
            http_table.get("ja3"),
            field_name="services.http.ja3",
            default=None,
        )
        akamai = cls._parse_optional_nullable_str(
            http_table.get("akamai"),
            field_name="services.http.akamai",
            default=None,
        )
        default_headers = cls._parse_optional_str_dict(
            http_table.get("default_headers"),
            field_name="services.http.default_headers",
        )
        extra_fp = cls._parse_optional_any_dict(
            http_table.get("extra_fp"),
            field_name="services.http.extra_fp",
        )

        return HttpConfig(
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
            user_agent=user_agent,
            proxy=proxy,
            http_proxy=http_proxy,
            https_proxy=https_proxy,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            impersonate=impersonate,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            default_headers=default_headers,
        )

    @classmethod
    def _parse_openai_register_config(cls, registers_table: dict[str, Any], base_dir: Path) -> OpenAIRegisterConfig:
        """解析 OpenAI 注册机配置。"""
        openai_register_table = registers_table.get("openai")
        if openai_register_table is None:
            raise ConfigError("[registers.openai] 配置项缺失")
        if not isinstance(openai_register_table, dict):
            raise ConfigError("[registers.openai] 必须是表结构")

        mail_provider: str = cls._parse_required_str(
            openai_register_table.get("mail_provider"),
            field_name="registers.openai.mail_provider",
        )

        oauth_client_id: str = cls._parse_optional_str(
            openai_register_table.get("oauth_client_id"),
            field_name="registers.openai.oauth_client_id",
            default=DEFAULT_OPENAI_REGISTER_CLIENT_ID,
        )

        default_timeout_seconds: int = cls._parse_positive_int(
            openai_register_table.get("default_timeout_seconds"),
            field_name="registers.openai.default_timeout_seconds",
            default=60,
        )
        callback_server_port: int = cls._parse_positive_int(
            openai_register_table.get("callback_server_port"),
            field_name="registers.openai.callback_server_port",
            default=1455,
        )

        chrome_binary_path: str | None = cls._parse_optional_nullable_str(
            openai_register_table.get("chrome_binary_path"),
            field_name="registers.openai.chrome_binary_path",
            default=None,
        )

        headless: bool = cls._parse_optional_bool(
            openai_register_table.get("headless"),
            field_name="registers.openai.headless",
            default=False,
        )

        default_account_password = cls._parse_optional_nullable_str(
            openai_register_table.get("default_account_password"),
            field_name="registers.openai.default_account_password",
            default=None,
        )

        auth_file_dir = cls._parse_optional_path(
            openai_register_table.get("auth_file_dir"),
            field_name="registers.openai.auth_file_dir",
            base_dir=base_dir,
            default=(base_dir / "accounts").resolve(),
        )

        return OpenAIRegisterConfig(
            mail_provider=mail_provider,
            oauth_client_id=oauth_client_id,
            default_timeout_seconds=default_timeout_seconds,
            callback_server_port=callback_server_port,
            chrome_binary_path=chrome_binary_path,
            headless=headless,
            default_account_password=default_account_password,
            auth_file_dir=auth_file_dir,
        )

    @classmethod
    def _parse_cpa_config(cls, services_table: dict[str, Any]) -> CpaConfig | None:
        """解析 CPA 配置。"""

        cpa_table = services_table.get("cpa")
        if cpa_table is None:
            return None
        if not isinstance(cpa_table, dict):
            raise ConfigError("[services.cpa] 必须是表结构")

        base_url = _normalize_base_url(
            cls._parse_required_str(cpa_table.get("base_url", ""), "services.cpa.base_url"),
            "services.cpa.base_url",
        )

        management_password = cls._parse_required_str(
            cpa_table.get("management_password", ""),
            field_name="services.cpa.management_password"
        )

        return CpaConfig(
            base_url=base_url,
            management_password=management_password,
        )

    @classmethod
    def _parse_token_dir(cls, api_table: dict[str, Any], base_dir: Path, api_field_name_prefix: str = "services.gmail.api") -> Path:
        """解析 token 目录，兼容旧字段 token_file。"""

        token_dir_raw = api_table.get("token_dir")
        if token_dir_raw is not None:
            return cls._parse_required_path(
                token_dir_raw,
                field_name=f"{api_field_name_prefix}.token_dir",
                base_dir=base_dir,
            )

        token_file_raw = api_table.get("token_file")
        if token_file_raw is not None:
            token_file = cls._parse_required_path(
                token_file_raw,
                field_name=f"{api_field_name_prefix}.token_file",
                base_dir=base_dir,
            )
            return token_file.parent

        raise ConfigError(f"字段 `{api_field_name_prefix}.token_dir` 必填")

    @staticmethod
    def _require_table(data: dict[str, Any], key: str, full_name: str | None = None) -> dict[str, Any]:
        value = data.get(key)
        if not isinstance(value, dict):
            table_name = full_name or key
            raise ConfigError(f"缺少配置表: [{table_name}]")
        return value

    @staticmethod
    def _parse_email(value: Any, field_name: str) -> str:
        if not isinstance(value, str):
            raise ConfigError(f"字段 `{field_name}` 必须是字符串")
        return _normalize_email(value, field_name)

    @staticmethod
    def _parse_required_path(value: Any, field_name: str, base_dir: Path) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"字段 `{field_name}` 必须是非空字符串")
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return path

    @staticmethod
    def _parse_optional_path(value: Any, field_name: str, base_dir: Path, default: Path) -> Path:
        if value is None:
            return default.resolve()
        if not isinstance(value, str):
            raise ConfigError(f"字段 `{field_name}` 必须是字符串")
        cleaned = value.strip()
        if not cleaned:
            return default.resolve()
        path = Path(cleaned).expanduser()
        if not path.is_absolute():
            path = (base_dir / path).resolve()
        return path

    @staticmethod
    def _parse_required_str(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"字段 `{field_name}` 必须是非空字符串")
        return value.strip()

    @staticmethod
    def _parse_optional_str(value: Any, field_name: str, default: str) -> str:
        if value is None:
            return default
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"字段 `{field_name}` 必须是非空字符串")
        return value.strip()

    @staticmethod
    def _parse_nullable_str(value: Any, field_name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ConfigError(f"字段 `{field_name}` 必须是字符串")
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _parse_optional_nullable_str(
            value: Any,
            field_name: str,
            default: str | None,
    ) -> str | None:
        if value is None:
            return default
        if not isinstance(value, str):
            raise ConfigError(f"字段 `{field_name}` 必须是字符串")
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _parse_positive_int(value: Any, field_name: str, default: int) -> int:
        if value is None:
            return default
        if not isinstance(value, int) or value <= 0:
            raise ConfigError(f"字段 `{field_name}` 必须是大于 0 的整数")
        return value

    @staticmethod
    def _parse_non_negative_int(value: Any, field_name: str, default: int) -> int:
        if value is None:
            return default
        if not isinstance(value, int) or value < 0:
            raise ConfigError(f"字段 `{field_name}` 必须是大于等于 0 的整数")
        return value

    @staticmethod
    def _parse_optional_bool(value: Any, field_name: str, default: bool) -> bool:
        if value is None:
            return default
        if not isinstance(value, bool):
            raise ConfigError(f"字段 `{field_name}` 必须是布尔值")
        return value

    @staticmethod
    def _parse_optional_str_dict(value: Any, field_name: str) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ConfigError(f"字段 `{field_name}` 必须是表结构")

        output: dict[str, str] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigError(f"`{field_name}` 的 key 必须是字符串")
            if not isinstance(item, str):
                raise ConfigError(f"`{field_name}.{key}` 必须是字符串")
            output[key] = item
        return output

    @staticmethod
    def _parse_optional_any_dict(value: Any, field_name: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ConfigError(f"字段 `{field_name}` 必须是表结构")

        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigError(f"`{field_name}` 的 key 必须是字符串")
            output[key] = item
        return output

    @staticmethod
    def _parse_scopes(value: Any, api_field_name_prefix: str = "services.gmail.api") -> tuple[str, ...]:
        if value is None:
            return DEFAULT_GMAIL_SCOPES

        if isinstance(value, str):
            value = [value]

        if not isinstance(value, list) or not value:
            raise ConfigError(f"字段 `{api_field_name_prefix}.scopes` 必须是字符串数组或字符串")

        scopes: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ConfigError(f"`{api_field_name_prefix}.scopes` 中每个元素都必须是非空字符串")
            scopes.append(item)

        return tuple(scopes)
