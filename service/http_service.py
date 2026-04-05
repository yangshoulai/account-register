from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict
from urllib.parse import urlencode

from curl_cffi import requests

from .config_service import HttpConfig


@dataclass(frozen=True)
class HttpResponse:
    """HTTP 响应对象。"""

    status_code: int
    headers: dict[str, str]
    text: str

    def json(self) -> Dict[str, Any]:
        """按 JSON 解析响应正文。"""

        if not self.text.strip():
            return {}
        return json.loads(self.text)


class HttpServiceError(RuntimeError):
    """HTTP 调用异常。"""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class HttpService:
    """基于 curl-cffi 的通用 HTTP 服务。"""

    def __init__(self, config: HttpConfig | None = None, session: requests.Session | None = None):
        self._config = config or HttpConfig()
        self._session = session or requests.Session()

    @property
    def config(self) -> HttpConfig:
        """返回当前 HTTP 配置。"""

        return self._config

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        timeout_seconds: int | float | None = None,
        verify_ssl: bool | None = None,
        proxy: str | None = None,
        proxies: dict[str, str] | None = None,
        proxy_auth: tuple[str, str] | None = None,
        impersonate: str | None = None,
        ja3: str | None = None,
        akamai: str | None = None,
        extra_fp: dict[str, Any] | None = None,
        allow_redirects: bool = True,
        raise_for_status: bool = False,
    ) -> HttpResponse:
        """发送通用 HTTP 请求。"""

        final_url = self._build_url(url, params=params)
        final_headers = self._build_headers(headers)

        request_timeout = timeout_seconds or self._config.timeout_seconds
        request_verify_ssl = self._config.verify_ssl if verify_ssl is None else verify_ssl
        request_proxy = proxy if proxy is not None else self._config.proxy
        request_proxy_auth = proxy_auth or self._build_proxy_auth()

        request_proxies = proxies
        if request_proxies is None and request_proxy is None:
            request_proxies = self._build_protocol_proxies()

        request_impersonate = impersonate
        if request_impersonate is None:
            request_impersonate = self._config.impersonate

        request_ja3 = self._config.ja3 if ja3 is None else ja3
        request_akamai = self._config.akamai if akamai is None else akamai
        request_extra_fp = extra_fp if extra_fp is not None else self._config.extra_fp

        kwargs: dict[str, Any] = {
            "headers": final_headers,
            "timeout": request_timeout,
            "verify": request_verify_ssl,
            "allow_redirects": allow_redirects,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        if data is not None:
            kwargs["data"] = data
        if request_proxy:
            kwargs["proxy"] = request_proxy
        elif request_proxies:
            kwargs["proxies"] = request_proxies
        if request_proxy_auth:
            kwargs["proxy_auth"] = request_proxy_auth
        if request_impersonate:
            kwargs["impersonate"] = request_impersonate
        if request_ja3:
            kwargs["ja3"] = request_ja3
        if request_akamai:
            kwargs["akamai"] = request_akamai
        if request_extra_fp:
            kwargs["extra_fp"] = request_extra_fp

        try:
            response = self._session.request(method=method.upper(), url=final_url, **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise HttpServiceError(f"HTTP 请求失败: {exc}") from exc

        response_text = response.text if response.text is not None else ""
        if raise_for_status and response.status_code >= 400:
            raise HttpServiceError(
                message=f"HTTP 状态异常: {response.status_code}",
                status_code=response.status_code,
                response_text=response_text,
            )

        return HttpResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response_text,
        )

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """发送 GET 请求。"""

        return self.request(
            method="GET",
            url=url,
            params=params,
            headers=headers,
            **kwargs,
        )

    def post(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """发送 POST 请求。"""

        return self.request(
            method="POST",
            url=url,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            **kwargs,
        )

    def delete(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """发送 DELETE 请求。"""

        return self.request(
            method="DELETE",
            url=url,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            **kwargs,
        )

    def put(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """发送 PUT 请求。"""

        return self.request(
            method="PUT",
            url=url,
            params=params,
            json_body=json_body,
            data=data,
            headers=headers,
            **kwargs,
        )

    def _build_url(self, url: str, params: dict[str, Any] | None) -> str:
        """拼接 URL（支持 base_url + 相对路径）。"""

        raw = url.strip()
        if not raw:
            raise ValueError("url 不能为空")

        if raw.startswith("http://") or raw.startswith("https://"):
            final = raw
        else:
            base_url = self._config.base_url
            if not base_url:
                raise ValueError("当前 HttpConfig 未配置 base_url，无法使用相对路径")
            if not raw.startswith("/"):
                raw = f"/{raw}"
            final = f"{base_url}{raw}"

        if params:
            query = urlencode(params, doseq=True)
            if query:
                joiner = "&" if "?" in final else "?"
                final = f"{final}{joiner}{query}"

        return final

    def _build_headers(self, headers: dict[str, str] | None) -> dict[str, str]:
        """合并默认请求头。"""

        merged: dict[str, str] = {}
        merged.update(self._config.default_headers)

        if self._config.user_agent:
            merged.setdefault("User-Agent", self._config.user_agent)

        if headers:
            merged.update(headers)

        return merged

    def _build_protocol_proxies(self) -> dict[str, str] | None:
        """从配置构建按协议代理。"""

        proxies: dict[str, str] = {}
        if self._config.http_proxy:
            proxies["http"] = self._config.http_proxy
        if self._config.https_proxy:
            proxies["https"] = self._config.https_proxy
        return proxies or None

    def _build_proxy_auth(self) -> tuple[str, str] | None:
        """从配置构建代理认证信息。"""

        username = self._config.proxy_username
        password = self._config.proxy_password
        if username and password:
            return username, password
        return None
