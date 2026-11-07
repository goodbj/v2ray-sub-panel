"""数据源抓取与节点解析。

原本 V2RayConfig 用 telethon 登录 Telegram 抓频道，本模块改成
直接 HTTP 拉取公开订阅源（纯文本节点列表 / base64 订阅链接），
把内容解析成结构化节点。协议识别思路照搬 V2RayConfig。
"""
import re
import json
import base64
import requests
from urllib.parse import urlparse, parse_qs, unquote

USER_AGENT = "Mozilla/5.0 (compatible; v2ray-sub-panel/1.0)"

# 协议识别：vless / vmess / ss / trojan
CONFIG_RE = re.compile(r"(?:vless|vmess|ss|trojan)://[^\s\"'<>]+", re.IGNORECASE)


def _b64decode(text):
    """容错 base64 解码，失败返回 None。"""
    if not text:
        return None
    try:
        pad = "=" * (-len(text) % 4)
        return base64.b64decode(text + pad, validate=False).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_configs(raw_text):
    """从一段文本里抠出所有 v2ray 配置链接，去重排序。

    先尝试把整段当 base64 解（很多订阅是 base64 编码的节点列表），
    解出来若含协议头就用解码后的内容，否则退回原文正则提取。
    """
    text = raw_text or ""
    candidate = _b64decode(text.strip().replace("\n", "").replace("\r", ""))
    if candidate and any(p in candidate for p in ("vmess://", "vless://", "trojan://", "ss://")):
        text = candidate
    found = CONFIG_RE.findall(text)
    return sorted(set(found))


def parse_node(link):
    """把一个配置链接解析成结构化 dict，解析失败返回 None。"""
    if link.startswith("vmess://"):
        return _parse_vmess(link)
    if link.startswith("vless://"):
        return _parse_vless_trojan(link, "vless")
    if link.startswith("trojan://"):
        return _parse_vless_trojan(link, "trojan")
    if link.startswith("ss://"):
        return _parse_ss(link)
    return None


def _parse_vmess(link):
    raw = link[len("vmess://"):]
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    data = _b64decode(raw)
    if not data:
        return None
    try:
        d = json.loads(data)
    except Exception:
        return None
    return {
        "protocol": "vmess",
        "remark": (d.get("ps") or "").strip(),
        "address": d.get("add") or "",
        "port": int(d.get("port") or 0),
        "uuid": d.get("id") or "",
        "aid": int(d.get("aid") or 0),
        "security": d.get("scy") or "auto",
        "network": (d.get("net") or "tcp").lower(),
        "host": d.get("host") or "",
        "path": d.get("path") or "/",
        "tls": (d.get("tls") or "") == "tls",
        "sni": d.get("sni") or d.get("host") or "",
    }


def _parse_vless_trojan(link, protocol):
    p = urlparse(link)
    user = unquote(p.username or "")
    host = p.hostname or ""
    port = p.port or 0
    remark = unquote(p.fragment or "").strip()
    params = {k: (v[0] if v else "") for k, v in parse_qs(p.query).items()}
    security = (params.get("security") or "none").lower()
    return {
        "protocol": protocol,
        "remark": remark,
        "address": host,
        "port": int(port),
        "uuid": user,  # vless=uuid, trojan=密码
        "network": (params.get("type") or "tcp").lower(),
        "host": params.get("host") or "",
        "path": params.get("path") or "/",
        "tls": security in ("tls", "reality"),
        "sni": params.get("sni") or params.get("peer") or params.get("host") or "",
        "flow": params.get("flow") or "",
        "security": security,
    }


def _parse_ss(link):
    p = urlparse(link)
    remark = unquote(p.fragment or "").strip()
    raw_user = p.username or ""
    # 情况1：userinfo 是 base64(method:passwd)
    try:
        decoded = _b64decode(raw_user)
        if decoded and ":" in decoded:
            method, passwd = decoded.split(":", 1)
            return {
                "protocol": "ss",
                "remark": remark,
                "address": p.hostname or "",
                "port": int(p.port or 0),
                "method": (method or "").strip(),
                "passwd": passwd.strip(),
            }
    except Exception:
        pass
    # 情况2：整段 base64(method:passwd@host:port)
    raw = link[len("ss://"):]
    if "#" in raw:
        raw = raw.split("#", 1)[0]
    decoded = _b64decode(raw)
    if decoded:
        m = re.match(r"(.+?):(.+?)@(.+?):(\d+)", decoded)
        if m:
            return {
                "protocol": "ss",
                "remark": remark,
                "address": m.group(3),
                "port": int(m.group(4)),
                "method": m.group(1).strip(),
                "passwd": m.group(2).strip(),
            }
    return None


def fetch_source(url, timeout=20):
    """HTTP 拉取一个订阅源，返回 (configs列表, error)。"""
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        text = resp.text
    except Exception as e:
        return [], f"fetch failed: {e}"
    configs = extract_configs(text)
    return configs, None
