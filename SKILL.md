---
name: appgo-app-generator
description: >
  用 AppGo 服务端 AI 流水线生成完整的 Android APP 并把源码下载到本地二次开发。
  当用户想要「生成一个 Android APP」「帮我做一个安卓应用」「生成 APK」「做个手机应用」，
  且愿意用 AI 生成 + 本地改代码的工作流时使用。需要 APPGO_API_KEY（在 appgo 控制台生成，
  充值与计费在 AppGo 网站完成，与网站 Credits 同价通用）。
license: MIT
allowed-tools: ["Bash", "Read", "Write"]
---

# AppGo APP 生成器

你将作为用户与 AppGo 生成服务之间的编排者：澄清需求 → 提交任务 → 展示报价并
**等用户确认** → 等待生成 → 下载源码到本地 → 引导二次开发。

**铁律（违反任意一条即失败）：**
1. **绝不 auto-confirm**：调用 `confirm` 之前，必须把报价单（档位/Credits/是否首单优惠/未覆盖能力）
   完整展示给用户，并得到用户对价格的明确同意。未同意就确认 = 未经授权扣费。
2. 需求描述至少 10 个字；描述越具体，报价与生成质量越好。
3. 生成失败（状态 2）时告知用户 Credits 已全额自动退回。
4. 源码一经导出不再退款；用户本地修改后的代码不在平台免费修复窗口内——在下载环节告知用户。

## 前置检查（每次会话第一步）

1. 读取环境变量 `APPGO_API_KEY`。
2. 若未设置，**停止并引导用户**：
   - 打开 AppGo 控制台 https://www.letwx.net （登录后进入控制台 →「API 接入」→ 生成 API Key）；
   - 复制 `agku_` 开头的完整密钥（仅展示一次）；
   - 让用户在终端设置：`export APPGO_API_KEY=agku_xxx`（Windows PowerShell：`$env:APPGO_API_KEY="agku_xxx"`），
     或写入 shell 配置文件；然后重试。
3. 确认脚本路径：本 skill 目录下 `scripts/appgo.py`（下称 CLI）。

## 工作流

### 第 1 步：澄清需求
与用户对话明确：应用名称（≤20 字）、核心功能列表、目标用户、界面风格偏好（可选）。
把它们整合成一段 10~2000 字的功能描述（写入 --prompt）。需求不明确时先追问，不要臆测。
用户手上有 Figma 导出的 H5 原型或设计稿打包的 zip 时，主动走「场景 D」的原型模式。

### 第 2 步：提交任务（免费）
```bash
python scripts/appgo.py submit --name "应用名" --prompt "功能描述" [--style "简约蓝"] [--type "品类"] [--h5-zip ./原型.zip]
```
记住返回的任务编号 `--id`。创建不产生任何费用。

### 第 3 步：等待报价 → 展示 → 等用户确认（关键）
```bash
python scripts/appgo.py wait --id <ID> --for quote --timeout 600
```
评估通常几分钟。CLI 会打印报价单摘要；**把报价单完整转述给用户**（档位、标准 Credits、
首单优惠、确认冻结额、未覆盖的服务端能力提示），并说明：
- Credits 在确认时冻结、生成成功后核销、失败全额退回；
- 平台未覆盖的服务端能力（如有）可以简化需求，或联系客服定制后端。
**得到用户明确同意后**再执行：
```bash
python scripts/appgo.py confirm --id <ID> --yes
```
用户不同意时：可调整需求后重新 `submit`（未确认的任务不产生费用）。

### 第 4 步：等待生成完成
```bash
python scripts/appgo.py wait --id <ID> --for done --timeout 3600
```
生成耗时约 10~30 分钟，期间可向用户说明进度。状态 2（失败）时告知 Credits 已全额退回，
可修改需求重新提交。

### 第 5 步：下载源码并引导二次开发
```bash
python scripts/appgo.py download --id <ID> --out <目标目录>
```
下载要求：账户已充值过（体验用户导出源码前需充值）；交付文件保留 3 天，超期需购托管服务。
完成后向用户报告：
- 解压目录与工程结构（Gradle 多模块 Android 工程，可直接 Android Studio 打开）；
- 质检报告与截图链接（`get --json` 输出中的 qcReportUrl/screenshots）；
- 引导用户开始二次开发（改 UI 文案、加页面、接自己的后端等）——这正是本地 agent 擅长的部分；
- 提醒：源码已导出不再退款；本地修改后的问题不在免费修复范围内；后续继续优化可用本 skill 的「迭代优化」工作流（见下文）。

## 场景工作流

### 场景 A：迭代优化（用户对已完成的应用提出修改）
已完成任务（状态 1）可继续迭代，流程与首次生成同构——**先报价、经用户确认、再执行**：
```bash
# ① 预览本轮报价（不产生计费/状态变更）
python scripts/appgo.py iterate-quote --id <ID> --add "本轮迭代需求"
# ② 把本轮报价（打分/档位/本轮 Credits/余额）完整展示给用户并得到明确同意
# ③ 用户同意后发起迭代（带上报价返回的 Credits 防预览与实扣不一致）
python scripts/appgo.py iterate --id <ID> --add "本轮迭代需求" --expected-credits <报价Credits>
# ④ 等待迭代完成
python scripts/appgo.py wait --id <ID> --for done --timeout 3600
```
铁律 1 同样适用：未经用户同意就 `iterate` = 未经授权扣费。报价返回 `overLimit=true`
（旗舰档 ≥14 分）时平台会拒绝执行，引导用户作为新应用重新 `submit`。

### 场景 B：生成失败（状态 2）
1. 告知用户 Credits 已全额自动退回，展示失败原因（`get --json` 的 failReason）。
2. 失败多为暂时性（流水线/资源问题）且需求无需调整时，可重新生成（按原确认冻结额）：
   ```bash
   python scripts/appgo.py retry --id <ID>
   python scripts/appgo.py wait --id <ID> --for done --timeout 3600
   ```
3. 需求本身可能过重/不合理时，引导用户简化需求后重新报价：
   ```bash
   python scripts/appgo.py redesign --id <ID> --prompt "简化后的功能描述"
   python scripts/appgo.py wait --id <ID> --for quote --timeout 600
   ```
   出新报价后回到「第 3 步」展示并等用户确认。

### 场景 C：需求变更（报价确认前想改需求）
仅待确认（状态 3）且非迭代任务可用：`redesign` 会清空原报价快照、退回原确认冻结额，
回到待开发重新评估（首单折扣按最新资格重新判定）。出具新报价后向用户展示并等确认。

### 场景 D：已有 UI 原型（Figma/H5 导出 zip）
用户有可点击 H5 原型或设计稿打包的 zip（≤50MB）时随任务一并提交，生成时 UI 以原型为
第一依据（页面结构、图标、配色按原型还原，SVG 图标自动转 Android drawable）：
```bash
python scripts/appgo.py submit --name "应用名" --prompt "功能描述" --h5-zip ./原型.zip
```
- `--h5-zip` 会先自动上传再随任务提交；已有托管 URL 时改用 `--h5-zip-url`（或先 `upload` 拿 URL）；
- zip 建议含 `PRODUCT_SPECS.md`（应用名/包名/功能需求）与 `figma_prototype/`（页面 HTML + icons/）
  目录；结构不完整时平台自动降级为纯描述模式，任务不会因此失败；
- 原型不改变计费与流程：仍走报价 → 用户确认 → 生成（铁律 1 不变）；
- 原型内容需自行确保合规；原型包与任务描述一同提交后即受平台风控约束。

## Webhook 回调（可选）
创建任务时传 `--callback-url`（http/https），任务状态变更（报价已出/生成完成/生成失败）
时平台会向该地址 POST JSON 回调，适合长期运行的 agent 做事件驱动而免轮询：
```bash
python scripts/appgo.py submit --name "应用名" --prompt "功能描述" --callback-url "http://127.0.0.1:9000/appgo-hook"
```
- 回调 Header：`X-AppGo-Event`（事件名）/ `X-AppGo-Delivery` / `X-AppGo-Timestamp` /
  `X-AppGo-Signature: sha256=<HMAC-SHA256(webhookSecret, timestamp + "." + body)>`；
- `webhookSecret` 在任务详情（`get --json`）中可查，仅归属会员可见；验签示例见 `API.md`；
- 投递失败自动重试（3 次，间隔 1/5/30 分钟）；`webhook-logs --id <ID>` 可查投递记录。
未配置 callbackUrl 的任务零回调，与既往行为一致。

## 错误处理
- `API Key 无效（401）`：让用户检查环境变量、确认密钥未吊销（控制台列表）。
- `业务错误 code=xxx`：把 msg 原文转述给用户（含内容安全拦截、任务数上限等）。
- `等待超时`：任务可能仍在生成，稍后重试 `wait` 或用 `get` 查看状态，不要重复 submit。
- `402 需充值`：引导用户到 https://www.letwx.net 充值后重试 download。
- 网络错误：检查网络与 APPGO_BASE_URL 配置。

## 参考
- 完整 API 契约（含 iterate/retry/redesign 等进阶端点）：本目录 `API.md`
- 项目主页与文档：https://www.letwx.net
