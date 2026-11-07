"""SQLite 数据层。数据目录默认 /data（Cloady 挂载卷），无挂载时回落本地。

表：
  sources   订阅源（URL + 启用 + 抓取状态）
  nodes     解析后的节点（去重存原始链接）
  subs      对外订阅（id + 名称 + 绑定的节点筛选）
  settings  单列 KV（管理密码等）
"""
import os
import sqlite3
import secrets
from contextlib import contextmanager
from datetime import datetime

DATA_DIR = os.getenv("DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "panel.db")
SCHEMA_VERSION = 1

# 首次空库自动种入的默认公开订阅源（纯文本节点列表 / base64 订阅链接）。
# 这些源长期活跃，但稳定性不保证；可在后台随时增删。
DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/main/Config/vless.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/main/Config/vmess.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/main/Config/shadowsocks.txt",
    "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subscriptions/all_configs_base64.txt",
]


def _init():
    os.makedirs(DATA_DIR, exist_ok=True)
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                remark TEXT DEFAULT '',
                last_fetch TEXT,
                last_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                protocol TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                remark TEXT DEFAULT '',
                address TEXT DEFAULT '',
                port INTEGER DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sub_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                protocols TEXT DEFAULT '',   -- 逗号分隔过滤，空=全协议
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_nodes_link ON nodes(link);
            CREATE INDEX IF NOT EXISTS idx_nodes_enabled ON nodes(enabled);
            """
        )
        cur = c.execute("SELECT value FROM settings WHERE key='schema_version'")
        row = cur.fetchone()
        if not row:
            c.execute(
                "INSERT INTO settings(key,value) VALUES('schema_version',?)",
                (str(SCHEMA_VERSION),),
            )
            # 首次：没设 ADMIN_PASS 才随机生成
            if not os.getenv("ADMIN_PASS") and not c.execute(
                "SELECT value FROM settings WHERE key='admin_pass'"
            ).fetchone():
                c.execute(
                    "INSERT INTO settings(key,value) VALUES('admin_pass',?)",
                    (secrets.token_hex(8),),
                )
            # 首次空库：自动种入默认公开订阅源（无卷场景兜底，启动即抓）
            if not c.execute("SELECT COUNT(*) FROM sources").fetchone()[0]:
                for u in DEFAULT_SOURCES:
                    c.execute(
                        "INSERT INTO sources(url,remark,created_at) VALUES(?,?,?)",
                        (u, "默认公开源", _now()),
                    )
    # ADMIN_PASS 每次启动都覆盖：设了 env 就以 env 为准，不设才用库里的值
    env_pass = os.getenv("ADMIN_PASS")
    if env_pass:
        with _conn() as c:
            c.execute(
                "INSERT INTO settings(key,value) VALUES('admin_pass',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (env_pass,),
            )
            # 首次空库：自动种入默认公开订阅源（无卷场景兜底，启动即抓）
            if not c.execute("SELECT COUNT(*) FROM sources").fetchone()[0]:
                for u in DEFAULT_SOURCES:
                    c.execute(
                        "INSERT INTO sources(url,remark,created_at) VALUES(?,?,?)",
                        (u, "默认公开源", _now()),
                    )


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ---- settings ----
def get_setting(key, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value):
    with _conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_admin_pass():
    return get_setting("admin_pass") or "admin"


def set_admin_pass(new_pass):
    set_setting("admin_pass", new_pass)


# ---- sources ----
def add_source(url, remark=""):
    with _conn() as c:
        c.execute(
            "INSERT INTO sources(url,remark,created_at) VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET enabled=1,remark=excluded.remark",
            (url, remark, _now()),
        )


def list_sources():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM sources ORDER BY id DESC")]


def update_source_fetch(url, count, error=None):
    with _conn() as c:
        c.execute(
            "UPDATE sources SET last_fetch=?, last_count=?, last_error=? WHERE url=?",
            (_now(), count, error, url),
        )


def set_source_enabled(url, enabled):
    with _conn() as c:
        c.execute("UPDATE sources SET enabled=? WHERE url=?", (1 if enabled else 0, url))


def delete_source(url):
    with _conn() as c:
        c.execute("DELETE FROM sources WHERE url=?", (url,))


# ---- nodes ----
def upsert_nodes(source_id, links):
    """批量写入节点，link 唯一冲突则忽略。返回新增数量。"""
    added = 0
    with _conn() as c:
        for link in links:
            node = parse_for_store(link)
            if not node:
                continue
            try:
                c.execute(
                    "INSERT INTO nodes(source_id,protocol,link,remark,address,port,created_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        source_id,
                        node["protocol"],
                        node["link"],
                        node["remark"],
                        node["address"],
                        node["port"],
                        _now(),
                    ),
                )
                added += 1
            except sqlite3.IntegrityError:
                pass
    return added


def parse_for_store(link):
    """只取展示用字段，避免循环 import 重解析。"""
    from fetcher import parse_node

    n = parse_node(link)
    if not n:
        return None
    return {
        "protocol": n["protocol"],
        "link": link,
        "remark": n.get("remark", "") or "",
        "address": n.get("address", "") or "",
        "port": n.get("port", 0) or 0,
    }


def list_nodes(protocol=None, enabled_only=True):
    sql = "SELECT * FROM nodes"
    params = []
    where = []
    if enabled_only:
        where.append("enabled=1")
    if protocol:
        where.append("protocol=?")
        params.append(protocol)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params)]


def set_node_enabled(node_id, enabled):
    with _conn() as c:
        c.execute("UPDATE nodes SET enabled=? WHERE id=?", (1 if enabled else 0, node_id))


def delete_node(node_id):
    with _conn() as c:
        c.execute("DELETE FROM nodes WHERE id=?", (node_id,))


def count_nodes():
    with _conn() as c:
        return c.execute("SELECT COUNT(*) AS n FROM nodes WHERE enabled=1").fetchone()["n"]


# ---- subs ----
def create_sub(name, protocols=""):
    sub_id = secrets.token_hex(6)
    with _conn() as c:
        c.execute(
            "INSERT INTO subs(sub_id,name,protocols,created_at) VALUES(?,?,?,?)",
            (sub_id, name, protocols, _now()),
        )
    return sub_id


def list_subs():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM subs ORDER BY id DESC")]


def get_sub(sub_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM subs WHERE sub_id=?", (sub_id,)).fetchone()
        return dict(row) if row else None


def delete_sub(sub_id):
    with _conn() as c:
        c.execute("DELETE FROM subs WHERE sub_id=?", (sub_id,))


def nodes_for_sub(sub):
    protos = [p.strip() for p in (sub.get("protocols") or "").split(",") if p.strip()]
    return list_nodes(protocol=protos[0] if len(protos) == 1 else None)


# 启动时初始化
_init()
