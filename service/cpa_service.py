from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from service.config_service import ConfigError, CpaConfig, ConfigService
from service.http_service import HttpService


class CpaService:
    def __init__(self, config: CpaConfig, http_service: HttpService):
        self._config = config
        self._http_service = http_service
        self.management_headers = {
            "Authorization": f"Bearer {self._config.management_password}",
            "X-Management-Key": self._config.management_password,
        }

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "CpaService":
        """从配置文件创建 CPA 服务。"""
        app_config = ConfigService.load(config_file)
        if app_config.cpa is None:
            raise ConfigError("缺少配置表: [services.cpa]")
        http_service = HttpService(app_config.http)
        return cls(app_config.cpa, http_service)

    def _request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, str] | None = None,
            headers: dict[str, str] | None = None,
            data: bytes | None = None,
    ) -> Dict[str, Any]:
        url = f"{self._config.base_url}{path}"
        merged_headers = dict(self.management_headers)
        if headers:
            merged_headers.update(headers)
        if "POST" == method.upper():
            return self._http_service.post(url, params=params, headers=merged_headers, data=data, raise_for_status=True).json()
        if "GET" == method.upper():
            return self._http_service.get(url, params=params, headers=merged_headers, raise_for_status=True).json()
        if "DELETE" == method.upper():
            return self._http_service.delete(url, params=params, headers=merged_headers, raise_for_status=True).json()
        if "PUT" == method.upper():
            return self._http_service.put(url, params=params, headers=merged_headers, data=data, raise_for_status=True).json()
        else:
            return self._http_service.post(url, headers=merged_headers, raise_for_status=True).json()

    def upload_auth_file(self, file_name: str, raw_json: str) -> bool:
        """上传授权文件。"""
        resp = self._request(
            "POST",
            "/auth-files",
            params={"name": file_name},
            headers={"Content-Type": "application/json"},
            data=raw_json.encode("utf-8"),
        )
        return resp.get("status", "") == "ok"
