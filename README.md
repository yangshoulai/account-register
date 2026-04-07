# fuckcodex

一个面向 **OpenAI / ChatGPT 账号注册与授权文件生成** 的自动化项目。

项目通过浏览器自动化、邮箱验证码获取、OAuth 授权回调与 CPA 上传四条链路协同工作，完成从“创建账号”到“生成并上传 auth file”的整套流程。

---

## 1. 项目目标

本项目主要解决以下问题：

1. **自动化注册 OpenAI / ChatGPT 账号**
2. **通过多种邮箱服务自动接收验证码**
3. **完成 OAuth 流程并生成本地授权文件**
4. **将生成的授权文件上传到 CPA 管理端**
5. **用统一配置驱动不同邮箱服务与 HTTP 行为**

换句话说，这个项目的核心不是“单纯收邮件”，而是：

> 用可插拔邮箱服务作为验证码入口，驱动 OpenAI 注册流程，最终产出可落地使用的 auth file。

---

## 2. 核心能力概览

当前项目主要包含以下能力模块：

### 2.1 配置加载
- `service/config_service.py`
- 负责读取本地 TOML 配置文件
- 将 TOML 配置解析为结构化配置对象
- 对关键字段做合法性校验

### 2.2 通用 HTTP 请求
- `service/http_service.py`
- 基于 `curl-cffi`
- 支持：
  - 默认请求头
  - User-Agent
  - `impersonate`
  - `ja3`
  - `akamai`
  - `extra_fp`
  - 代理 / 分协议代理 / 代理鉴权

> 说明：当前 `HttpService` 是通用 HTTP 客户端，**只接受绝对 URL**，不负责拼接业务服务的 `base_url`。

### 2.3 邮箱服务
位于 `service/mail/` 目录，当前支持 5 种邮箱 provider：

- Gmail
- LuckMail
- FreeMail
- DuckMail
- Firefox Relay

### 2.4 CPA 服务
- `service/cpa_service.py`
- 负责将生成的 auth file 上传到 CPA 管理端

### 2.5 OpenAI 注册机
- `core/openai_register.py`
- 负责完整注册流程：
  1. 打开 ChatGPT 页面
  2. 创建随机账号信息
  3. 生成或购买邮箱
  4. 获取验证码
  5. 完成 OAuth 授权
  6. 保存本地 auth file
  7. 上传到 CPA

---

## 3. 支持的邮箱服务

这是本项目最核心的能力之一。

### 3.1 支持列表

| provider | 生成邮箱方式 | 验证码获取方式 | 是否依赖 Gmail | 典型场景 |
|---|---|---|---|---|
| `gmail` | 基于已有 Gmail 主邮箱生成 `plus alias` | 直接调用 Gmail API 查邮件 | 否 | 已有 Gmail 主邮箱，最稳定 |
| `luckmail` | 调用 LuckMail API 购买邮箱 | 基于购买结果中的 token 获取验证码 | 否 | 需要独立临时邮箱 |
| `freemail` | 调用 FreeMail API 生成邮箱 | 轮询 FreeMail 邮件列表取验证码 | 否 | 自建临时邮箱服务 |
| `duckmail` | 调用 DuckMail 生成 `@duck.com` 地址 | 实际从转发到的 Gmail 中读取验证码 | 是 | 需要 Duck 地址，同时用 Gmail 收件 |
| `firefoxrelay` | 调用 Firefox Relay 生成中继邮箱 | 实际从转发到的 Gmail 中读取验证码 | 是 | 需要 Relay 地址，同时用 Gmail 收件 |

### 3.2 各邮箱服务说明

#### Gmail
特点：
- 不创建真实新邮箱账号
- 基于你已有的 Gmail 主邮箱生成别名，例如：
  - `yourname@gmail.com`
  - `yourname+ab12cd34@gmail.com`
- 验证码通过 Gmail API 查询

适合场景：
- 你已经有稳定可用的 Gmail
- 你希望验证码链路尽量稳定

#### LuckMail
特点：
- 通过 LuckMail OpenAPI 购买新邮箱
- `generate_mail_box()` 返回的 `MailBox.extras` 中通常带有 token
- `get_latest_verification_code()` 依赖该 token 查询验证码

适合场景：
- 需要真正新生成的邮箱地址
- 不希望验证码依赖 Gmail 主邮箱

#### FreeMail
特点：
- 通过 FreeMail API 生成临时邮箱
- 通过轮询邮件列表提取验证码
- 可配置 `domain_index`、`email_length`、`max_probe_emails`

适合场景：
- 已部署或可访问 FreeMail 服务
- 希望邮箱获取和验证码读取都在一个服务内完成

#### DuckMail
特点：
- 生成 DuckDuckGo Private Email 地址
- 验证码**不是直接从 DuckMail API 里读取**
- 而是通过 `forward_gmail` 转发到 Gmail，再用 Gmail API 读取

注意：
- 使用 `duckmail` 时，**必须同时配置 `[services.gmail]` 和 `[services.gmail.api]`**

#### Firefox Relay
特点：
- 生成 Firefox Relay 马甲邮箱
- 验证码通过转发到 Gmail 后读取

注意：
- 使用 `firefoxrelay` 时，**必须同时配置 `[services.gmail]` 和 `[services.gmail.api]`**

### 3.3 统一接口能力

所有邮箱服务都实现统一抽象 `BaseMailService`：

```python
class BaseMailService:
    def generate_mail_box(self) -> MailBox:
        ...

    def get_latest_verification_code(self, mail_box: MailBox, mail_filter: MailFilter | None = None) -> str:
        ...
```

这意味着上层注册逻辑不需要关心具体是 Gmail、LuckMail 还是 FreeMail。

---

## 4. 项目结构

```text
fuckcodex/
├── core/
│   └── openai_register.py        # OpenAI 注册主流程
├── service/
│   ├── config_service.py         # 配置解析
│   ├── http_service.py           # 通用 HTTP 客户端
│   ├── cpa_service.py            # CPA 上传服务
│   ├── base_mail_service.py      # 邮箱服务抽象
│   └── mail/
│       ├── mail_factory.py       # 邮箱服务工厂
│       ├── gmail_service.py
│       ├── luckmail_service.py
│       ├── freemail_service.py
│       ├── duckmail_service.py
│       └── firefoxrelay_service.py
├── util/
│   ├── account_util.py           # 随机账号信息生成
│   ├── logger.py                 # 日志封装
│   └── openai_register_util.py   # OAuth 辅助函数
├── secrets/                      # Gmail client_secret / token 等敏感文件
├── accounts/                     # 生成的 auth file 输出目录
├── config.example.toml           # 示例配置模板
├── pyproject.toml
└── README.md
```

---

## 5. 环境要求

### 5.1 Python
- Python **>= 3.13**

### 5.2 浏览器
- 运行注册流程时需要本机可用的 **Chrome / Chromium**
- 如果没有放在系统默认位置，可以通过 `registers.openai.chrome_binary_path` 指定路径

### 5.3 Gmail 相关
如果你使用以下任一 provider：
- `gmail`
- `duckmail`
- `firefoxrelay`

则需要：
- Google Cloud OAuth 客户端凭证文件（`client_secret.json`）
- 首次运行时完成 Gmail API 授权
- 本地可写的 token 目录

### 5.4 网络与代理
如果网络环境需要代理，可以通过 `[services.http]` 和 `[services.gmail]` 配置代理。

---

## 6. 安装方式

### 6.1 使用 uv（推荐）

```bash
uv sync
```

### 6.2 使用 pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

当前项目依赖主要包括：
- `curl-cffi`
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`
- `pydoll-python`
- `pysocks`
- `rich`

### 6.3 准备本地配置

仓库中只提供一个示例配置模板：

```text
config.example.toml
```

使用前，请复制一份作为你自己的本地配置文件，并把其中所有形如 `<...>` 的占位内容替换成真实配置。

例如：

```bash
cp config.example.toml config.toml
```

后续运行代码时，请显式传入你自己的本地配置文件路径。

---

## 7. 配置说明

### 7.1 配置文件位置

项目仓库中提供的配置模板为：

```text
config.example.toml
```

推荐使用流程：

```text
1. 先复制 config.example.toml 为你自己的本地配置文件 config.toml
2. 再修改本地配置文件中的占位配置
3. 运行项目
```

### 7.2 重要说明

当前配置解析器有一个重要约束：

- `ConfigService.load()` 要求配置中必须存在：
  - `[services]`
  - `[registers.openai]`

也就是说，即使你当前只想单独测试邮箱服务，只要你是通过 `ConfigService.load("<你的本地配置文件路径>")` 加载配置，`[registers.openai]` 也必须存在。

### 7.3 完整配置示例

> 下面是一个**完整示例**。实际使用时，只保留你当前需要的 provider 配置即可。  
> 例如：如果 `mail_provider = "freemail"`，则可以不配置 `luckmail` / `duckmail` / `firefoxrelay`。  
> 但如果使用 `duckmail` 或 `firefoxrelay`，则必须同时保留 `gmail` 相关配置。

```toml
[services.cpa]
base_url = "https://your-cpa-host/v0/management"
management_password = "YOUR_CPA_MANAGEMENT_PASSWORD"

[services.http]
user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
proxy = ""
http_proxy = ""
https_proxy = ""
proxy_username = ""
proxy_password = ""
impersonate = "chrome136"
ja3 = ""
akamai = ""
timeout_seconds = 60
verify_ssl = true

[services.http.extra_fp]
# 可按需填写 curl-cffi extra_fp 参数

[services.http.default_headers]
Accept-Language = "zh-CN,zh;q=0.9,en;q=0.8"

[services.gmail]
email = "your.email@gmail.com"
proxy = ""
email_length = 8
default_max_results = 20

[services.gmail.api]
credentials_file = "secrets/client_secret.json"
token_dir = "secrets/tokens"
scopes = ["https://www.googleapis.com/auth/gmail.modify"]

[services.luckmail]
base_url = "https://mails.luckyous.com/api/v1/openapi"
api_key = "YOUR_LUCKMAIL_API_KEY"
project_code = "openai"
email_type = "ms_graph"
variant_mode = "dot"
domain = "hotmail.com"

[services.freemail]
base_url = "https://your-freemail-host"
admin_token = "YOUR_FREEMAIL_ADMIN_TOKEN"
domain_index = 0
email_length = 8
max_probe_emails = 10

[services.duckmail]
base_url = "https://quack.duckduckgo.com"
authorization_token = "YOUR_DUCKMAIL_AUTHORIZATION_TOKEN"
forward_gmail = "your.email@gmail.com"

[services.firefoxrelay]
base_url = "https://relay.firefox.com"
session_id = "YOUR_FIREFOX_RELAY_SESSION_ID"
csrf_token = "YOUR_FIREFOX_RELAY_CSRF_TOKEN"
forward_gmail = "your.email@gmail.com"

[registers.openai]
mail_provider = "gmail"
oauth_client_id = "app_EMoamEEZ73f0CkXaXp7hrann"
default_timeout_seconds = 60
callback_server_port = 1455
chrome_binary_path = ""
headless = false
auth_file_dir = "accounts"
default_account_password = ""
```

---

## 8. 配置项详解

### 8.1 `[registers.openai]`

这是注册主流程的核心配置。

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `mail_provider` | 是 | 当前注册流程使用的邮箱 provider，支持：`gmail` / `luckmail` / `freemail` / `duckmail` / `firefoxrelay` |
| `oauth_client_id` | 否 | OpenAI OAuth 客户端 ID，默认已内置 |
| `default_timeout_seconds` | 否 | 页面等待、验证码轮询等超时时间 |
| `callback_server_port` | 否 | 本地 OAuth 回调监听端口 |
| `chrome_binary_path` | 否 | Chrome 可执行文件路径 |
| `headless` | 否 | 是否无头运行浏览器 |
| `auth_file_dir` | 否 | 本地 auth file 输出目录 |
| `default_account_password` | 否 | 注册时固定密码；留空则随机生成 |

### 8.2 `[services.http]`

这是所有基于 `HttpService` 的模块共享的 HTTP 配置。

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `user_agent` | 否 | 默认 UA |
| `proxy` | 否 | 全局代理，优先级高于 `http_proxy` / `https_proxy` |
| `http_proxy` | 否 | HTTP 代理 |
| `https_proxy` | 否 | HTTPS 代理 |
| `proxy_username` | 否 | 代理用户名 |
| `proxy_password` | 否 | 代理密码 |
| `impersonate` | 否 | `curl-cffi` 浏览器指纹模拟值 |
| `ja3` | 否 | JA3 TLS 指纹 |
| `akamai` | 否 | Akamai 指纹 |
| `timeout_seconds` | 否 | 默认超时时间 |
| `verify_ssl` | 否 | 是否校验证书 |
| `default_headers` | 否 | 默认请求头表 |
| `extra_fp` | 否 | 额外指纹字段表 |

### 8.3 `[services.gmail]` 与 `[services.gmail.api]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `services.gmail.email` | 是 | 主 Gmail 地址 |
| `services.gmail.proxy` | 否 | Gmail API / OAuth 使用的代理 |
| `services.gmail.email_length` | 否 | 生成 alias 时的随机后缀长度 |
| `services.gmail.default_max_results` | 否 | Gmail 查询默认返回条数 |
| `services.gmail.api.credentials_file` | 是 | Google OAuth 客户端凭证文件 |
| `services.gmail.api.token_dir` | 是 | token 目录，文件名格式为 `<email>.json` |
| `services.gmail.api.scopes` | 否 | Gmail 授权范围 |

说明：
- 首次运行会触发 Gmail OAuth 授权流程
- token 会保存在 `token_dir/<邮箱>.json`
- 若配置 Gmail 代理，环境中需要可用的 `PySocks`

### 8.4 `[services.luckmail]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `base_url` | 是 | LuckMail OpenAPI 地址 |
| `api_key` | 是 | 用户 API Key |
| `project_code` | 是 | 项目标识 |
| `email_type` | 是 | 邮箱类型 |
| `variant_mode` | 否 | 邮箱变体模式 |
| `domain` | 否 | 指定域名 |

### 8.5 `[services.freemail]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `base_url` | 是 | FreeMail 服务地址 |
| `admin_token` | 是 | FreeMail 管理 Token |
| `domain_index` | 否 | 邮箱域名索引，默认 0 |
| `email_length` | 否 | 邮箱前缀长度 |
| `max_probe_emails` | 否 | 拉取验证码时最多检查的邮件数，不能大于 50 |

### 8.6 `[services.duckmail]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `base_url` | 是 | DuckMail 服务地址 |
| `authorization_token` | 是 | DuckMail 授权令牌 |
| `forward_gmail` | 是 | DuckMail 转发到的 Gmail 地址 |

说明：
- 该 provider 需要同时存在 Gmail 配置
- 验证码是从 `forward_gmail` 对应 Gmail 邮箱中读取的

### 8.7 `[services.firefoxrelay]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `base_url` | 是 | Firefox Relay 服务地址 |
| `session_id` | 是 | 登录态 session_id |
| `csrf_token` | 是 | CSRF Token |
| `forward_gmail` | 是 | 转发到的 Gmail 地址 |

说明：
- 该 provider 需要同时存在 Gmail 配置
- 验证码是从 `forward_gmail` 对应 Gmail 邮箱中读取的

### 8.8 `[services.cpa]`

| 字段 | 是否必填 | 说明 |
|---|---|---|
| `base_url` | 是 | CPA 管理 API 地址 |
| `management_password` | 是 | 上传 auth file 的管理口令 |

说明：
- 仅在运行 `OpenAIRegister` 完整流程并上传 auth file 时必须配置

---

## 9. 使用方法

### 9.1 运行完整注册流程（推荐）

最常见的用法是直接运行注册机。

### 方式一：直接运行模块文件

```bash
python core/openai_register.py
```

### 方式二：通过 Python 调用

```python
from core.openai_register import OpenAIRegister

OpenAIRegister.from_config_file("config.toml").start_sync(register_num=1)
```

### 流程产物

成功后会产生两类结果：

1. 本地授权文件
   - 输出目录由 `registers.openai.auth_file_dir` 控制
   - 文件名通常为：`<注册邮箱>.json`

2. CPA 上传结果
   - 会调用 `services.cpa` 配置对应的管理接口上传 auth file

---

### 9.2 单独使用邮箱服务

如果你只是想测试某个邮箱 provider 的“生成邮箱 + 获取验证码”，可以这样写：

```python
from service.config_service import ConfigService
from service.http_service import HttpService
from service.mail.mail_factory import create_mail_service

app_config = ConfigService.load("config.toml")
http_service = HttpService(app_config.http)
mail_service = create_mail_service(
    app_config,
    app_config.openai_register.mail_provider,
    http_service=http_service,
)

mail_box = mail_service.generate_mail_box()
print("生成邮箱:", mail_box.email)

code = mail_service.get_latest_verification_code(
    mail_box,
    mail_filter=lambda mail_from, subject, receive_at: (
        "openai" in mail_from.lower() or "chatgpt" in subject.lower()
    ),
)
print("验证码:", code)
```

### `mail_filter` 回调说明

所有邮箱服务统一使用以下回调签名：

```python
mail_filter(mail_from: str, subject: str, receive_at: str) -> bool
```

参数说明：
- `mail_from`：发件人
- `subject`：邮件主题
- `receive_at`：收件时间，格式通常为 `YYYY-MM-DD HH:MM:SS`

---

### 9.3 单独使用 GmailService

适合你已经有 Gmail 主邮箱，只想：
- 生成 Gmail alias
- 查询目标邮件
- 获取验证码

```python
from service.config_service import ConfigService
from service.mail.gmail_service import GmailService

app_config = ConfigService.load("config.toml")
gmail_service = GmailService(app_config.gmail)

mail_box = gmail_service.generate_mail_box()
print(mail_box.email)

code = gmail_service.get_latest_verification_code(
    mail_box,
    mail_filter=lambda mail_from, subject, receive_at: "openai" in mail_from.lower(),
)
print(code)
```

---

## 10. 典型场景推荐

### 场景一：你有稳定 Gmail，想追求成功率
推荐：`mail_provider = "gmail"`

原因：
- 依赖最少
- 链路最清晰
- 验证码读取稳定

### 场景二：你希望每次都是真正的新邮箱
推荐：`mail_provider = "luckmail"` 或 `mail_provider = "freemail"`

原因：
- 可生成新的临时邮箱
- 不依赖 Gmail 主邮箱别名

### 场景三：你想用 Duck / Relay 地址，但仍用 Gmail 接收验证码
推荐：
- `mail_provider = "duckmail"`
- 或 `mail_provider = "firefoxrelay"`

注意：
- 必须配置 Gmail API
- 实际验证码读取仍然依赖 Gmail

---

## 11. 注意事项

### 11.1 配置与 provider 的依赖关系
`registers.openai.mail_provider` 决定了需要哪些配置：

- `gmail` → 需要 `services.gmail` + `services.gmail.api`
- `luckmail` → 需要 `services.luckmail`
- `freemail` → 需要 `services.freemail`
- `duckmail` → 需要 `services.duckmail` + `services.gmail` + `services.gmail.api`
- `firefoxrelay` → 需要 `services.firefoxrelay` + `services.gmail` + `services.gmail.api`

### 11.2 Gmail 首次授权
首次使用 Gmail API 时，会触发本地授权流程并生成 token 文件。

### 11.3 HttpService 的 URL 规则
当前 `HttpService` **只接受完整绝对地址**，例如：

```text
https://example.com/api/path
```

不要传：

```text
/api/path
```

### 11.4 敏感信息保护
以下文件或字段都属于敏感信息：
- 你自己的本地配置文件中的 token / password / session_id / csrf_token / api_key
- `secrets/client_secret.json`
- `secrets/tokens/*.json`
- `accounts/*.json`

建议：
- 不要提交到公共仓库
- 使用 `.gitignore` 排除
- 生产环境使用独立密钥

---

## 12. 当前推荐的阅读顺序

如果你要快速理解项目，我建议按下面顺序阅读源码：

1. `core/openai_register.py` —— 看主流程
2. `service/config_service.py` —— 看配置结构
3. `service/mail/mail_factory.py` —— 看 provider 选择逻辑
4. `service/mail/*.py` —— 看各邮箱 provider 实现差异
5. `service/http_service.py` —— 看通用 HTTP 能力
6. `service/cpa_service.py` —— 看上传 auth file 的流程

---

## 13. 总结

这个项目本质上是一个：

> **以邮箱服务为验证码基础设施，以浏览器自动化为执行引擎，以 OAuth + CPA 上传为最终输出的 OpenAI 注册自动化工具。**

如果你要开始使用，最推荐的路径是：

1. 先复制并修改 `config.example.toml`
2. 先确认邮箱 provider 可正常拿到验证码
3. 再运行 `OpenAIRegister.from_config_file("config.toml").start_sync(1)`
4. 最后检查 `accounts/` 输出与 CPA 上传结果
