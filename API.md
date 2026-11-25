# AppGo 开放 API 契约（v1）

AppGo 把 Android APP 生成能力以 REST API 开放：任何能发起 HTTP 请求的本地
coding agent（Qoder / Claude Code / Kiro / 自研脚本）都可以接入。充值与账户
管理在 AppGo 网站完成，API 与网站同价（Credits 通用）。

- Base URL：`https://www.letwx.net`（可用环境变量 `APPGO_BASE_URL` 覆盖）
- 鉴权：请求头 `X-API-Key: <你的密钥>`（`agku_` 开头，控制台「API 接入」生成）
- 固定请求头：`tenant-id: 1`（平台租户，保持默认）
- 编码：请求/响应均为 UTF-8 JSON；下载端点除外

## 响应结构

业务端点统一返回 `CommonResult`：

```json
{ "code": 0, "data": <业务数据>, "msg": "" }
```

`code=0` 成功；非 0 失败，`msg` 为可读原因。HTTP 层错误：401（密钥无效/未认证）、
402（体验用户未充值不能导出源码）、403（交付物超保留期）、404（资源不存在）、
429 系风控拒绝以业务码返回。

## 任务状态机（devStatus）

| 状态 | 含义 | 下一步 |
|------|------|--------|
| 0 | 待开发（复杂度评估中） | 轮询等待 |
| 3 | 待确认（报价已回写） | 展示报价 → 用户确认后调 confirm |
| 4 | 生成中（已冻结 Credits） | 轮询等待 |
| 1 | 已完成 | 可下载源码/APK |
| 2 | 失败 | Credits 已全额退回，可调整需求重新创建 |

## 计费说明

- 创建任务免费；报价确认（confirm）时冻结 Credits；生成成功核销、失败全额退回。
- 首单优惠在报价时快照，确认冻结额 = 标准 Credits − 首单优惠（见 priceQuote）。
- 源码一经导出不再受理退款。
- 内容安全：需求描述先经关键词黑名单审核、再经 LLM 语义审核增强（LLM 不可用时自动降级为仅关键词），违规直接拒绝（创建/迭代前零成本，不透出具体原因）。
- 限流：进行中任务 ≤ 3 个；每日创建 ≤ 10 个；API Key 单账户 ≤ 5 个。

## 端点

### 一期主工作流（skill 默认使用）

#### POST /app-api/appgo/dev-app/create — 创建任务（免费）

```json
{
  "appName": "喝水提醒",            // 必填，≤20 字
  "codePrompt": "功能描述…",        // 必填，10~2000 字
  "appType": "效率工具",            // 可选，留空自动推断
  "uiPrompt": "简约蓝",             // 可选，视觉风格
  "packageName": "com.example.app", // 可选，留空自动分配
  "callbackUrl": "http://127.0.0.1:9000/appgo-hook",  // 可选，Webhook 回调地址（http/https）
  "h5PrototypeZipUrl": "https://…/devapp-h5-prototype/1/…-prototype.zip",  // 可选，H5/UI 原型包（先经 upload-prototype 上传）
  "h5PrototypeZipName": "原型.zip"  // 可选，与上一字段配套的原始文件名
}
```

传 `callbackUrl` 后任务状态变更会向该地址 POST 回调（见下方「Webhook 回调」章节），
平台生成的 `webhookSecret` 随任务详情（get）返回。

返回 `data`：任务编号（Long）。

#### POST /app-api/appgo/dev-app/upload-prototype — 上传 H5/UI 原型包

`multipart/form-data`，字段名 `file`；仅 `.zip` 且 ≤50MB（否则返回
`PROTOTYPE_ZIP_INVALID`）。返回 `data`：

```json
{ "url": "https://…/devapp-h5-prototype/1/1728…-prototype.zip", "fileName": "1728…-prototype.zip" }
```

- CLI 推荐直接 `submit --h5-zip ./原型.zip`（自动上传后随任务提交）；已有托管 URL 时
  先 `upload ./原型.zip` 拿 URL 再 `submit --h5-zip-url <url>`；
- zip 建议结构：`PRODUCT_SPECS.md`（应用名/包名/功能需求）、`DESIGN_SPECS.md`（UI 规格，可选）、
  `figma_prototype/`（页面 HTML + `icons/` SVG 图标）；解压后总内容 ≤250MB，禁止绝对路径与 `..` 路径段；
- 生成时流水线以原型为 UI 第一依据（h5_zip 模式：页面深度遍历实现、图标自动转 Android drawable），
  zip 无法解析时自动降级为纯描述（design_md）模式，任务不会因此失败；
- 原型包内容需自行确保合规。

#### GET /app-api/appgo/dev-app/get?id={id} — 单任务详情（轮询用）

返回 `data`：任务对象（字段见下）。仅归属会员可查，他人任务与不存在同样报
`DEV_APP_NOT_EXISTS`（防探测）。

#### GET /app-api/appgo/dev-app/my-list — 我的任务列表

返回 `data`：任务对象数组，按创建时间倒序。

#### POST /app-api/appgo/dev-app/confirm — 确认报价并冻结 Credits

```json
{ "id": 123 }
```

仅状态 3 可确认；余额不足返回 `CREDIT_BALANCE_NOT_ENOUGH`。返回 `data: true`。

#### GET /app-api/appgo/dev-app/source-download?id={id} — 下载源码 ZIP

302 重定向到签名短链（HTTP 客户端需开启跟随重定向）。要求：状态 1、账户已充值、
未超 3 天保留期（或已购托管）。**首次导出成功即落库导出标记（不再退款）**。
剥离 build/.git/node_modules 等缓存与内部凭据后打包。

#### GET /app-api/appgo/dev-app/apk-download?id={id} — 下载 APK

同上约束（不含导出标记语义）。

### API Key 管理（控制台同能力，网站 JWT 调用；X-API-Key 不可管理自身）

- `POST /app-api/appgo/api-key/create` `{name}` → 签发（完整 key 仅本次返回）
- `GET /app-api/appgo/api-key/my-list` → 列表（仅 key 前 12 位）
- `POST /app-api/appgo/api-key/revoke` `{id}` → 吊销（幂等）

### 迭代与失败恢复（skill 主工作流覆盖，CLI 直接可用）

- `POST /app-api/appgo/dev-app/iterate/quote` — 迭代报价预览（不产生计费/状态变更）

  ```json
  { "id": 123, "iterationPrompt": "首页背景改蓝色" }
  ```

  返回：`{score, surchargeScore, tier, quoteYuan, quoteCredits, overLimit, balance, balanceEnough}`；
  `overLimit=true`（打分≥14 旗舰档）时平台拒绝执行，建议作为新应用下单。
  CLI：`python appgo.py iterate-quote --id 123 --add "…"`（**必须先向用户展示本轮报价**）

- `POST /app-api/appgo/dev-app/iterate` — 对已完成任务发起迭代优化（按本轮报价冻结 Credits，失败全额退回）

  ```json
  { "id": 123, "iterationPrompt": "首页背景改蓝色", "expectedCredits": 600 }
  ```

  `expectedCredits` 传 iterate/quote 返回的 quoteCredits（后端复算不一致时报价变化提示）。
  CLI：`python appgo.py iterate --id 123 --add "…" --expected-credits 600`

- `POST /app-api/appgo/dev-app/retry` `{id}` — 首次生成失败后按原确认冻结额重试（复用原始需求）

  CLI：`python appgo.py retry --id 123`

- `POST /app-api/appgo/dev-app/redesign` `{id, codePrompt}` — 简化需求重新报价
  （仅状态 3 且未计费；退回原冻结额回到状态 0 重新评估，首单折扣重新判定）

  CLI：`python appgo.py redesign --id 123 --prompt "简化后的需求"`

- `GET /app-api/appgo/dev-app/versions?id={id}` — 版本记录（托管迭代追溯）
- `GET /app-api/appgo/pricing/config` — 定价配置（汇率/档位价/注册赠送，公开）
- `GET /app-api/appgo/dev-app/categories` — 品类清单（公开）

## Webhook 回调（可选）

创建任务时传 `callbackUrl`（http/https），该任务状态变更时平台向该地址 POST JSON。
适合长期运行的 agent 做事件驱动，免轮询。

| 事件（X-AppGo-Event） | 触发时机 | data 附加字段 |
|----------------------|---------|--------------|
| quote_ready | 复杂度评估完成、报价已出（状态 →3） | complexityTier / quotedCredits / firstOrderDiscount |
| completed | 生成完成（状态 →1） | iterationCount / gitUrl（有源码托管时，否则空串） |
| failed | 首次生成失败（状态 →2；迭代失败自动回滚不回调，应用仍可用） | failReason（截断 200 字） |

payload 结构：

```json
{
  "event": "quote_ready",
  "appId": 123,
  "appName": "喝水提醒",
  "packageName": "com.appgo.u1.tabs34",
  "devStatus": 3,
  "timestamp": 1728360000000,
  "data": { "complexityTier": "标准", "quotedCredits": 990, "firstOrderDiscount": 500 }
}
```

投递 Header：

- `X-AppGo-Event`：事件名（见上表）
- `X-AppGo-Delivery`：投递记录编号（可与 webhook-logs 对账）
- `X-AppGo-Timestamp`：Unix 秒级时间戳
- `X-AppGo-Signature`：`sha256=<HMAC-SHA256(webhookSecret, timestamp + "." + 请求体原文)>` 的 hex

验签示例（Python）：

```python
import hashlib, hmac

def verify(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), (timestamp + ".").encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + expected, signature or "")
```

投递与重试：

- `webhookSecret` 创建时生成（32 位 hex），随任务详情（get）返回，仅归属会员可查；
- 连接超时 5s/读取超时 10s，响应 2xx 即成功；失败自动重试 3 次（间隔 1/5/30 分钟）；
- `GET /app-api/appgo/dev-app/webhook-logs?id={id}` 查询投递记录
  （event/status/statusCode/retryCount/failReason/createTime，新→旧）；
  CLI：`python appgo.py webhook-logs --id 123`；
- 未配置 callbackUrl 的任务零回调，与既往行为一致。

## 任务对象字段（节选）

```json
{
  "id": 123,
  "appName": "喝水提醒",
  "packageName": "com.appgo.u1.tabs34",
  "appType": "效率工具",
  "devStatus": 3,
  "billingStatus": 0,
  "credits": 0,
  "complexityTier": "标准",
  "quotedCredits": 990,
  "firstOrderDiscount": 500,
  "priceQuote": "{\"tier\":\"标准\",\"credits\":990,\"firstOrderDiscount\":500,\"server_signals\":[…]}",
  "callbackUrl": "http://127.0.0.1:9000/appgo-hook",
  "webhookSecret": "a3f…（32 位 hex，仅归属会员可查）",
  "apkUrl": "https://…", "sourceUrl": "https://…", "qcReportUrl": "https://…",
  "failReason": null,
  "createTime": "2026-10-08 12:00:00"
}
```

`priceQuote` 为 JSON 字符串，含档位、Credits、首单优惠、支付路由与
`server_signals`（服务端能力覆盖信号：`covered=false` 的组表示平台暂未覆盖，
可简化需求或联系客服定制后端）。

## curl 示例

```bash
export APPGO_API_KEY=agku_xxx

# 创建任务
curl -s -X POST https://www.letwx.net/app-api/appgo/dev-app/create \
  -H "X-API-Key: $APPGO_API_KEY" -H "tenant-id: 1" -H "Content-Type: application/json" \
  -d '{"appName":"喝水提醒","codePrompt":"记录每日饮水量并生成周统计图表，目标用户为健身人群"}'

# 轮询任务
curl -s "https://www.letwx.net/app-api/appgo/dev-app/get?id=123" \
  -H "X-API-Key: $APPGO_API_KEY" -H "tenant-id: 1"

# 确认报价（冻结 Credits）
curl -s -X POST https://www.letwx.net/app-api/appgo/dev-app/confirm \
  -H "X-API-Key: $APPGO_API_KEY" -H "tenant-id: 1" -H "Content-Type: application/json" \
  -d '{"id":123}'

# 下载源码（跟随重定向）
curl -sL -o source.zip "https://www.letwx.net/app-api/appgo/dev-app/source-download?id=123" \
  -H "X-API-Key: $APPGO_API_KEY" -H "tenant-id: 1"
```

## 错误码（业务码段 1-010-014-x）

| code | 含义 |
|------|------|
| 1010001000 | 任务不存在（含无权访问他人任务） |
| 1010001001 | 包名已存在任务 |
| 1010001003 | 当前状态不允许确认（仅待确认可确认） |
| 1010001005 | 报价缺失，请等待流水线回写后再确认 |
| 1010002001 | Credits 余额不足（msg 含需要额与余额） |
| 1010014002 | 需求描述包含平台不支持的内容（关键词审核拦截） |
| 1010014003 | 进行中任务数已达上限（3 个） |
| 1010014004 | 今日创建任务数已达上限（10 个） |
| 1010014000 | API 密钥不存在 |
| 1010014001 | 启用中 API 密钥已达上限（5 个） |
