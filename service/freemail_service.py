from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from .config_service import ConfigService, FreeMailConfig, HttpConfig
from .http_service import HttpService, HttpServiceError

MailFilter = Callable[[str, str, str], bool]
_OTP_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


@dataclass(frozen=True)
class FreeMailEmailSummary:
    """邮件摘要信息。"""

    id: int
    sender: str
    subject: str
    received_at: str
    is_read: int
    preview: str
    verification_code: str


@dataclass(frozen=True)
class FreeMailEmailContent:
    """邮件详情信息。"""

    id: int
    sender: str
    to_addrs: str
    subject: str
    content: str
    html_content: str
    received_at: str
    is_read: int


class FreeMailApiError(RuntimeError):
    """FreeMail 接口调用异常。"""

    def __init__(self, message: str, *, http_status: int | None = None, response: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.response = response


class FreeMailService:
    """FreeMail 服务封装。"""

    def __init__(self, config: FreeMailConfig, http_service: HttpService | None = None):
        self._config = config
        self._http_service = http_service or self._create_default_http_service(config)

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "FreeMailService":
        """从配置文件加载 FreeMailConfig 并创建服务实例。"""

        app_config = ConfigService.load(config_file)
        if app_config.freemail is None:
            raise FreeMailApiError("缺少 FreeMail 配置")

        http_cfg = HttpConfig(
            base_url=app_config.freemail.base_url,
            timeout_seconds=app_config.http.timeout_seconds,
            verify_ssl=app_config.http.verify_ssl,
            user_agent=app_config.http.user_agent,
            proxy=app_config.http.proxy,
            http_proxy=app_config.http.http_proxy,
            https_proxy=app_config.http.https_proxy,
            proxy_username=app_config.http.proxy_username,
            proxy_password=app_config.http.proxy_password,
            impersonate=app_config.http.impersonate,
            ja3=app_config.http.ja3,
            akamai=app_config.http.akamai,
            extra_fp=dict(app_config.http.extra_fp),
            default_headers=dict(app_config.http.default_headers),
        )
        return cls(config=app_config.freemail, http_service=HttpService(config=http_cfg))

    @property
    def config(self) -> FreeMailConfig:
        """返回当前服务配置。"""

        return self._config

    def generate_mail_box(self, *, length: int = 8) -> str:
        """随机生成新的临时邮箱。"""

        if length <= 0:
            raise ValueError("length 必须大于 0")
        payload = self._request_json(
            method="GET",
            path="/api/generate",
            query={"length": length, "domainIndex": self._config.domain_index},
        )
        if not isinstance(payload, dict):
            raise FreeMailApiError("生成邮箱失败：接口返回格式错误", response=payload)
        email = payload.get("email")
        return email.strip().lower()

    def fetch_latest_emails(self, email_address: str) -> list[FreeMailEmailSummary]:
        """获取最新邮件摘要列表。"""
        payload = self._request_json(
            method="GET",
            path="/api/emails",
            query={"mailbox": email_address, "limit": self._config.max_probe_emails},
        )

        if isinstance(payload, dict):
            data = payload.get("data", [])
        else:
            data = payload

        if not isinstance(data, list):
            raise FreeMailApiError("获取邮件列表失败：接口返回格式错误", response=payload)

        emails: list[FreeMailEmailSummary] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            mail_id = self._to_int(item.get("id"))
            if mail_id is None:
                continue

            emails.append(
                FreeMailEmailSummary(
                    id=mail_id,
                    sender=self._to_str(item.get("sender")),
                    subject=self._to_str(item.get("subject")),
                    received_at=self._to_str(item.get("received_at")),
                    is_read=self._to_int(item.get("is_read"), default=0) or 0,
                    preview=self._to_str(item.get("preview")),
                    verification_code=self._to_str(item.get("verification_code")),
                )
            )
        return emails

    def fetch_email_content(self, email_id: int) -> FreeMailEmailContent | None:
        """获取邮件详情。"""

        if email_id <= 0:
            raise ValueError("email_id 必须大于 0")

        payload = self._request_json(
            method="GET",
            path=f"/api/email/{email_id}",
        )
        if payload in (None, {}, []):
            return None
        if not isinstance(payload, dict):
            raise FreeMailApiError("获取邮件详情失败：接口返回格式错误", response=payload)

        return FreeMailEmailContent(
            id=email_id,
            sender=self._to_str(payload.get("sender")),
            to_addrs=self._to_str(payload.get("to_addrs")),
            subject=self._to_str(payload.get("subject")),
            content=self._to_str(payload.get("content")),
            html_content=self._to_str(payload.get("html_content")),
            received_at=self._to_str(payload.get("received_at")),
            is_read=self._to_int(payload.get("is_read"), default=0) or 0,
        )

    def get_latest_verification_code(self, email_address: str, mail_filter: MailFilter, ) -> str:
        """
        获取最新验证码。

        mail_filter 回调入参顺序严格为：
        1) from（邮件发送者）
        2) subject（邮件主题）
        3) receive_at（yyyy-mm-dd HH:mm:ss）
        """

        if not callable(mail_filter):
            raise ValueError("mail_filter 必须是可调用对象")

        mail_items = self.fetch_latest_emails(email_address)
        if not mail_items:
            raise FreeMailApiError(f"邮箱 {email_address} 暂无邮件")

        for item in mail_items:
            if item.verification_code and mail_filter(item.sender, item.subject, item.received_at):
                return item.verification_code
        return ""

    def _request_json(
            self,
            *,
            method: str,
            path: str,
            query: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        response = self._request(method=method, path=path, query=query, body=body)
        return response.json()

    def _request(
            self,
            *,
            method: str,
            path: str,
            query: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
    ):
        request_path = self._build_request_path(path)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-admin-token": self._config.admin_token,
        }

        try:
            response = self._http_service.request(
                method=method,
                url=request_path,
                params=query,
                json_body=body,
                headers=headers,
                raise_for_status=False,
            )
        except HttpServiceError as error:
            raise FreeMailApiError(
                message=str(error),
                http_status=error.status_code,
                response=error.response_text,
            ) from error

        parsed = response.json()
        if response.status_code >= 400:
            raise FreeMailApiError(
                message=f"FreeMail HTTP 错误: {response.status_code}",
                http_status=response.status_code,
                response=parsed,
            )
        return response

    @staticmethod
    def _build_request_path(path: str) -> str:
        clean_path = path.strip()
        if not clean_path:
            raise ValueError("path 不能为空")
        if not clean_path.startswith("/"):
            clean_path = f"/{clean_path}"
        return clean_path

    @staticmethod
    def _to_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _to_int(value: Any, default: int | None = None) -> int | None:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.strip():
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    @staticmethod
    def _create_default_http_service(config: FreeMailConfig) -> HttpService:
        http_config = HttpConfig(base_url=config.base_url)
        return HttpService(config=http_config)
