# Service 模块说明

当前项目包含五个服务：

- `/Users/yangshoulai/Development/PycharmProjects/fuckcodex/service/gmail_service.py`
- `/Users/yangshoulai/Development/PycharmProjects/fuckcodex/service/http_service.py`
- `/Users/yangshoulai/Development/PycharmProjects/fuckcodex/service/luckmail_service.py`
- `/Users/yangshoulai/Development/PycharmProjects/fuckcodex/service/freemail_service.py`
- `/Users/yangshoulai/Development/PycharmProjects/fuckcodex/service/mail_service.py`（通用邮箱服务）

## 配置文件结构

`/Users/yangshoulai/Development/PycharmProjects/fuckcodex/config.toml`

```toml
[services.gmail]
email = "your.email@gmail.com"
proxy = "http://127.0.0.1:7890" # 可选，仅 Gmail API / OAuth 使用
default_query = "is:inbox"
default_max_results = 20

[services.gmail.api]
credentials_file = "secrets/client_secret.json"
token_dir = "secrets/tokens"
scopes = ["https://www.googleapis.com/auth/gmail.modify"]

[services.luckmail]
base_url = "https://mails.luckyous.com"
api_key = "请替换为你的apikey"
openapi_prefix = "/api/v1/openapi"
timeout_seconds = 30

[services.mail]
provider = "luckmail"

[services.freemail]
base_url = "https://mailfree.yangshoulai.xyz"
admin_token = "请替换为你的 admin_token"
domain_index = 0
max_probe_emails = 10

[services.http]
user_agent = "Mozilla/5.0 ..."
proxy = "http://127.0.0.1:7890" # 可选，全局代理
# http_proxy = "http://127.0.0.1:7890" # 可选，按协议代理
# https_proxy = "http://127.0.0.1:7890"
# proxy_username = "username" # 可选
# proxy_password = "password" # 可选
impersonate = "chrome136"
timeout_seconds = 30
verify_ssl = true

[services.http.default_headers]
Accept-Language = "zh-CN,zh;q=0.9,en;q=0.8"
```

> 如果给 Gmail 配置了 `proxy`，运行环境需要安装 `PySocks`。

## HttpService 说明

`HttpService` 基于 `curl-cffi`，提供：

- `request(...)`
- `get(...)`
- `post(...)`
- `delete(...)`
- `put(...)`

支持配置默认 UA、`impersonate` 指纹、`ja3`、`akamai`、`extra_fp`、默认请求头等。
也支持代理配置：`proxy`、`http_proxy`、`https_proxy`、`proxy_username`、`proxy_password`。

## LuckMailService 已封装接口

- `query_balance()`：查询余额
- `purchase_email(...)`：购买邮箱
- `list_purchased_emails(...)`：获取已购邮箱列表
- `get_latest_code_by_token(token)`：通过 Token 获取最新验证码
- `get_mails_by_token(token, refresh=False)`：通过 Token 获取邮件列表

## FreeMailService 已封装接口

- `generate_mail_box(length=8, domain_index=None)`：生成新邮箱地址
- `fetch_latest_emails(email_address, n=None)`：获取最新邮件摘要列表
- `fetch_email_content(email_id)`：获取邮件详情
- `get_latest_verification_code(email_address, mail_filter, max_probe_emails=None)`：按过滤条件获取验证码

## MailService（通用邮箱服务）

- `generate_email_address(...)`：按 provider 生成新的邮箱地址
- `get_latest_verification_code(target_email, mail_filter, refresh=True, max_probe_emails=None)`：获取目标邮箱最新验证码
  - `mail_filter(from, subject, receive_at)` 回调参数顺序固定
  - `receive_at` 格式：`yyyy-mm-dd HH:mm:ss`

## 使用示例

```python
from service.config_service import ConfigService
from service.mail_service import MailService

mail_service = MailService.from_config_file("config.toml")
generated = mail_service.generate_email_address(project_code="your_project_code")

code = mail_service.get_latest_verification_code(
    generated.email,
    mail_filter=lambda from_, subject, receive_at: (
        "noreply" in from_.lower()
        and "验证码" in subject
    ),
)
print(generated.email, code)
```

如果 `provider = "freemail"`，可以这样生成邮箱（不需要 project_code）：

```python
generated = mail_service.generate_email_address(length=8)
```
