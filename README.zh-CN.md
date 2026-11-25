# AppGo Skill — 在本地 coding agent 中生成 Android APP

[English](README.md) | **简体中文**

在 Qoder / Claude Code / Kiro 等 coding agent 里，通过对话生成完整的 Android APP，
并把**源码下载到本地**二次开发。生成由 AppGo 服务端 AI 流水线完成（品类模板、
UI 生成、构建、质检、截图一条龙），充值与计费在 [AppGo 网站](https://www.letwx.net)
完成，API 与网站同价（Credits 通用）。

> 为什么选 AppGo Skill 而不是让 agent 直接从零写？见 [OVERVIEW.md](./OVERVIEW.md)
> （定位、优势与成本对比）。

## 它能做什么

```
你（对话）                      AppGo 服务端                     你（本地）
────────                      ─────────────                   ────────
描述需求 ──── submit ────→ 复杂度评估 + 报价
等待几分钟  ←─ 状态 3 ─────  报价单（档位/Credits）
确认报价 ──── confirm ──→   冻结 Credits，AI 流水线启动
等待 10~30 分钟 ←─ 状态 4 ──  生成 UI/代码 → 构建 APK → 质检截图
download ────────────────→  源码 ZIP（已剥离内部凭据）
本地二次开发 ←─ 解压 ──────   完整 Gradle 工程
```

- 生成失败全额自动退款；源码导出后不再退款
- 交付物含 APK、源码、质检报告、截图（保留 3 天，可购托管延长）
- 已完成的 APP 可直接在本地继续「迭代优化」（iterate-quote → 确认 → iterate），失败可 retry、改需求可 redesign
- 创建任务可传 Webhook 回调（callbackUrl），报价/完成/失败事件主动推送，验签防伪造
- 支持 H5/UI 原型 zip（Figma 导出）：`submit --h5-zip` 自动上传随任务提交，生成时 UI 以原型为第一依据，无法解析时自动降级纯描述模式

## 安装

密钥先行：登录 [AppGo 控制台](https://www.letwx.net) →「API 接入」→ 生成 API Key
（`agku_` 开头，仅展示一次），然后：

```bash
export APPGO_API_KEY=agku_你的密钥          # Windows PowerShell: $env:APPGO_API_KEY="agku_你的密钥"
```

### Qoder

将本目录放入项目的 `.qoder/skills/`（或全局 skills 目录），Qoder 会自动加载
SKILL.md；对话中说「帮我生成一个记账 APP」即可触发。

### Claude Code

```bash
# 项目级
mkdir -p .claude/skills && cp -r /path/to/appgo-skill .claude/skills/appgo-app-generator
# 或用户级
cp -r /path/to/appgo-skill ~/.claude/skills/appgo-app-generator
```

### Kiro

将 SKILL.md 内容按 Kiro steering 约定放入 `.kiro/steering/appgo-app-generator.md`，
或直接让 agent 阅读 SKILL.md 后按其工作流执行。

### 手动（任何终端）

不装 skill 也能用，CLI 本身就是完整工具：

```bash
python scripts/appgo.py submit --name "喝水提醒" --prompt "记录每日饮水量并生成周统计图表"
python scripts/appgo.py submit --name "记账" --prompt "..." --h5-zip ./原型.zip  # 带 H5/UI 原型提交（可选）
python scripts/appgo.py upload ./原型.zip                                      # 仅上传原型拿 URL
python scripts/appgo.py wait --id 123 --for quote
python scripts/appgo.py confirm --id 123        # 展示报价并确认
python scripts/appgo.py wait --id 123 --for done
python scripts/appgo.py download --id 123 --out ./my-app
python scripts/appgo.py iterate-quote --id 123 --add "加夜间模式"   # 迭代报价预览
python scripts/appgo.py iterate --id 123 --add "加夜间模式"         # 确认后发起迭代
```

要求 Python 3.8+，无第三方依赖。

## 快速开始（agent 对话示例）

> 用户：帮我生成一个待办事项 APP，要有番茄钟。
>
> Agent：先确认需求（名称/功能/风格）→ `submit` → 展示报价单：
> 「标准档 990 Credits，首单优惠 500，确认冻结 490 Credits（约 ¥49），失败全额退回」
> → 用户确认 → `confirm` → `wait` → `download` → 源码落地 `./待办事项/`，
> 引导本地继续开发。

## 计费与风控

| 项目 | 规则 |
|------|------|
| 创建任务 | 免费 |
| 确认报价 | 冻结 Credits（生成成功核销，失败全额退回） |
| 源码导出 | 需账户已充值；导出后不再退款 |
| 交付保留 | 3 天（可购代码托管服务延长） |
| 内容安全 | 需求描述关键词审核，违规拒绝 |
| 任务限流 | 进行中 ≤ 3，每日创建 ≤ 10，API Key ≤ 5 |

**报价确认永远需要你本人的明确同意**——skill 会先展示报价单等你点头，绝不自动扣费。

## SLA 边界

- 服务端生成产物以**质检报告**为准；你本地修改后的代码不在免费修复窗口内
- 生成失败（状态 2）Credits 全额退回，可调整需求重新提交
- 后端/账号体系等重能力若平台未覆盖，报价单会标注，可简化需求或联系客服定制

## 开发

- `scripts/appgo.py`：单文件 CLI（Python 标准库 only），`--json` 输出供 agent 消费；
  覆盖主流程（submit/wait/confirm/download）+ 迭代与失败恢复（iterate-quote/iterate/retry/redesign）
  + Webhook 投递记录查询（webhook-logs）+ H5/UI 原型上传（upload，或 submit --h5-zip 自动上传）
- `API.md`：完整 REST 契约（含迭代/失败恢复/Webhook 回调验签），可绕过 skill 直接集成
- `SKILL.md`：跨 agent 的工作流指令（含迭代/失败/需求变更/H5 原型四段场景 + Webhook 段落）

## 版本

- **v2（开放 API 二期）**：CLI 主工作流覆盖迭代优化/重试/重报价；新增 Webhook 回调
  （callbackUrl + HMAC-SHA256 验签 + 失败重试 + webhook-logs）；服务端新增 LLM 语义审核增强（fail-open）
  与管理端 API 密钥管理页
- **v1（开放 API 一期）**：API Key 鉴权、提交/报价/确认/生成/下载主流程、关键词内容审核

## 文档语言

`SKILL.md`、`API.md`、`OVERVIEW.md` 目前为中文；英文版在计划中。`API.md` 的 REST 契约与语言无关，可直接使用。

## 发布到 GitHub

```bash
cd appgo-skill
git init && git add -A && git commit -m "feat: AppGo open API skill v2 (iterate/retry/redesign + webhook)"
git remote add origin git@github.com:<you>/appgo-skill.git
git push -u origin main        # README 顶部徽章/链接按需替换为你的仓库地址
```

## License

[MIT](./LICENSE)
