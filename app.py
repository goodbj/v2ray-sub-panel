"""Flask 主应用：管理后台 + 订阅分发 + 配置获取 API。

路由：
  GET  /                      -> 重定向到 /admin
  GET  /admin                 -> 后台（Basic Auth）
  POST /admin/api/sources     -> 增删订阅源
  POST /admin/api/fetch       -> 手动触发抓取
  POST /admin/api/subs        -> 建订阅链接
  GET  /sub/<sub_id>          -> 订阅分发（base64）
  GET  /api/nodes             -> 节点列表 API（可按协议过滤）

环境变量：
  DATA_DIR     数据目录（Cloady 挂载卷，默认 /data）
  PORT         监听端口（Cloady 注入，默认 8000）
  ADMIN_USER   后台登录用户名（默认 admin）
  ADMIN_PASS   后台登录密码（默认读 db 里的 admin_pass）
"""
import os
import base64
import threading
from flask import Flask, request, redirect, url_for, jsonify, Response

import db
import fetcher
from admin_template import ADMIN_HTML

app = Flask(__name__)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "1800"))  # 秒，默认30分钟


# ---- 鉴权 ----
def check_auth(username, pw):
    return username == ADMIN_USER and pw == db.get_admin_pass()


@app.before_request
def require_auth():
    # 只有后台 API/页面需要登录；/sub 和 /api/nodes 对外
    if request.path.startswith("/admin"):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                "Authentication required",
                401,
                {"WWW-Authenticate": 'Basic realm="v2ray-sub-panel"'},
            )


# ---- 页面 ----
@app.route("/")
def index():
    return redirect(url_for("admin"))


@app.route("/admin")
def admin():
    return _render_admin()


def _render_admin():
    sources = db.list_sources()
    subs = db.list_subs()
    nodes = db.list_nodes()
    stats = {
        "total": len(nodes),
        "by_proto": _count_by(nodes, "protocol"),
    }
    return app.jinja_env.from_string(ADMIN_HTML).render(
        sources=sources, subs=subs, nodes=nodes, stats=stats,
        admin_user=ADMIN_USER, admin_pass=db.get_admin_pass(),
    )


def _count_by(rows, key):
    out = {}
    for r in rows:
        out[r[key]] = out.get(r[key], 0) + 1
    return out


# ---- 后台 API ----
@app.route("/admin/api/sources", methods=["POST"])
def api_source():
    action = request.form.get("action")
    url = request.form.get("url", "").strip()
    if action == "add" and url:
        db.add_source(url, request.form.get("remark", ""))
    elif action == "delete" and url:
        db.delete_source(url)
    elif action == "toggle" and url:
        db.set_source_enabled(url, request.form.get("enabled") == "1")
    return redirect(url_for("admin"))


@app.route("/admin/api/fetch", methods=["POST"])
def api_fetch():
    result = run_fetch_all()
    return jsonify(result)


@app.route("/admin/api/subs", methods=["POST"])
def api_sub():
    action = request.form.get("action")
    name = request.form.get("name", "").strip()
    if action == "create" and name:
        sub_id = db.create_sub(name, request.form.get("protocols", ""))
        return jsonify({"ok": True, "sub_id": sub_id})
    elif action == "delete":
        db.delete_sub(request.form.get("sub_id", ""))
    return redirect(url_for("admin"))


@app.route("/admin/api/settings", methods=["POST"])
def api_settings():
    new_pass = request.form.get("admin_pass", "").strip()
    if new_pass:
        db.set_admin_pass(new_pass)
    return redirect(url_for("admin"))


# ---- 对外：订阅分发 ----
@app.route("/sub/<sub_id>")
def sub_distribute(sub_id):
    sub = db.get_sub(sub_id)
    if not sub:
        return "subscription not found", 404
    nodes = db.nodes_for_sub(sub)
    links = [n["link"] for n in nodes if n.get("link")]
    raw = "\n".join(links)
    b64 = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return Response(b64, mimetype="text/plain; charset=utf-8")


# ---- 对外：节点 API ----
@app.route("/api/nodes")
def api_nodes():
    proto = request.args.get("protocol")
    nodes = db.list_nodes(protocol=proto)
    return jsonify([n["link"] for n in nodes])


# ---- 抓取逻辑 ----
def run_fetch_all():
    sources = db.list_sources()
    total_added = 0
    errors = []
    for s in sources:
        if not s["enabled"]:
            continue
        configs, err = fetcher.fetch_source(s["url"])
        if err:
            db.update_source_fetch(s["url"], 0, err)
            errors.append({"url": s["url"], "error": err})
            continue
        added = db.upsert_nodes(s["id"], configs)
        total_added += added
        db.update_source_fetch(s["url"], len(configs))
    return {"added": total_added, "sources": len(sources), "errors": errors}


def _background_refresh():
    """定时自动抓取（独立线程）。"""
    import time

    while True:
        time.sleep(REFRESH_INTERVAL)
        try:
            run_fetch_all()
        except Exception:
            pass


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "nodes": db.count_nodes()})


def start_background():
    t = threading.Thread(target=_background_refresh, daemon=True)
    t.start()


if __name__ == "__main__":
    if os.getenv("AUTO_FETCH", "1") == "1":
        start_background()
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
