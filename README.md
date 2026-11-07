# V2Ray 订阅面板

一体化 Flask 后端：从公开订阅源自动抓取节点、后台管理、订阅分发。数据存储 SQLite + Cloady 挂载卷。

## 功能

- **数据源管理**：添加公开订阅源 URL（纯文本节点列表 / base64 订阅链接），支持启用/禁用
- **自动抓取**：定时 HTTP 拉取订阅源并解析节点（支持 vless/vmess/trojan/ss 协议），默认 30 分钟
- **节点管理**：去重存储节点列表，可按协议过滤
- **订阅分发**：创建订阅链接 `/sub/<id>`，对外分发 base64 节点列表
- **节点 API**：`/api/nodes?protocol=vless` 获取 JSON 节点列表
- **后台鉴权**：管理后台 Basic Auth 保护，默认用户名 `admin`，首次启动自动生成随机密码

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `/data` | 数据目录（SQLite 挂载点） |
| `PORT` | `8000` | 监听端口 |
| `ADMIN_USER` | `admin` | 后台登录用户名 |
| `AUTO_FETCH` | `1` | 是否启动后台定时抓取线程 |
| `REFRESH_INTERVAL` | `1800` | 自动抓取间隔（秒） |

## 部署到 Cloady

1. **创建 GitHub 仓库**：`goodbj/v2ray-sub-panel`，推送本目录所有文件
2. **Cloady 控制台**：
   - 创建 Workspace
   - 新建 App → Deploy from GitHub → 选择仓库
   - 挂载 Volume：挂载路径 `/data`
   - 环境变量：`DATA_DIR=/data`（默认即可）
3. **启动后访问**：
   - 后台：`https://<your-domain>/admin`（Basic Auth 登录）
   - 订阅：`https://<your-domain>/sub/<sub_id>`
   - 节点 API：`https://<your-domain>/api/nodes?protocol=vless`

## 本地运行

```bash
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python app.py
```

访问 `http://localhost:8000/admin`。

## 数据结构

- `sources`：订阅源（URL + 启用 + 抓取状态）
- `nodes`：解析后的节点（去重存原始链接）
- `subs`：对外订阅（id + 名称 + 协议过滤）
- `settings`：单列 KV（管理密码等）

## 抓取逻辑说明

原本 V2RayConfig 用 telethon 登录 Telegram 抓频道，本模块改成 HTTP 拉取公开订阅源：
- 先尝试把整段当 base64 解码（很多订阅是 base64 编码的节点列表）
- 解出后若含协议头（`vmess://`、`vless://`、`trojan://`、`ss://`）就用解码后的内容
- 否则退回原文正则提取配置链接
- 协议识别正则照搬 V2RayConfig 的思路

## 安全说明

- 后台 `/admin` 及其 API 需要 Basic Auth
- 订阅链接 `/sub/<id>` 和节点 API `/api/nodes` 对外开放（可根据需要在 Cloady 层添加 IP 白名单）
- 数据存储 SQLite + 挂载卷持久化
