"""后台 HTML 模板（字符串），被 app.py 引用为 ADMIN_HTML 常量。"""

ADMIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V2Ray 订阅面板</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 0; background: #0f1117; color: #e6e6e6; }
  header { padding: 16px 24px; background: #1a1d27; border-bottom: 1px solid #2a2e3a; }
  header h1 { margin: 0; font-size: 18px; }
  .wrap { padding: 24px; max-width: 1100px; margin: 0 auto; }
  .card { background: #1a1d27; border: 1px solid #2a2e3a; border-radius: 10px; padding: 18px; margin-bottom: 20px; }
  .card h2 { margin: 0 0 14px; font-size: 15px; color: #9aa4b2; }
  input, button, select { font-size: 14px; padding: 8px 10px; border-radius: 6px; border: 1px solid #2a2e3a; background: #0f1117; color: #e6e6e6; }
  input[type=text], input[type=url] { width: 100%; }
  button { background: #3b82f6; border: none; color: #fff; cursor: pointer; }
  button:hover { background: #2563eb; }
  button.danger { background: #ef4444; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #2a2e3a; }
  th { color: #9aa4b2; font-weight: 600; }
  .stat { display: inline-block; margin-right: 16px; }
  .stat b { font-size: 22px; color: #3b82f6; }
  .small { font-size: 12px; color: #9aa4b2; }
  .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
  .row > div { flex: 1; min-width: 200px; }
  code { background: #0f1117; padding: 2px 6px; border-radius: 4px; }
  .ok { color: #22c55e; } .err { color: #ef4444; }
</style>
</head>
<body>
<header><h1>🛰️ V2Ray 订阅面板</h1></header>
<div class="wrap">

  <div class="card">
    <h2>概览</h2>
    <div class="stat">节点总数 <b>{{ stats.total }}</b></div>
    {% for p, c in stats.by_proto.items() %}
      <div class="stat">{{ p }} <b>{{ c }}</b></div>
    {% endfor %}
    <form method="post" action="/admin/api/fetch" style="margin-top:12px;display:inline-block">
      <button type="submit">🔄 立即抓取全部源</button>
    </form>
  </div>

  <div class="card">
    <h2>订阅源（数据源）</h2>
    <form method="post" action="/admin/api/sources">
      <div class="row">
        <div><label class="small">订阅源 URL（纯文本节点列表 / base64 订阅链接）</label>
          <input type="url" name="url" placeholder="https://example.com/sub.txt" required></div>
        <div style="flex:0 0 220px"><label class="small">备注</label>
          <input type="text" name="remark" placeholder="来源说明"></div>
        <div style="flex:0 0 120px">
          <input type="hidden" name="action" value="add">
          <button type="submit">+ 添加源</button>
        </div>
      </div>
    </form>
    <table style="margin-top:14px">
      <tr><th>URL</th><th>备注</th><th>状态</th><th>上次抓取</th><th>节点数</th><th>操作</th></tr>
      {% for s in sources %}
      <tr>
        <td><code>{{ s.url }}</code></td>
        <td>{{ s.remark }}</td>
        <td>{% if s.enabled %}<span class="ok">启用</span>{% else %}<span class="err">禁用</span>{% endif %}</td>
        <td class="small">{{ s.last_fetch or '-' }}<br>{% if s.last_error %}<span class="err">{{ s.last_error }}</span>{% endif %}</td>
        <td>{{ s.last_count }}</td>
        <td>
          <form method="post" action="/admin/api/sources" style="display:inline">
            <input type="hidden" name="url" value="{{ s.url }}">
            <input type="hidden" name="action" value="toggle">
            <input type="hidden" name="enabled" value="{% if s.enabled %}0{% else %}1{% endif %}">
            <button>{% if s.enabled %}禁用{% else %}启用{% endif %}</button>
          </form>
          <form method="post" action="/admin/api/sources" style="display:inline">
            <input type="hidden" name="url" value="{{ s.url }}">
            <input type="hidden" name="action" value="delete">
            <button class="danger">删除</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>

  <div class="card">
    <h2>订阅链接（对外分发）</h2>
    <form method="post" action="/admin/api/subs">
      <div class="row">
        <div><label class="small">名称</label>
          <input type="text" name="name" placeholder="我的订阅" required></div>
        <div><label class="small">协议过滤（空=全部，逗号分隔：vless,vmess,trojan,ss）</label>
          <input type="text" name="protocols" placeholder="vless,vmess"></div>
        <div style="flex:0 0 120px">
          <input type="hidden" name="action" value="create">
          <button type="submit">+ 创建</button>
        </div>
      </div>
    </form>
    <table style="margin-top:14px">
      <tr><th>名称</th><th>订阅链接</th><th>协议过滤</th><th>操作</th></tr>
      {% for sub in subs %}
      <tr>
        <td>{{ sub.name }}</td>
        <td><code>/sub/{{ sub.sub_id }}</code></td>
        <td class="small">{{ sub.protocols or '全部' }}</td>
        <td>
          <form method="post" action="/admin/api/subs" style="display:inline">
            <input type="hidden" name="action" value="delete">
            <input type="hidden" name="sub_id" value="{{ sub.sub_id }}">
            <button class="danger">删除</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </table>
  </div>

  <div class="card">
    <h2>节点列表（共 {{ nodes|length }} 条）</h2>
    <table>
      <tr><th>协议</th><th>备注</th><th>地址</th><th>端口</th><th>状态</th></tr>
      {% for n in nodes[:200] %}
      <tr>
        <td>{{ n.protocol }}</td>
        <td>{{ n.remark }}</td>
        <td class="small">{{ n.address }}</td>
        <td>{{ n.port }}</td>
        <td>{% if n.enabled %}<span class="ok">启用</span>{% else %}<span class="err">禁用</span>{% endif %}</td>
      </tr>
      {% endfor %}
    </table>
    {% if nodes|length > 200 %}<p class="small">仅显示前 200 条，完整列表通过订阅链接获取。</p>{% endif %}
  </div>

  <div class="card">
    <h2>设置</h2>
    <form method="post" action="/admin/api/settings">
      <div class="row">
        <div><label class="small">后台登录用户名</label>
          <input type="text" value="{{ admin_user }}" disabled></div>
        <div><label class="small">新密码</label>
          <input type="text" name="admin_pass" placeholder="输入新密码"></div>
        <div style="flex:0 0 120px">
          <button type="submit">保存</button>
        </div>
      </div>
    </form>
    <p class="small">当前用户名：<code>{{ admin_user }}</code> ｜ 部署后请立即修改密码。订阅链接 <code>/sub/&lt;id&gt;</code> 与节点 API <code>/api/nodes</code> 无需登录。</p>
  </div>

</div>
</body>
</html>
"""
