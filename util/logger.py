from __future__ import annotations

import json
import logging
import sys
from typing import Any


_DEFAULT_FORMAT = "[%(asctime)s] [%(name)s] [%(levelshort)s] %(message)s"
_DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"
_LEVEL_NAMES = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO ",
    logging.WARNING: "WARN ",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "FATAL",
}


class _SingleLineFormatter(logging.Formatter):
    """将普通日志压成单行，避免 RichHandler 的自动换行效果。"""

    def format(self, record: logging.LogRecord) -> str:
        preserve_newlines = bool(getattr(record, "preserve_newlines", False))
        message = record.getMessage()
        record.message = message if preserve_newlines else self._normalize_text(message)
        record.levelshort = self._format_level(record.levelno)
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        rendered = self.formatMessage(record)

        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            if not preserve_newlines:
                exc_text = self._normalize_text(exc_text)
            if exc_text:
                rendered = f"{rendered} | {exc_text}"

        if record.stack_info:
            stack_text = self.formatStack(record.stack_info)
            if not preserve_newlines:
                stack_text = self._normalize_text(stack_text)
            if stack_text:
                rendered = f"{rendered} | {stack_text}"

        return rendered

    @staticmethod
    def _normalize_text(text: str) -> str:
        # return " ".join(part.strip() for part in text.replace("\r", "\n").split("\n") if part.strip())
        return text

    @staticmethod
    def _format_level(levelno: int) -> str:
        return _LEVEL_NAMES.get(levelno, logging.getLevelName(levelno)[:5].ljust(5))


class Logger:
    """统一日志输出工具。"""

    def __init__(
        self,
        name: str = "app",
        level: str | int = "INFO",
        *,
        stream = None,
    ) -> None:
        resolved_level = self._resolve_level(level)
        self._logger = logging.getLogger(name)
        self._logger.setLevel(resolved_level)
        self._logger.propagate = False

        if not self._logger.handlers:
            handler = logging.StreamHandler(stream or sys.stdout)
            handler.setLevel(resolved_level)
            handler.setFormatter(_SingleLineFormatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT))
            self._logger.addHandler(handler)
        else:
            for handler in self._logger.handlers:
                handler.setLevel(resolved_level)

    @property
    def raw(self) -> logging.Logger:
        """返回底层 logging.Logger。"""

        return self._logger

    def set_level(self, level: str | int) -> None:
        """动态设置日志级别。"""

        resolved_level = self._resolve_level(level)
        self._logger.setLevel(resolved_level)
        for handler in self._logger.handlers:
            handler.setLevel(resolved_level)

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(message, *args, **kwargs)

    def info_multiline(self, message: str, *args: Any, **kwargs: Any) -> None:
        """保留换行的 INFO 日志。"""

        extra = dict(kwargs.pop("extra", {}) or {})
        extra["preserve_newlines"] = True
        self._logger.info(message, *args, extra=extra, **kwargs)

    def info_pretty(self, data: Any, prefix: str | None = None) -> None:
        """以 JSON 美化形式输出多行 INFO 日志。"""

        rendered = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        if prefix:
            rendered = f"{prefix}\n{rendered}"
        self.info_multiline(rendered)

    def success(self, message: str, *args: Any, **kwargs: Any) -> None:
        """成功日志。"""

        self._logger.info(f"✔ {message}", *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """异常日志。"""

        self._logger.exception(message, *args, **kwargs)

    @staticmethod
    def _resolve_level(level: str | int) -> int:
        if isinstance(level, int):
            return level
        text = level.strip().upper()
        if text in {"CRITICAL", "FATAL"}:
            return logging.CRITICAL
        if text == "ERROR":
            return logging.ERROR
        if text in {"WARN", "WARNING"}:
            return logging.WARN
        if text == "DEBUG":
            return logging.DEBUG
        return logging.INFO


def get_logger(name: str = "app", level: str | int = "INFO") -> Logger:
    """快捷创建日志对象。"""

    return Logger(name=name, level=level)
