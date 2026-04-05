from __future__ import annotations

import base64
import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from .config_service import ConfigService, GmailConfig

MessageFormat = Literal["minimal", "full", "raw", "metadata"]
MailFilter = Callable[[str, str, str], bool]
DEFAULT_USER_ID = "me"
_OTP_PATTERN = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


@dataclass(frozen=True)
class MessageRef:
    """邮件引用信息。"""

    id: str
    thread_id: str


class GmailService:
    """Gmail 业务服务，负责邮件查询与删除。"""

    def __init__(self, config: GmailConfig, client: Resource | None = None):
        self._config = config
        self._client = client or self._build_client(config)

    @classmethod
    def from_config_file(cls, config_file: str | Path = "config.toml") -> "GmailService":
        """从配置文件加载 GmailConfig 并创建服务实例。"""

        gmail_config = ConfigService.get_gmail_config(config_file)
        return cls(config=gmail_config)

    @property
    def config(self) -> GmailConfig:
        """返回服务当前使用的 Gmail 配置。"""

        return self._config

    def list_messages(
            self,
            query: str | None = None,
            max_results: int | None = None,
            include_spam_trash: bool = False,
    ) -> list[MessageRef]:
        """获取邮件列表（仅返回邮件 ID 与线程 ID）。"""

        resolved_query = query if query is not None else self._config.default_query
        resolved_max_results = (
            max_results
            if max_results is not None
            else self._config.default_max_results
        )

        if resolved_max_results <= 0:
            raise ValueError("max_results 必须大于 0")

        request_kwargs: dict[str, Any] = {
            "userId": DEFAULT_USER_ID,
            "maxResults": resolved_max_results,
            "includeSpamTrash": include_spam_trash,
        }
        if resolved_query:
            request_kwargs["q"] = resolved_query

        response = self._client.users().messages().list(**request_kwargs).execute()
        return [
            MessageRef(id=item["id"], thread_id=item["threadId"])
            for item in response.get("messages", [])
        ]

    def get_message(self, message_id: str, fmt: MessageFormat = "full") -> dict[str, Any]:
        """根据邮件 ID 获取邮件详情。"""

        return (
            self._client.users()
            .messages()
            .get(userId=DEFAULT_USER_ID, id=message_id, format=fmt)
            .execute()
        )

    def get_latest_verification_code(
            self,
            mail_filter: MailFilter,
            *,
            query: str | None = None,
            max_results: int | None = None,
            include_spam_trash: bool = False,
    ) -> str:
        """
        获取最近一次验证码。

        mail_filter 回调入参顺序固定为：
        1) from（发件人）
        2) subject（邮件主题）
        3) receive_at（yyyy-mm-dd HH:mm:ss）
        """

        if not callable(mail_filter):
            raise ValueError("mail_filter 必须是可调用对象")

        message_refs = self.list_messages(
            query=query,
            max_results=max_results,
            include_spam_trash=include_spam_trash,
        )
        if not message_refs:
            return ""

        candidates: list[tuple[int, str]] = []
        for item in message_refs:
            message = self.get_message(item.id, fmt="full")
            mail_from = self._extract_from(message)
            subject = self._extract_subject(message)
            receive_at = self._format_receive_at(message)
            if not mail_filter(mail_from, subject, receive_at):
                continue

            code = self._extract_verification_code(message)
            if not code:
                continue

            candidates.append((self._extract_internal_timestamp(message), code))

        if not candidates:
            return ""

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def generate_mail_box(self, *, length: int = 8, alias: str | None = None) -> str:
        """
        基于当前配置邮箱生成新的 Gmail 别名邮箱。

        默认使用 plus addressing，例如：
        user@gmail.com -> user+abc123xy@gmail.com
        """

        base_email = self._normalize_email(self._config.email)
        local_part, domain = base_email.split("@", 1)
        base_local = local_part.split("+", 1)[0]

        if alias is not None:
            clean_alias = self._normalize_alias(alias)
        else:
            if length <= 0:
                raise ValueError("length 必须大于 0")
            clean_alias = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(length))

        return f"{base_local}+{clean_alias}@{domain}"

    def delete_message(self, message_id: str, permanently: bool = False) -> dict[str, Any]:
        """删除邮件。默认移入垃圾箱，permanently=True 时永久删除。"""

        if permanently:
            response = (
                self._client.users()
                .messages()
                .delete(userId=DEFAULT_USER_ID, id=message_id)
                .execute()
            )
            return response or {}

        return (
            self._client.users()
            .messages()
            .trash(userId=DEFAULT_USER_ID, id=message_id)
            .execute()
        )

    def delete_messages(
            self,
            message_ids: Sequence[str],
            permanently: bool = False,
    ) -> dict[str, Any]:
        """批量删除邮件。"""

        if not message_ids:
            return {"deleted": 0, "details": []}

        if permanently:
            response = (
                self._client.users()
                .messages()
                .batchDelete(
                    userId=DEFAULT_USER_ID,
                    body={"ids": list(message_ids)},
                )
                .execute()
            )
            return {"deleted": len(message_ids), "details": response or {}}

        details: list[dict[str, Any]] = []
        for message_id in message_ids:
            details.append(self.delete_message(message_id=message_id, permanently=False))
        return {"deleted": len(message_ids), "details": details}

    @staticmethod
    def extract_text_from_message(message: dict) -> str:
        payload = message.get("payload", {})

        def _decode_base64url(data: str) -> str:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")

        def walk(part: dict) -> str | None:
            mime = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")

            # 优先 text/plain
            if mime.startswith("text/plain") and data:
                return _decode_base64url(data)

            for child in part.get("parts", []) or []:
                text = walk(child)
                if text:
                    return text

            # 兜底 text/html
            if mime.startswith("text/html") and data:
                return _decode_base64url(data)
            return None

        return walk(payload) or message.get("snippet", "")

    @staticmethod
    def _extract_headers(message: dict[str, Any]) -> dict[str, str]:
        payload = message.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        result: dict[str, str] = {}
        for item in headers:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            value = str(item.get("value") or "").strip()
            if name:
                result[name.lower()] = value
        return result

    def _extract_from(self, message: dict[str, Any]) -> str:
        return self._extract_headers(message).get("from", "")

    def _extract_subject(self, message: dict[str, Any]) -> str:
        return self._extract_headers(message).get("subject", "")

    def _format_receive_at(self, message: dict[str, Any]) -> str:
        timestamp = self._extract_internal_timestamp(message)
        if timestamp > 0:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

        raw_date = self._extract_headers(message).get("date", "")
        if raw_date:
            try:
                dt = parsedate_to_datetime(raw_date)
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError, IndexError):
                pass

        return "1970-01-01 00:00:00"

    @staticmethod
    def _extract_internal_timestamp(message: dict[str, Any]) -> int:
        raw = str(message.get("internalDate") or "").strip()
        if not raw.isdigit():
            return 0
        value = int(raw)
        return value // 1000 if value > 1_000_000_000_000 else value

    @classmethod
    def _extract_verification_code(cls, message: dict[str, Any]) -> str:
        texts = [
            cls._extract_headers(message).get("subject", ""),
            str(message.get("snippet") or ""),
            cls.extract_text_from_message(message),
        ]
        for text in texts:
            matched = _OTP_PATTERN.search(text or "")
            if matched:
                return matched.group(1)
        return ""

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("当前配置邮箱不是合法的 Gmail 地址")
        return normalized

    @staticmethod
    def _normalize_alias(alias: str) -> str:
        normalized = alias.strip().lower()
        if not normalized:
            raise ValueError("alias 不能为空")
        if not re.fullmatch(r"[a-z0-9._-]+", normalized):
            raise ValueError("alias 仅支持字母、数字、点、下划线和中划线")
        return normalized

    @staticmethod
    def _build_client(config: GmailConfig) -> Resource:
        """根据当前邮箱配置创建 Gmail API 客户端，并自动处理 token 刷新。"""

        creds: Credentials | None = None
        api_config = config.api

        credentials_file = config.resolve_credentials_file()
        token_file = config.resolve_token_file()

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(
                str(token_file),
                list(api_config.scopes),
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file),
                    list(api_config.scopes),
                )
                creds = flow.run_local_server(port=0)

            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds, cache_discovery=False)
