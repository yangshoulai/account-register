import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

from .logger import get_logger

LOGGER = get_logger("OpenAI Register")


@dataclass(frozen=True)
class OAuthStart:
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str
    client_id: str


@dataclass
class CallbackUrl:
    code: str
    state: str
    error: str
    error_description: str


def _jwt_claims_no_verify(id_token: str) -> Dict[str, Any]:
    # WARNING: no signature verification; this only decodes claims to extract fields.
    if not id_token or id_token.count(".") < 2:
        return {}
    payload_b64 = id_token.split(".")[1]
    pad = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload = base64.urlsafe_b64decode((payload_b64 + pad).encode("ascii"))
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _parse_callback_url(callback_url: str) -> Optional[CallbackUrl]:
    candidate = callback_url.strip()
    if not candidate:
        return None
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)

    # Query takes precedence; fragment is a fallback.
    for key, values in fragment.items():
        if key not in query or not query[key] or not (query[key][0] or "").strip():
            query[key] = values

    def get1(k: str) -> str:
        v = query.get(k, [""])
        return (v[0] or "").strip()

    code = get1("code")
    state = get1("state")
    error = get1("error")
    error_description = get1("error_description")

    # Handle malformed callback payloads where state is appended with '#'.
    if code and not state and "#" in code:
        code, state = code.split("#", 1)

    if not error and error_description:
        error, error_description = error_description, ""

    return CallbackUrl(code, state, error, error_description)


def generate_pkce() -> Tuple[str, str]:
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)


def submit_callback_url(
        callback_url: str,
        client_id: str,
        expected_state: str,
        code_verifier: str,
        redirect_uri: str
) -> Dict[str, Any]:
    cb = _parse_callback_url(callback_url)
    if not cb:
        raise ValueError("Invalid callback URL")
    if cb.error:
        raise RuntimeError(f"oauth error: {cb.error}: {cb.error_description}".strip())
    if not cb.code:
        raise ValueError("callback url missing ?code=")
    if not cb.state:
        raise ValueError("callback url missing ?state=")
    if cb.state != expected_state:
        raise ValueError("state mismatch")

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": cb.code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://auth.openai.com/oauth/token",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if resp.status != 200:
                raise RuntimeError(f"token exchange failed: {resp.status}: {raw.decode('utf-8', 'replace')}")
            token_resp = json.loads(raw.decode("utf-8"))
            return create_cpa_auth_file_payload(token_resp)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(f"token exchange failed: {exc.code}: {raw.decode('utf-8', 'replace')}")


def create_cpa_auth_file_payload(auth_token_resp: Dict[str, Any], email: str = "") -> Dict[str, Any]:
    access_token = (auth_token_resp.get("access_token") or "").strip()
    refresh_token = (auth_token_resp.get("refresh_token") or "").strip()
    id_token = (auth_token_resp.get("id_token") or "").strip()
    expires_in = _to_int(auth_token_resp.get("expires_in"))

    claims = _jwt_claims_no_verify(id_token or access_token)
    claim_email = str(claims.get("email") or "").strip()
    auth_claims = claims.get("https://api.openai.com/auth") or {}
    account_id = str(auth_claims.get("chatgpt_account_id") or "").strip()

    now = int(time.time())
    expired_rfc3339 = ""
    if expires_in != 0:
        expired_rfc3339 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + max(expires_in, 0)))
    else:
        exp_timestamp = claims.get("exp", 0)
        if exp_timestamp > 0:
            expired_rfc3339 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(exp_timestamp))

    now_rfc3339 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    return {
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "account_id": account_id,
        "last_refresh": now_rfc3339,
        "email": claim_email or email,
        "type": "codex",
        "expired": expired_rfc3339,
    }


def generate_oauth_url(client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann", callback_sever_port: int = 1455) -> OAuthStart:
    state = secrets.token_urlsafe(16)
    code_verifier = secrets.token_urlsafe(64)

    sha256_raw = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(sha256_raw).decode("ascii").rstrip("=")

    redirect_uri = f"http://localhost:{callback_sever_port}/auth/callback"

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid email profile offline_access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    auth_url = f"https://auth.openai.com/oauth/authorize?{urllib.parse.urlencode(params)}"
    return OAuthStart(
        auth_url=auth_url,
        state=state,
        code_verifier=code_verifier,
        redirect_uri=redirect_uri,
        client_id=client_id,
    )
