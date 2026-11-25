# AppGo Skill — Generate an Android app inside your local coding agent

**English** | [简体中文](README.zh-CN.md)

Build a complete Android app through conversation in coding agents such as Qoder / Claude Code / Kiro,
then **download the source code locally** for further development. Generation is done by the AppGo
server-side AI pipeline (category templates, UI generation, build, QA, screenshots — end to end).
Top-ups and billing happen on the [AppGo website](https://www.letwx.net); API pricing matches the
website (Credits are shared).

> Why use AppGo Skill instead of letting the agent write everything from scratch? See
> [OVERVIEW.md](./OVERVIEW.md) (positioning, advantages, cost comparison).

## What it does

```
You (chat)                    AppGo server                    You (local)
────────                      ────────────────                ────────
describe requirements ── submit ──→ complexity scoring + quote
wait a few minutes   ←─ status 3 ── quote (tier / Credits)
confirm the quote    ── confirm ──→ freeze Credits, AI pipeline starts
wait 10–30 minutes   ←─ status 4 ── UI/code → build APK → QA + screenshots
download ─────────────────────────→ source ZIP (internal credentials stripped)
local development    ←─ unzip ───── complete Gradle project
```

- Failed generations are refunded in full automatically; no refund once the source has been exported
- Deliverables include APK, source code, QA report and screenshots (kept for 3 days; hosting can be purchased to extend)
- A finished app can be improved in place (iterate-quote → confirm → iterate); retry on failure, redesign when requirements change
- Tasks can pass a Webhook callback (`callbackUrl`): quote / completion / failure events are pushed proactively and signed against forgery
- H5/UI prototype zip (Figma export) is supported: `submit --h5-zip` uploads it with the task; when a prototype can be parsed, UI follows it first and falls back to description-only mode otherwise

## Installation

API key first: sign in to the [AppGo console](https://www.letwx.net) → "API Access" → create an API Key
(starts with `agku_`, shown only once), then:

```bash
export APPGO_API_KEY=agku_your_key          # Windows PowerShell: $env:APPGO_API_KEY="agku_your_key"
```

### Qoder

Put this directory under your project's `.qoder/skills/` (or the global skills directory); Qoder
loads SKILL.md automatically. Say "build me an expense tracker app" in chat to trigger it.

### Claude Code

```bash
# project level
mkdir -p .claude/skills && cp -r /path/to/appgo-skill .claude/skills/appgo-app-generator
# or user level
cp -r /path/to/appgo-skill ~/.claude/skills/appgo-app-generator
```

### Kiro

Put the content of SKILL.md into `.kiro/steering/appgo-app-generator.md` following Kiro's steering
convention, or simply let the agent read SKILL.md and follow its workflow.

### Manual (any terminal)

No skill needed — the CLI is a complete tool on its own:

```bash
python scripts/appgo.py submit --name "Water reminder" --prompt "Track daily water intake and draw a weekly chart"
python scripts/appgo.py submit --name "Expense tracker" --prompt "..." --h5-zip ./prototype.zip  # submit with an H5/UI prototype (optional)
python scripts/appgo.py upload ./prototype.zip                                                   # upload a prototype only and get its URL
python scripts/appgo.py wait --id 123 --for quote
python scripts/appgo.py confirm --id 123        # show the quote and confirm
python scripts/appgo.py wait --id 123 --for done
python scripts/appgo.py download --id 123 --out ./my-app
python scripts/appgo.py iterate-quote --id 123 --add "add dark mode"   # preview an iteration quote
python scripts/appgo.py iterate --id 123 --add "add dark mode"         # start the iteration after confirmation
```

Requires Python 3.8+; no third-party dependencies.

## Quick start (agent conversation)

> User: build me a todo app with a pomodoro timer.
>
> Agent: confirm the requirements (name / features / style) → `submit` → present the quote:
> "Standard tier 990 Credits, first-order discount 500, 490 Credits frozen on confirmation (≈ ¥49),
> fully refunded if generation fails"
> → user confirms → `confirm` → `wait` → `download` → source lands in `./todo-app/`,
> then guide local development.

## Billing and safeguards

| Item | Rule |
|------|------|
| Create a task | Free |
| Confirm the quote | Credits are frozen (captured on success, refunded in full on failure) |
| Export the source | Account must be topped up; no refund after export |
| Deliverable retention | 3 days (code hosting can be purchased to extend) |
| Content safety | Requirement text is moderated by keywords; violations are rejected |
| Rate limits | ≤ 3 in progress, ≤ 10 created per day, ≤ 5 API keys |

**Quote confirmation always requires your explicit approval** — the skill shows the quote and waits
for your go-ahead; it never charges automatically.

## SLA boundaries

- Server-generated artifacts are judged by the **QA report**; code you modify locally is outside the free-fix window
- A failed generation (status 2) refunds Credits in full; adjust the requirements and resubmit
- If a heavy capability (backend, account system, etc.) is not covered by the platform, the quote
  states so; you can simplify the requirements or contact support for a custom build

## Development

- `scripts/appgo.py`: single-file CLI (Python standard library only); `--json` output for agent
  consumption. Covers the main flow (submit/wait/confirm/download), iteration and failure recovery
  (iterate-quote/iterate/retry/redesign), webhook delivery logs (webhook-logs) and H5/UI prototype
  upload (upload, or submit --h5-zip)
- `API.md`: the full REST contract (iteration / failure recovery / webhook signature verification),
  usable without the skill
- `SKILL.md`: cross-agent workflow instructions (iteration / failure / requirement change / H5
  prototype scenarios plus webhooks)

## Version

- **v2 (Open API phase 2)**: the CLI main workflow covers iteration, retry and re-quote; adds Webhook
  callbacks (`callbackUrl` + HMAC-SHA256 verification + retries + webhook-logs); the server adds LLM
  semantic moderation (fail-open) and an admin API-key management page
- **v1 (Open API phase 1)**: API Key auth, submit/quote/confirm/generate/download main flow,
  keyword content moderation

## Docs language

`SKILL.md`, `API.md` and `OVERVIEW.md` are currently written in Chinese; an English edition is
planned. The REST contract in `API.md` is language-neutral and can be used as is.

## Publishing to GitHub

```bash
cd appgo-skill
git init && git add -A && git commit -m "feat: AppGo open API skill v2 (iterate/retry/redesign + webhook)"
git remote add origin git@github.com:<you>/appgo-skill.git
git push -u origin main        # replace badges/links with your own repository address as needed
```

## License

[MIT](./LICENSE)
