from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config_service import ConfigService, HttpConfig, LuckMailConfig
from .freemail_service import MailFilter
from .http_service import HttpService, HttpServiceError


@dataclass(frozen=True)
class LuckMailHttpResult:
    """LuckMail HTTP 调用结果。"""

    status_code: int
    payload: Any


class LuckMailApiError(RuntimeError):
    """LuckMail 接口调用异常。"""

    def __init__(
            self,
            message: str,
            *,
            http_status: int | None = None,
            business_code: int | None = None,
            response: Any = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.business_code = business_code
        self.response = response


class LuckMailService:
    """LuckMail 服务封装（用户 OpenAPI）。"""

    def __init__(self, config: LuckMailConfig, http_service: HttpService | None = None):
        self._config = config
        self._http_service = http_service or self._create_default_http_service(config)

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "LuckMailService":
        """从配置文件加载 LuckMailConfig 并创建服务实例。"""

        app_config = ConfigService.load(config_file)
        if app_config.luckmail is None:
            raise LuckMailApiError("缺少 LuckMail 配置")

        http_cfg = HttpConfig(
            base_url=app_config.luckmail.base_url,
            timeout_seconds=app_config.luckmail.timeout_seconds,
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
        return cls(config=app_config.luckmail, http_service=HttpService(config=http_cfg))

    @property
    def config(self) -> LuckMailConfig:
        """返回服务当前使用的 LuckMail 配置。"""

        return self._config

    def query_balance(self) -> float:
        """查询账户余额。"""
        return self._request_json(
            method="GET",
            path="/balance",
            use_api_key=True,
        ).get("balance", 0.0)

    def purchase_email(self) -> dict[str, Any]:
        """购买邮箱。"""

        body: dict[str, Any] = {
            "project_code": self._config.project_code.strip(),
            "quantity": 1,
        }
        if self._config.email_type:
            body["email_type"] = self._config.email_type
        if self._config.domain:
            body["domain"] = self._config.domain
        if self._config.variant_mode:
            body["variant_mode"] = self._config.variant_mode

        purchases = self._request_json(
            method="POST",
            path="/email/purchase",
            body=body,
            use_api_key=True,
        ).get("purchases", [])

        if len(purchases) == 0:
            raise LuckMailApiError("购买邮箱失败：无邮箱返回")
        return purchases[0]

    def list_purchased_emails(
            self,
            *,
            page: int = 1,
            page_size: int = 20,
            project_id: int | None = None,
            tag_id: int | None = None,
            keyword: str | None = None,
            user_disabled: int | None = None,
    ) -> list[dict[str, Any]]:
        """获取已购邮箱列表（分页）。"""

        if page <= 0:
            raise ValueError("page 必须大于 0")
        if page_size <= 0:
            raise ValueError("page_size 必须大于 0")

        query: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if project_id is not None:
            query["project_id"] = project_id
        if tag_id is not None:
            query["tag_id"] = tag_id
        if keyword:
            query["keyword"] = keyword
        if user_disabled is not None:
            query["user_disabled"] = user_disabled

        return self._request_json(
            method="GET",
            path="/email/purchases",
            query=query,
            use_api_key=True,
        ).get("list", [])

    def get_latest_verification_code(self, token: str, mail_filter: MailFilter, ) -> str:
        """通过 Token 获取最新验证码。"""

        if not callable(mail_filter):
            raise ValueError("mail_filter 必须是可调用对象")

        clean_token = token.strip()
        if not clean_token:
            raise ValueError("token 不能为空")

        data = self._request_json(
            method="GET",
            path=f"/email/token/{clean_token}/code",
            use_api_key=False,
        )
        mail = data.get("mail", {})
        verification_code = data.get("verification_code", "")

        if verification_code and mail_filter(mail.get("from"), mail.get("subject"), mail.get("received_at")):
            return verification_code
        return ""

    def get_mails_by_token(self, token: str, refresh: bool = False) -> list[dict[str, Any]]:
        """通过 Token 获取邮件列表。"""

        clean_token = token.strip()
        if not clean_token:
            raise ValueError("token 不能为空")

        query = {"refresh": 1} if refresh else None
        return self._request_json(
            method="GET",
            path=f"/email/token/{clean_token}/mails",
            query=query,
            use_api_key=False,
        ).get("mails", [])

    def _request_json(
            self,
            *,
            method: str,
            path: str,
            query: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
            use_api_key: bool,
    ) -> dict[str, Any]:
        """发送请求并返回 JSON 结构。"""

        result = self._request(
            method=method,
            path=path,
            query=query,
            body=body,
            use_api_key=use_api_key,
        )

        if not isinstance(result.payload, dict):
            raise LuckMailApiError(
                "接口返回非 JSON 对象",
                http_status=result.status_code,
                response=result.payload,
            )

        business_code = result.payload.get("code")
        if business_code is not None and business_code != 0:
            raise LuckMailApiError(
                message=result.payload.get("message") or "LuckMail 业务错误",
                http_status=result.status_code,
                business_code=business_code,
                response=result.payload,
            )

        return result.payload.get("data", {})

    def _request(
            self,
            *,
            method: str,
            path: str,
            query: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
            use_api_key: bool,
    ) -> LuckMailHttpResult:
        """底层 HTTP 请求。"""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if use_api_key:
            headers["X-API-Key"] = self._config.api_key

        try:
            response = self._http_service.request(
                method=method,
                url=path,
                params=query,
                json_body=body,
                headers=headers,
                raise_for_status=False,
            )
        except HttpServiceError as error:
            raise LuckMailApiError(
                message=str(error),
                http_status=error.status_code,
                response=error.response_text,
            ) from error

        parsed = response.json()
        if response.status_code >= 400:
            raise LuckMailApiError(
                message=f"LuckMail HTTP 错误: {response.status_code}",
                http_status=response.status_code,
                response=parsed,
            )

        return LuckMailHttpResult(status_code=response.status_code, payload=parsed)

    @staticmethod
    def _create_default_http_service(config: LuckMailConfig) -> HttpService:
        """创建 LuckMail 默认 HTTP 客户端。"""

        http_config = HttpConfig(base_url=config.base_url, timeout_seconds=config.timeout_seconds, )
        return HttpService(config=http_config)
