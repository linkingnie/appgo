#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AppGo Open API CLI（开源 skill 配套脚本）

用 AppGo 的 API Key 在任意 coding agent（Qoder / Claude Code / Kiro 等）中
以「提交需求 → 确认报价 → 轮询生成 → 下载源码」的方式生成 Android APP，
源码下载到本地后即可二次开发。

仅依赖 Python 3.8+ 标准库，无第三方包。

配置（环境变量）：
  APPGO_API_KEY    必填，在 AppGo 控制台「API 接入」生成（agku_ 开头）
  APPGO_BASE_URL   可选，默认 https://www.letwx.net
  APPGO_TENANT_ID  可选，默认 1（平台租户，保持默认即可）

用法示例：
  export APPGO_API_KEY=agku_xxxx
  python appgo.py submit --name "喝水提醒" --prompt "一个记录每日饮水量的 APP，含统计图表"
  python appgo.py wait --id 123 --for quote      # 等报价（状态 3）
  python appgo.py confirm --id 123               # 确认报价并冻结 Credits（agent 必须先向用户展示报价）
  python appgo.py wait --id 123 --for done       # 等生成完成（状态 1 或 2）
  python appgo.py download --id 123 --out ./my-app   # 下载并解压源码

迭代优化（已完成的任务继续改需求）：
  python appgo.py iterate-quote --id 123 --add "首页背景改蓝色"   # 迭代报价预览（agent 必须先向用户展示）
  python appgo.py iterate --id 123 --add "首页背景改蓝色"          # 用户确认后发起迭代
  python appgo.py retry --id 123                                  # 失败任务重新生成（按原冻结额）
  python appgo.py redesign --id 123 --prompt "简化后的需求"        # 需求变更：简化后重新报价
  python appgo.py webhook-logs --id 123                           # 查 Webhook 投递记录

H5/UI 原型（有 Figma 导出 H5 原型或设计稿 zip 时）：
  python appgo.py submit --name "记账" --prompt "..." --h5-zip ./原型.zip   # 自动上传随任务提交（推荐）
  python appgo.py upload ./原型.zip                                        # 仅上传拿 URL（高级用法）
"""

import argparse
import json
import os
import sys
import time
import uuid
import zipfile

try:
    from urllib import error as urlerror
    from urllib import request as urlrequest
except ImportError:  # pragma: no cover
    sys.stderr.write("需要 Python 3.x\n")
    sys.exit(2)

API_KEY = os.environ.get("APPGO_API_KEY", "").strip()
BASE_URL = os.environ.get("APPGO_BASE_URL", "https://www.letwx.net").strip().rstrip("/")
TENANT_ID = os.environ.get("APPGO_TENANT_ID", "1").strip()

# 开发状态机：与 API.md 的状态表一致
STATUS_TEXT = {
    0: "待开发（复杂度评估中）",
    3: "待确认（报价已出，等待确认设计）",
    4: "生成中（已确认报价，AI 生成运行中）",
    1: "已完成（可下载源码/APK）",
    2: "失败（Credits 已全额退回）",
}

TERMINAL_DONE = (1, 2)

# Webhook 事件与投递状态文本（与 API.md 事件表一致）
EVENT_TEXT = {"quote_ready": "报价已出", "completed": "生成完成", "failed": "生成失败"}
WEBHOOK_STATUS_TEXT = {0: "待投递", 1: "成功", 2: "失败"}


class ApiError(Exception):
    """API 调用失败（HTTP 或业务码）"""


def _ensure_key():
    if not API_KEY:
        raise ApiError(
            "未配置 APPGO_API_KEY。请在 AppGo 控制台（%s）「API 接入」生成 API Key 后：\n"
            "  export APPGO_API_KEY=agku_你的密钥" % BASE_URL
        )


def _read_result(req, timeout):
    """发送请求并解析 CommonResult，返回 data 字段；错误处理与业务码判定全端共用"""
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as e:
        detail = ""
        try:
            payload = json.loads(e.read().decode("utf-8"))
            detail = payload.get("msg") or ""
        except Exception:
            pass
        if e.code == 401:
            raise ApiError("API Key 无效或已吊销（401）：%s" % detail)
        if e.code == 402:
            raise ApiError("体验用户需先充值后才能导出源码（402），请在 AppGo 网站充值")
        if e.code == 403:
            raise ApiError("交付文件已超保留期（3 天），购买代码托管服务后可继续下载（403）")
        if e.code == 404:
            raise ApiError("资源不存在或无权访问（404）")
        raise ApiError("HTTP %s %s" % (e.code, detail))
    except urlerror.URLError as e:
        raise ApiError("无法连接 AppGo 服务（%s）：%s" % (BASE_URL, e.reason))
    if payload.get("code") != 0:
        raise ApiError("API 业务错误（code=%s）：%s" % (payload.get("code"), payload.get("msg")))
    return payload.get("data")


def http_json(method, path, body=None, timeout=60):
    """调用开放 API 并返回 data 字段；业务码非 0 抛 ApiError"""
    _ensure_key()
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urlrequest.Request(url, data=data, method=method)
    req.add_header("X-API-Key", API_KEY)
    req.add_header("tenant-id", TENANT_ID)
    req.add_header("Content-Type", "application/json")
    return _read_result(req, timeout)


def http_upload(path, file_path, timeout=300):
    """multipart/form-data 上传本地文件（零依赖手工编码），返回 data 字段

    平台侧仅接受 .zip 且 ≤50MB（与流水线下载校验上限一致），此处先行校验省一次往返。
    """
    _ensure_key()
    if not os.path.exists(file_path):
        raise ApiError("文件不存在：%s" % file_path)
    size = os.path.getsize(file_path)
    if size > 50 * 1024 * 1024:
        raise ApiError("文件超过 50MB 上限（当前 %.1f MB），请压缩原型资源后再试" % (size / 1024.0 / 1024.0))
    fname = os.path.basename(file_path)
    if not fname.lower().endswith(".zip"):
        raise ApiError("仅支持 .zip 文件：%s" % fname)
    boundary = "----AppGoForm%s" % uuid.uuid4().hex
    with open(file_path, "rb") as f:
        content = f.read()
    safe_fname = fname.replace('"', "").replace("\\", "_")
    body = b"".join([
        ("--%s\r\n" % boundary).encode("ascii"),
        ('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % safe_fname).encode("utf-8"),
        b"Content-Type: application/zip\r\n\r\n",
        content,
        ("\r\n--%s--\r\n" % boundary).encode("ascii"),
    ])
    req = urlrequest.Request(BASE_URL + path, data=body, method="POST")
    req.add_header("X-API-Key", API_KEY)
    req.add_header("tenant-id", TENANT_ID)
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    return _read_result(req, timeout)


def print_quote(app):
    """从任务详情解析并打印报价单摘要（confirm 前必须展示给用户）"""
    raw = app.get("priceQuote")
    if not raw:
        print("  报价单：尚未回写，请稍后用 wait --for quote 继续")
        return
    try:
        quote = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        quote = {}
    tier = quote.get("tier") or app.get("complexityTier") or "-"
    quoted = quote.get("credits") if quote.get("credits") is not None else app.get("quotedCredits")
    discount = quote.get("firstOrderDiscount") if quote.get("firstOrderDiscount") is not None else app.get("firstOrderDiscount") or 0
    try:
        final = max(1, int(quoted or 0) - int(discount or 0))
    except (TypeError, ValueError):
        final = quoted
    print("  ─────────────── 报价单 ───────────────")
    print("  复杂度档位：%s" % tier)
    print("  标准 Credits：%s" % quoted)
    if discount:
        print("  首单优惠：-%s" % discount)
    print("  确认冻结 Credits：%s（失败全额退回；源码导出后不再退款）" % final)
    signals = quote.get("server_signals") or []
    uncovered = [s.get("group") for s in signals if isinstance(s, dict) and not s.get("covered") and s.get("group")]
    if uncovered:
        print("  平台未覆盖的服务端能力：%s（可简化需求，或联系客服定制后端）" % "、".join(uncovered))
    print("  ─────────────────────────────────────")


def fmt_time(v):
    """createTime 兼容毫秒时间戳（服务端 jackson 序列化）与字符串两种形态"""
    if v is None:
        return "-"
    try:
        ts = float(v)
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts / 1000.0 if ts > 1e11 else ts))
    except (TypeError, ValueError):
        return str(v)[:16]


def print_app(app):
    status = app.get("devStatus")
    print("任务 #%s「%s」" % (app.get("id"), app.get("appName")))
    print("  状态：%s（%s）" % (status, STATUS_TEXT.get(status, "未知")))
    print("  包名：%s" % app.get("packageName"))
    if app.get("devStatus") in (3, 4) or app.get("priceQuote"):
        print_quote(app)
    if app.get("apkUrl"):
        print("  APK：%s" % app.get("apkUrl"))
    if app.get("sourceUrl"):
        print("  源码：%s" % app.get("sourceUrl"))
    if app.get("qcReportUrl"):
        print("  质检报告：%s" % app.get("qcReportUrl"))
    if status == 2 and app.get("failReason"):
        print("  失败原因：%s" % app.get("failReason"))


def strip_common_root(members):
    """若压缩包所有条目共享同一顶层目录则剥离（源码包可能是 customer_x/ 前缀）"""
    roots = set(m.filename.split("/", 1)[0] for m in members if m.filename.strip())
    if len(roots) == 1 and not roots.pop().endswith((".gradle", ".md", ".txt", ".xml", ".json", ".gitignore", ".properties")):
        return True
    return False


def cmd_submit(args):
    if args.h5_zip and args.h5_zip_url:
        raise ApiError("--h5-zip 与 --h5-zip-url 只能二选一")
    body = {"appName": args.name, "codePrompt": args.prompt}
    if args.type:
        body["appType"] = args.type
    if args.style:
        body["uiPrompt"] = args.style
    if args.package:
        body["packageName"] = args.package
    if args.callback_url:
        body["callbackUrl"] = args.callback_url
    if args.h5_zip_url:
        body["h5PrototypeZipUrl"] = args.h5_zip_url
    elif args.h5_zip:
        print("上传 H5 原型 %s …" % args.h5_zip)
        up = http_upload("/app-api/appgo/dev-app/upload-prototype", args.h5_zip)
        body["h5PrototypeZipUrl"] = up.get("url")
        body["h5PrototypeZipName"] = up.get("fileName") or os.path.basename(args.h5_zip)
    app_id = http_json("POST", "/app-api/appgo/dev-app/create", body)
    print("任务创建成功：#%s「%s」" % (app_id, args.name))
    if body.get("h5PrototypeZipUrl"):
        print("H5 原型已随任务提交：生成时 UI 以原型为第一依据；原型无法解析时自动降级纯描述模式")
    if args.callback_url:
        print("Webhook 回调已配置：%s（webhookSecret 用 get --json 查看）" % args.callback_url)
    print("下一步：python appgo.py wait --id %s --for quote（复杂度评估通常几分钟）" % app_id)
    return app_id


def cmd_upload(args):
    """上传 H5/UI 原型 zip，返回 URL（高级用法：submit --h5-zip-url 引用已有托管文件）"""
    data = http_upload("/app-api/appgo/dev-app/upload-prototype", args.file)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return data
    print("原型已上传：")
    print("  url      = %s" % data.get("url"))
    print("  fileName = %s" % data.get("fileName"))
    print("下一步：python appgo.py submit --name ... --prompt ... --h5-zip-url '%s'" % data.get("url"))
    return data


def cmd_get(args):
    app = http_json("GET", "/app-api/appgo/dev-app/get?id=%s" % args.id)
    if args.json:
        print(json.dumps(app, ensure_ascii=False, indent=2))
    else:
        print_app(app)
    return app


def cmd_list(args):
    apps = http_json("GET", "/app-api/appgo/dev-app/my-list")
    if args.json:
        print(json.dumps(apps, ensure_ascii=False, indent=2))
        return apps
    if not apps:
        print("暂无任务")
        return []
    for a in apps:
        print("#%s「%s」状态 %s（%s）· 创建 %s" % (
            a.get("id"), a.get("appName"), a.get("devStatus"),
            STATUS_TEXT.get(a.get("devStatus"), "未知"), fmt_time(a.get("createTime"))))
    return apps


def cmd_confirm(args):
    if not args.yes:
        app = http_json("GET", "/app-api/appgo/dev-app/get?id=%s" % args.id)
        if app.get("devStatus") != 3:
            raise ApiError("任务 #%s 当前状态为 %s（%s），仅待确认状态可确认" % (args.id, app.get("devStatus"), STATUS_TEXT.get(app.get("devStatus"), "未知")))
        print("即将确认以下报价并冻结 Credits：")
        print_app(app)
        answer = input("确认请输入 yes：").strip().lower()
        if answer != "yes":
            print("已取消，未产生任何费用")
            return
    http_json("POST", "/app-api/appgo/dev-app/confirm", {"id": args.id})
    print("已确认，Credits 已冻结，生成已启动")
    print("下一步：python appgo.py wait --id %s --for done" % args.id)


def cmd_wait(args):
    targets = TERMINAL_DONE if args.for_ == "done" else ([3] if args.for_ == "quote" else [1, 2, 3])
    labels = {"quote": "报价（状态 3）", "done": "终态（完成/失败）", "any": "状态变化"}
    deadline = time.time() + args.timeout
    last = None
    print("等待任务 #%s %s（每 %ss 轮询一次，最长 %ss）…" % (args.id, labels[args.for_], args.interval, args.timeout))
    while True:
        app = http_json("GET", "/app-api/appgo/dev-app/get?id=%s" % args.id)
        status = app.get("devStatus")
        if status != last:
            print("[%s] 状态：%s（%s）" % (time.strftime("%H:%M:%S"), status, STATUS_TEXT.get(status, "未知")))
            last = status
        if status in targets:
            if args.json:
                print(json.dumps(app, ensure_ascii=False, indent=2))
            else:
                print_app(app)
            if status == 1:
                print("下一步：python appgo.py download --id %s --out ./%s" % (args.id, app.get("appName", "app")))
            elif status == 2:
                print("生成失败：Credits 已全额退回，可调整需求后重新 submit")
            elif status == 3:
                print("下一步：向用户展示上方报价单，经确认后再执行 confirm")
            return app
        if time.time() >= deadline:
            raise ApiError("等待超时（%ss）。生成可能仍在进行，可稍后重试 wait 或用 get 查看当前状态" % args.timeout)
        time.sleep(args.interval)


def cmd_download(args):
    app = http_json("GET", "/app-api/appgo/dev-app/get?id=%s" % args.id)
    if app.get("devStatus") != 1:
        raise ApiError("任务 #%s 尚未完成（当前状态 %s），无法下载源码" % (args.id, app.get("devStatus")))
    out = os.path.abspath(args.out or ".")
    os.makedirs(out, exist_ok=True)
    zip_path = os.path.join(out, "appgo-source-%s.zip" % args.id)
    url = BASE_URL + "/app-api/appgo/dev-app/source-download?id=%s" % args.id
    req = urlrequest.Request(url, method="GET")
    req.add_header("X-API-Key", API_KEY)
    req.add_header("tenant-id", TENANT_ID)
    print("下载源码包…")
    with urlrequest.urlopen(req, timeout=300) as resp, open(zip_path, "wb") as f:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    size = os.path.getsize(zip_path)
    if size < 2048:
        raise ApiError("下载的源码包异常（%s 字节），请稍后重试或联系客服" % size)
    print("已下载：%s（%.1f MB）" % (zip_path, size / 1024.0 / 1024.0))
    extract_to = os.path.join(out, app.get("appName") or "appgo-app")
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        strip = strip_common_root(members)
        for m in members:
            if m.is_dir():
                continue
            name = m.filename.split("/", 1)[1] if strip else m.filename
            target = os.path.join(extract_to, *name.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(zf.read(m))
    os.remove(zip_path)
    print("源码已解压到：%s" % extract_to)
    print("已剥离内部构建缓存与凭据；可直接导入 Android Studio 二次开发。")
    print("注意：源码一经导出不再受理退款；本地修改后的代码不在免费修复窗口内。")
    return extract_to


def cmd_iterate_quote(args):
    """迭代报价预览（不产生计费/状态变更；agent 必须先向用户展示本轮报价）"""
    quote = http_json("POST", "/app-api/appgo/dev-app/iterate/quote",
                      {"id": args.id, "iterationPrompt": args.add})
    if args.json:
        print(json.dumps(quote, ensure_ascii=False, indent=2))
        return quote
    print("任务 #%s 迭代报价预览：" % args.id)
    print("  迭代需求：%s" % args.add)
    print("  复杂度打分：%s（档位 %s，变更附加分 %s）" % (
        quote.get("score"), quote.get("tier") or "-", quote.get("surchargeScore") or 0))
    print("  本轮迭代：%s 元 = %s Credits（失败全额退回）" % (quote.get("quoteYuan"), quote.get("quoteCredits")))
    print("  当前余额：%s Credits（充足：%s）" % (
        quote.get("balance"), "是" if quote.get("balanceEnough") else "否"))
    if quote.get("overLimit"):
        print("  注意：本轮需求超出迭代范围（旗舰档），平台将拒绝执行；建议作为新应用重新 submit")
    print("  下一步：向用户展示本轮报价，经确认后再执行 python appgo.py iterate --id %s --expected-credits %s" % (
        args.id, quote.get("quoteCredits")))
    return quote


def cmd_iterate(args):
    """发起迭代优化（前置：agent 已通过 iterate-quote 向用户展示报价并获确认）"""
    body = {"id": args.id, "iterationPrompt": args.add}
    if args.expected_credits is not None:
        body["expectedCredits"] = args.expected_credits
    http_json("POST", "/app-api/appgo/dev-app/iterate", body)
    print("迭代已发起：任务 #%s 进入生成中，Credits 已按本轮报价冻结（失败全额退回）" % args.id)
    print("下一步：python appgo.py wait --id %s --for done" % args.id)


def cmd_retry(args):
    """失败任务重新生成（仅首次生成失败可用；按原确认冻结额重新冻结）"""
    http_json("POST", "/app-api/appgo/dev-app/retry", {"id": args.id})
    print("重新生成已发起：任务 #%s 复用原始需求，按原确认冻结额重新冻结 Credits" % args.id)
    print("下一步：python appgo.py wait --id %s --for done" % args.id)


def cmd_redesign(args):
    """简化需求重新报价（仅待确认状态可用；回到待开发重新评估）"""
    http_json("POST", "/app-api/appgo/dev-app/redesign", {"id": args.id, "codePrompt": args.prompt})
    print("需求已简化：任务 #%s 回到待开发（0），流水线重新评估报价（通常几分钟）" % args.id)
    print("下一步：python appgo.py wait --id %s --for quote，出新报价后向用户确认再 confirm" % args.id)


def cmd_webhook_logs(args):
    """查询任务 Webhook 投递记录（需创建时传 callbackUrl）"""
    logs = http_json("GET", "/app-api/appgo/dev-app/webhook-logs?id=%s" % args.id)
    if args.json:
        print(json.dumps(logs, ensure_ascii=False, indent=2))
        return logs
    if not logs:
        print("任务 #%s 暂无 Webhook 投递记录（未配置 callbackUrl 或尚无状态变更）" % args.id)
        return []
    print("任务 #%s Webhook 投递记录（新→旧）：" % args.id)
    for lg in logs:
        print("  [%s] %s · %s · HTTP %s · 已失败 %s 次%s" % (
            fmt_time(lg.get("createTime")),
            EVENT_TEXT.get(lg.get("event"), lg.get("event")),
            WEBHOOK_STATUS_TEXT.get(lg.get("status"), lg.get("status")),
            lg.get("statusCode") if lg.get("statusCode") is not None else "-",
            lg.get("retryCount") or 0,
            (" · 原因：%s" % lg.get("failReason")) if lg.get("failReason") else ""))
    return logs


def build_parser():
    parser = argparse.ArgumentParser(prog="appgo", description="AppGo Open API CLI（AI 生成 Android APP，源码本地二次开发）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出原始数据（供 agent 消费）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("submit", help="提交生成需求（创建任务，创建免费）")
    p.add_argument("--name", required=True, help="应用名称（≤20 字）")
    p.add_argument("--prompt", required=True, help="功能描述（10~2000 字，越具体报价越准）")
    p.add_argument("--type", help="应用品类（可选，留空自动推断）")
    p.add_argument("--style", help="视觉风格（可选，如 简约蓝）")
    p.add_argument("--package", help="包名（可选，留空平台自动分配）")
    p.add_argument("--callback-url", help="Webhook 回调地址（可选，http/https；报价已出/完成/失败时 POST 通知）")
    p.add_argument("--h5-zip", help="H5/UI 原型 zip 路径（可选，自动上传后随任务提交；含页面 HTML/icons/PRODUCT_SPECS.md，≤50MB）")
    p.add_argument("--h5-zip-url", help="H5/UI 原型 zip 的已托管 URL（可选，与 --h5-zip 二选一）")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("upload", help="上传 H5/UI 原型 zip，返回 URL（高级用法，一般直接 submit --h5-zip）")
    p.add_argument("file", help="本地 .zip 文件路径（≤50MB）")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("get", help="查询任务详情（含状态与报价单）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("list", help="列出我的全部任务")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("confirm", help="确认报价并冻结 Credits（确认前必须已向用户展示报价单）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--yes", action="store_true", help="跳过交互确认（agent 已获得用户明确同意后使用）")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_confirm)

    p = sub.add_parser("wait", help="轮询等待任务到达目标状态")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--for", dest="for_", choices=["quote", "done", "any"], default="any",
                   help="quote=等报价(3) done=等终态(1/2) any=任一变化（默认）")
    p.add_argument("--timeout", type=int, default=3600, help="最长等待秒（默认 3600）")
    p.add_argument("--interval", type=int, default=20, help="轮询间隔秒（默认 20）")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_wait)

    p = sub.add_parser("download", help="下载已完成任务的源码并解压到本地")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--out", help="输出目录（默认当前目录）")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("iterate-quote", help="迭代报价预览（iterate 前必须向用户展示本轮报价）")
    p.add_argument("--id", required=True, help="任务编号（仅已完成任务可迭代）")
    p.add_argument("--add", required=True, help="迭代需求描述（≤1000 字）")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_iterate_quote)

    p = sub.add_parser("iterate", help="发起迭代优化（前置：iterate-quote 已展示报价且用户确认）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--add", required=True, help="迭代需求描述（≤1000 字）")
    p.add_argument("--expected-credits", type=int,
                   help="iterate-quote 返回的本轮 Credits（防预览与实扣不一致，推荐传入）")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_iterate)

    p = sub.add_parser("retry", help="失败任务重新生成（按原确认冻结额，仅首次生成失败可用）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_retry)

    p = sub.add_parser("redesign", help="简化需求重新报价（回到待开发重新评估，原确认冻结额退回）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--prompt", required=True, help="简化后的功能描述")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_redesign)

    p = sub.add_parser("webhook-logs", help="查询任务 Webhook 投递记录（需创建时传 callbackUrl）")
    p.add_argument("--id", required=True, help="任务编号")
    p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_webhook_logs)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ApiError as e:
        sys.stderr.write("错误：%s\n" % e)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\n已中断\n")
        sys.exit(130)


if __name__ == "__main__":
    main()
