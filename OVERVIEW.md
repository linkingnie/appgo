# AppGo Skill — 让 coding agent 成为 APP 开发代理商

> **一句话定位**：agent 出脑力（理解需求、编排流程、验收取货），AppGo 出产能
> （AI 流水线生成、构建、质检、交付）。安装一个 skill，你的 coding agent 就多了一项
> 「生成完整 Android APP」的能力——不写一行代码，10~30 分钟拿到 APK + 完整 Gradle 源码。

适用：Qoder / Claude Code / Kiro / 任何能跑命令的 agent 或终端。

---

## 为什么不是「让 agent 直接从零写一个」？

直接让 coding agent 开发 Android APP，你实际面对的是：

| 隐性成本 | 直接 agent 开发 | AppGo Skill |
|---|---|---|
| **环境门槛** | Android SDK、Gradle、JDK、签名、真机调试，一套配下来半天起步 | **零**。agent 侧只需 Python 3.8+（CLI 零第三方依赖） |
| **金钱成本** | Token 消耗**不可预估**：Android 工程文件多，构建报错循环最烧 token，中途失败只能重来 | **报价前置锁定**：先看报价单再决定，确认才扣费，失败**全额自动退款** |
| **人力时间** | 人在环路盯构建、修报错、装包验证，数小时到数天 | 写清楚需求 10 分钟，`wait` 或 Webhook 等通知，期间 agent 可以干别的 |
| **交付物** | 一堆代码，「能不能跑通看运气」 | 构建通过的 **APK + 完整 Gradle 工程 + 质检报告 + 真机安装截图** |
| **失败兜底** | 跑不通就是沉没成本 | 生成失败 Credits **全额退回**，可调整需求重新提交 |
| **迭代计价** | 每轮改动都在烧会话 token，改到一半预算失控 | `iterate-quote` **先看本轮价格**再决定，常见迭代 ¥10~50/轮 |

**核心区别**：coding agent 是「开发工具」，产出质量与成本取决于你的提示工程水平和运气；
AppGo Skill 是「开发代理商」，把生产交给平台流水线——品类模板、UI 生成、构建、质检、
截图一条龙，**多少钱、多久、拿到什么，提交前全部明码标价**。

---

## 六大优势

### 1. 环境零门槛
不需要 Android SDK / Gradle / 签名 / 真机。agent 侧是一个零依赖的单文件 Python CLI，
交付物直接是安装包 + 源码。手机上装一下就能看到真实运行效果。

### 2. 成本前置锁定，绝不盲扣
```
submit（免费创建）→ 报价单（档位/Credits 明细）→ 你确认 → 冻结 Credits → 开始生成
```
**报价确认永远需要你本人点头**，skill 绝不自动扣费。迭代同理：`iterate-quote` 先出
本轮报价预览，确认后才发起。对比直接开发「token 烧到哪算哪」，预算从第一秒就锁定。

### 3. 分钟级异步交付 + Webhook 主动通知
生成 10~30 分钟异步完成，agent 无需阻塞等待：
- 轮询模式：`wait --for done` 挂起等待
- 推送模式：创建时传 `callbackUrl`，报价就绪/生成完成/生成失败事件**主动 POST** 到你的服务，
  HMAC-SHA256 签名防伪造（附 Python 验签示例），失败自动按 1/5/30 分钟重试 3 次

### 4. 交付确定性有兜底
- 每个应用独立生成代码与构建，**不是网页套壳**；源码可导出、可自行二次开发
- 交付物含 APK、完整 Gradle 工程、质检报告、真机截图（保留 3 天，可购托管延长）
- 生成失败（状态 2）Credits 全额自动退回
- 失败可 `retry`（按原冻结额重跑）、需求想清楚了可 `redesign` 回炉重新报价——
  失败和变更有**标准恢复动作**，不是「重新聊一遍」

### 5. 完整生命周期 CLI，全部 `--json` 可消费
主流程 + 迭代 + 失败恢复 + Webhook 日志查询，一条命令一个动作：

```bash
python scripts/appgo.py submit --name "喝水提醒" --prompt "记录每日饮水量并生成周统计图表"
python scripts/appgo.py confirm --id 123            # 展示报价，确认扣费
python scripts/appgo.py wait --id 123 --for done    # 等待生成完成
python scripts/appgo.py download --id 123 --out ./my-app   # 源码落地本地
python scripts/appgo.py iterate-quote --id 123 --add "加夜间模式"   # 迭代先看价
python scripts/appgo.py iterate --id 123 --add "加夜间模式"          # 确认后发起迭代
python scripts/appgo.py retry --id 123              # 失败按原价重试
python scripts/appgo.py redesign --id 123 --prompt "简化后的需求"    # 回炉重新报价
python scripts/appgo.py submit --name "记账" --prompt "..." --h5-zip ./原型.zip  # 带 Figma H5 原型提交（可选）
python scripts/appgo.py webhook-logs --id 123       # 查回调投递记录
```

### 6. 跨 agent 通用，源码真正属于你
Qoder 放 `.qoder/skills/`、Claude Code 放 `.claude/skills/`、Kiro 走 steering 约定，
或者不装 skill 直接命令行用。源码导出后与平台再无绑定，本地想怎么改就怎么改。

---

## 什么时候选 AppGo Skill，什么时候直接写？

**适合 AppGo Skill**：
- 不会开发 / 不想配 Android 环境的人，想把想法快速变成可安装的 APP
- 产品经理/设计师：有现成 Figma 导出的 H5 原型，`--h5-zip` 随任务提交即可按原型还原成 APP
- 批量生产工具类应用（矩阵 APP、外包接单量产），单均成本与周期远优于逐个人工开发
- agent 用户想把「生成 APP」外包成一次工具调用，自己专注上层编排
- 需要交付确定性：报价锁定、失败全退、质检报告

**适合直接用 coding agent**：
- 深度服务端集成、复杂业务逻辑（平台报价单会标注「超纲」，转定制评估）
- 已有源码的小改动——直接改代码比走一轮迭代更快更省
- 对代码架构有强控制诉求、且自己具备 Android 工程能力的开发者

---

## 成本一览

| 项目 | 价格 | 说明 |
|---|---|---|
| 创建任务 | **免费** | 提交需求 + 拿报价，不花钱 |
| 简单档生成 | ¥99（990 Credits） | ≤5 页纯工具类 |
| 标准档 | ¥299 | 6~12 页 |
| 高级档 | ¥499 | >12 页 |
| 旗舰档 | ¥999 | 高复杂度 |
| 迭代 | ¥9.9/复杂度分起 | 常见一轮 ¥10~50，`iterate-quote` 先看价 |
| 生成失败 | **全额自动退款** | — |

- 首单有折扣（以报价单实际展示为准）；API 与网站同价，Credits 通用
- 充值与密钥管理在 [AppGo 控制台](https://www.letwx.net)完成

---

## 60 秒上手

```bash
# 1. 控制台生成 API Key（agku_ 开头，仅展示一次）
export APPGO_API_KEY=agku_你的密钥

# 2. 提交需求，等报价
python scripts/appgo.py submit --name "待办事项" --prompt "待办事项管理，要有番茄钟和周统计"

# 3. 确认报价 → 等待 → 下载源码
python scripts/appgo.py confirm --id 123
python scripts/appgo.py wait --id 123 --for done
python scripts/appgo.py download --id 123 --out ./my-app
```

完整安装（Qoder / Claude Code / Kiro）见 [README](./README.md#安装)；
agent 侧工作流指令见 [SKILL.md](./SKILL.md)；完整 REST 契约（可绕过 skill 直接集成）见 [API.md](./API.md)。

---

## 文档导航

| 文档 | 用途 |
|---|---|
| [OVERVIEW.md](./OVERVIEW.md) | 本页：定位、优势、成本对比 |
| [README.md](./README.md) | 安装、快速开始、计费与风控规则 |
| [SKILL.md](./SKILL.md) | agent 工作流指令（五步主流程 + 迭代/失败/需求变更场景 + Webhook） |
| [API.md](./API.md) | 完整 REST API 契约（含 HMAC 验签示例） |

---

AppGo 平台：[www.letwx.net](https://www.letwx.net) ｜ License: [MIT](./LICENSE)
