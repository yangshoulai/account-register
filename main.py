from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pyexpat.errors import messages

from service.config_service import ConfigError, ConfigService
from service.gmail_service import GmailService
from service.mail_service import MailService


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数。"""

    parser = argparse.ArgumentParser(description="调试 ConfigService 与 MailService")
    parser.add_argument(
        "--config",
        default="config.toml",
        help="配置文件路径，默认 config.toml",
    )
    parser.add_argument(
        "--target-email",
        default=None,
        help="目标邮箱地址；不传时会先调用 generate_email_address 生成",
    )
    parser.add_argument(
        "--project-code",
        default=None,
        help="当 provider=luckmail 且需要生成邮箱时必填",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=8,
        help="当 provider=freemail 生成邮箱时，邮箱前缀长度，默认 8",
    )
    parser.add_argument(
        "--domain-index",
        type=int,
        default=None,
        help="当 provider=freemail 生成邮箱时，可选的域名索引",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="获取验证码时是否强制刷新邮件（luckmail 生效）",
    )
    parser.add_argument(
        "--max-probe-emails",
        type=int,
        default=None,
        help="获取验证码时最多探测邮件数量（freemail 生效）",
    )
    parser.add_argument(
        "--from-contains",
        default=None,
        help="验证码过滤条件：发送者包含该关键字（不区分大小写）",
    )
    parser.add_argument(
        "--subject-contains",
        default=None,
        help="验证码过滤条件：主题包含该关键字（不区分大小写）",
    )
    parser.add_argument(
        "--skip-fetch-code",
        action="store_true",
        help="仅测试 MailService 初始化/生成邮箱，不获取验证码",
    )
    return parser


def main() -> int:
    """调试入口：初始化 MailService，并测试生成邮箱/获取验证码。"""

    args = build_parser().parse_args()

    try:
        # 1) 加载配置
        app_config = ConfigService.load(Path(args.config))
        print("[ConfigService] 配置加载成功")

        # 2) 初始化通用邮箱服务
        gmail_service = GmailService.from_config_file(args.config)
        print("[GMailService] 初始化成功")

        messages = gmail_service.list_messages(query="from:openai.com subject:ChatGPT")
        message = gmail_service.get_message(messages[0].id)


        return 0
    except ConfigError as exc:
        print(f"[配置错误] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[运行错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
