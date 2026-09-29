"""标准库 OpenRouter 连通性测试；固定免费模型，无重试或收费 fallback。"""

import json
import os
import re
import socket
from pathlib import Path
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL = "openrouter/free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = 45


def load_api_key() -> bool:
    """优先已有环境变量，否则从项目 .env 载入；只返回是否存在。

    支持普通赋值、export 前缀和成对引号，不执行插值或 shell 命令。
    """
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        return True
    path = PROJECT_ROOT / ".env"
    if not path.resolve().is_relative_to(PROJECT_ROOT):
        return False
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].strip()
            name, separator, value = line.partition("=")
            if separator and name.strip() == "OPENROUTER_API_KEY":
                value = value.strip()
                if value[:1] in ("'", '"'):
                    if len(value) < 2 or value[-1] != value[0]:
                        return False
                    value = value[1:-1].strip()
                else:
                    value = value.split(" #", 1)[0].strip()
                if value:
                    os.environ["OPENROUTER_API_KEY"] = value
                    return True
    except (OSError, UnicodeError):
        pass
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不将认证头转发到重定向地址，也不发起第二次请求。
        return None


def redact(text):
    secret = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if secret:
        text = text.replace(secret, "[REDACTED]")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)


def safe_error_text(value):
    """仅用于错误标量：敏感字段/头出现时整段省略，不输出任意远端对象。"""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    text = redact(str(value))
    if re.search(r"authorization|bearer|api[_ -]?key|secret|password|cookie|\.env", text, re.I):
        return "[敏感错误文本已省略]"
    text = re.sub(r"[A-Za-z0-9_./+=-]{24,}", "[REDACTED TOKEN]", text)
    return text[:1500]


def remote_error(envelope):
    """白名单提取；绝不返回 headers、metadata.raw 或完整 response。"""
    error = envelope.get("error") if isinstance(envelope, dict) else None
    if not isinstance(error, dict):
        return {}
    return {name: safe_error_text(error[source])
            for source, name in (("code", "openrouter_code"), ("message", "provider_error"), ("type", "provider_error_type"))
            if source in error and safe_error_text(error[source]) is not None}


def parse_content(content, finish_reason=None):
    """仅在内存中解析原文；只兼容完整的单个 json code fence。"""
    kind = "unknown"
    candidate = content
    if content is None or isinstance(content, str) and not content.strip():
        kind = "empty"
    elif isinstance(content, str):
        stripped = content.strip()
        fence = re.fullmatch(r"```json\r?\n([\s\S]*?)\r?\n```", stripped)
        if stripped.startswith("```"):
            kind = "markdown_code_fence"
        elif stripped.startswith(("{", "[")):
            kind = "malformed_json"
        elif "{" in stripped:
            kind = "natural_language_plus_json"
        if fence:
            candidate = fence.group(1)
    try:
        if not isinstance(candidate, str):
            raise TypeError()
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            return {"status": "error", "error": {"code": "action_validation_error",
                    "message": "模型 JSON 必须是单个 object"}}
        return {"status": "ok", "result": parsed}
    except (json.JSONDecodeError, TypeError) as exc:
        return {"status": "error", "error": {"code": "content_json_error", "message": "模型 content 无法解析为 JSON"},
                "content_type": type(content).__name__,
                "content_length": len(content) if isinstance(content, str) else None,
                "finish_reason": safe_error_text(finish_reason),
                "json_line": getattr(exc, "lineno", None), "json_column": getattr(exc, "colno", None),
                "format": kind,
                "preview": (safe_error_text(content) or "")[:300] if isinstance(content, str) else ""}


def request_json(messages, max_tokens=1024, json_schema=None) -> dict:
    """固定免费模型，单次请求；仅返回 JSON 内容及安全错误。"""
    present = load_api_key()
    attempts = 0
    http_status = None

    def failure(code, message, details=None, parse_error=False):
        result = {"status": "error", "model": MODEL, "key_present": present,
                  "api_calls": attempts, "http_status": http_status,
                  "error_type": code, "timeout": code == "timeout",
                  "json_parse_error": parse_error,
                  "error": {"code": code, "message": message}}
        result.update(details or {})
        return result

    if not present:
        return failure("missing_api_key", "OPENROUTER_API_KEY 未配置")
    payload = {"model": MODEL, "messages": messages,
               "max_tokens": max_tokens, "stream": False,
               "response_format": {"type": "json_object"},
               "provider": {"allow_fallbacks": False}}
    if json_schema is not None:
        payload["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "planner_action", "strict": True, "schema": json_schema}}
        payload["provider"]["require_parameters"] = True
    try:
        request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"].strip(),
                             "Content-Type": "application/json"}, method="POST")
        opener = urllib.request.build_opener(_NoRedirect())
        attempts = 1
        with opener.open(request, timeout=TIMEOUT) as response:
            status = response.status
            http_status = status if type(status) is int else None
            raw = response.read(65537)
        if len(raw) > 65536:
            return failure("response_too_large", "响应超过大小限制")
        try:
            envelope = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError) as exc:
            return failure("response_json_error", "HTTP response body 不是合法 JSON",
                           {"json_line": getattr(exc, "lineno", None), "json_column": getattr(exc, "colno", None)}, True)
        if not isinstance(envelope, dict):
            return failure("invalid_response", "API 响应结构不正确")
        if "error" in envelope:
            return failure("api_error", "OpenRouter 返回 API 错误；未重试或切换模型", remote_error(envelope))
        content = envelope["choices"][0]["message"]["content"]
        parsed = parse_content(content, envelope["choices"][0].get("finish_reason"))
        if parsed["status"] == "error":
            details = {k: v for k, v in parsed.items() if k not in ("status", "error")}
            return failure(parsed["error"]["code"], parsed["error"]["message"], details,
                           parsed["error"]["code"] == "content_json_error")
        return {"status": "ok", "model": MODEL, "key_present": True,
                "api_calls": attempts, "result": parsed["result"]}
    except urllib.error.HTTPError as exc:
        http_status = exc.code
        details = {}
        parse_error = False
        try:
            body = exc.read(65537)
            if len(body) <= 65536:
                details = remote_error(json.loads(body))
        except (ValueError, UnicodeError):
            parse_error = True
        except OSError:
            pass
        finally:
            exc.close()
        return failure("http_error", "OpenRouter HTTP 请求失败；未重试或切换模型", details, parse_error)
    except (KeyError, IndexError, TypeError):
        return failure("invalid_response", "API 响应缺少预期字段")
    except (TimeoutError, socket.timeout):
        return failure("timeout", "OpenRouter 请求超时；未重试")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return failure("timeout", "OpenRouter 请求超时；未重试")
        return failure("connection_error", "网络连接失败；未重试")
    except (OSError, ValueError):
        return failure("connection_error", "网络、超时或请求配置错误；未重试")


def test_connection() -> dict:
    expected = {"status": "ok", "message": "connection successful"}
    result = request_json([{"role": "user", "content":
        'Return only this JSON object: {"status":"ok","message":"connection successful"}'}], max_tokens=128)
    if result["status"] == "ok" and result["result"] != expected:
        result.pop("result")
        result.update(status="error", error={"code": "unexpected_content", "message": "模型未返回预期的连通性 JSON"})
    return result


if __name__ == "__main__":
    result = test_connection()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "ok" else 1)
